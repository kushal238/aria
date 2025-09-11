# app/security.py
#
# This module handles security-related functions, such as token verification,
# password hashing, and authorization dependencies.

import os
import time
from typing import Dict, Any, Optional, List

import boto3
import httpx
import jwt as pyjwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer

# Since crud functions are now in their own module, we import from there.
from .crud import db_get_user_by_id

# --- Configuration ---
# Function to fetch the secret from SSM Parameter Store or environment
def get_api_jwt_secret():
    """Retrieves the API JWT secret from SSM or environment variables."""
    if "API_JWT_SECRET" in os.environ:
        return os.environ["API_JWT_SECRET"]

    try:
        ssm_client = boto3.client('ssm')
        parameter_name = os.environ['API_JWT_SECRET_NAME']
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        secret = response['Parameter']['Value']
        os.environ["API_JWT_SECRET"] = secret # Cache it
        return secret
    except Exception:
        # Fallback for local testing if SSM is not available
        return "default_secret_for_local_testing"

# --- Constants ---
API_JWT_SECRET = get_api_jwt_secret()
JWT_ALGORITHM = "HS256"
API_TOKEN_EXPIRY_MINUTES = 60

# --- Cognito JWK Fetching ---
# These are needed for the Cognito authorizer logic
COGNITO_REGION = os.getenv("COGNITO_REGION")
COGNITO_USERPOOL_ID = os.getenv("COGNITO_USERPOOL_ID")
COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USERPOOL_ID}"
COGNITO_JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

jwks_cache: Optional[List[Dict[str, Any]]] = None

async def get_jwks() -> List[Dict[str, Any]]:
    """Fetches and caches Cognito JSON Web Keys."""
    global jwks_cache
    if jwks_cache is None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(COGNITO_JWKS_URL)
                response.raise_for_status()
                jwks_cache = response.json()["keys"]
            except Exception:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not fetch auth keys")
    return jwks_cache


def get_cognito_user_info(request: Request) -> Dict[str, Any]:
    """
    Dependency that extracts user claims from the Cognito authorizer context
    provided by API Gateway.
    """
    try:
        # The claims are added to the request scope by the Mangum adapter
        claims = request.scope['aws.event']['requestContext']['authorizer']['claims']
        if not claims.get("sub"):
            raise HTTPException(status_code=401, detail="User identifier missing from token")
        return claims
    except KeyError:
        # This will happen if the authorizer context is not available
        # (e.g., when testing locally without API Gateway)
        print("WARN: Cognito authorizer context not found. This is expected for local testing.")
        # In a real deployed environment, this should be a hard failure.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials (Authorizer context missing)"
        )


# --- Token Generation ---
def create_final_api_token(user_id: str, cognito_sub: str) -> str:
    """Creates the main API session JWT containing internal user ID."""
    payload = {
        "sub": user_id,
        "cognito_sub": cognito_sub,
        "aud": "api_access",
        "exp": time.time() + (API_TOKEN_EXPIRY_MINUTES * 60),
        "iat": time.time()
    }
    token = pyjwt.encode(payload, API_JWT_SECRET, algorithm=JWT_ALGORITHM)
    print(f"JWT: Generated final API token for internal ID: {user_id}")
    return token

# --- Authentication Dependencies ---
oauth2_scheme_api = OAuth2PasswordBearer(tokenUrl="dummy")

async def verify_api_token(token: str = Depends(oauth2_scheme_api)) -> Dict[str, Any]:
    """Dependency to verify the backend's own final API session token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate API credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = pyjwt.decode(
            token,
            API_JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience="api_access"
        )
        internal_user_id: str = payload.get("sub")
        if internal_user_id is None:
            raise credentials_exception

        if not db_get_user_by_id(internal_user_id):
             print(f"API Token valid, but user ID {internal_user_id} not found in DB.")
             raise credentials_exception

        print(f"Backend API token verified for internal user ID: {internal_user_id}")
        return payload

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API token has expired")
    except pyjwt.InvalidAudienceError:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token audience")
    except pyjwt.PyJWTError:
         raise credentials_exception
