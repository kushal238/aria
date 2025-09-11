"""
In India, clinic doctors still hand physical prescriptions to patients. 
This physical prescription is the only signature of the interaction 
between the doctor and their patient. 

We want to change that. 

We are creating a digital medical record of each doctor-patient interaction. 
The doctor will prescribe the patient on the doctor app, the patient will 
receive the prescription on the patients app, and we will maintain each 
record for both the parties to review anytime and have a history of. 

Additionally, we can deploy AI agents that can order based on the 
prescriptions, help doctors find patterns, etc.
"""
# main.py 
# --- Imports ---
import os
import time
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import boto3
import uvicorn
import httpx  # For async HTTP requests to get JWKs
from jose import jwk, jwt
from jose.utils import base64url_decode
import jwt as pyjwt # Rename original jwt import to avoid conflict if needed, or just use jose.jwt

# --- FastAPI Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, Body, Request, Header
from fastapi.security import OAuth2PasswordBearer
from mangum import Mangum

# --- Pydantic Imports ---
from pydantic import BaseModel, Field

from app.models import *
from app.database import (
    users_table,
    patients_table,
    doctors_table,
    prescriptions_table,
    dynamodb
)
from app.crud import (
    db_get_user_by_id, 
    db_get_user_by_cognito_sub,
    db_get_full_user_profile,
    db_find_or_create_user_by_cognito_sub,
    db_update_user_profile
)

# --- Firebase Admin Imports (Commented out for Auth - Keep if needed for OTHER services) ---
# import firebase_admin
# from firebase_admin import credentials #, auth # Commented out auth

# --- Configuration ---
# Function to fetch the secret from SSM Parameter Store
def get_api_jwt_secret():
    """Retrieves the API JWT secret from SSM Parameter Store."""
    if "API_JWT_SECRET" in os.environ:
        return os.environ["API_JWT_SECRET"]

    try:
        ssm_client = boto3.client('ssm')
        parameter_name = os.environ['API_JWT_SECRET_NAME']
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        secret = response['Parameter']['Value']
        os.environ["API_JWT_SECRET"] = secret # Cache it for subsequent invocations
        return secret
    except Exception as e:
        print(f"FATAL: Could not retrieve API_JWT_SECRET from SSM Parameter Store: {e}")
        # In a real-world scenario, you'd want to handle this failure gracefully.
        # For now, we'll run in an insecure state.
        # exit(1)
API_JWT_SECRET = os.environ.get("API_JWT_SECRET", "default_secret_for_local_testing")

JWT_ALGORITHM = "HS256"
API_TOKEN_EXPIRY_MINUTES = 60 # e.g., 1 hour for final token

# --- DynamoDB Configuration ---

# --- Cognito Configuration ---
# Load from environment variables set in SAM template
COGNITO_REGION = os.getenv("COGNITO_REGION")
COGNITO_USERPOOL_ID = os.getenv("COGNITO_USERPOOL_ID")
PATIENT_APP_CLIENT_ID = os.getenv("PATIENT_APP_CLIENT_ID")
DOCTOR_APP_CLIENT_ID = os.getenv("DOCTOR_APP_CLIENT_ID")

if not all([COGNITO_REGION, COGNITO_USERPOOL_ID, PATIENT_APP_CLIENT_ID, DOCTOR_APP_CLIENT_ID]):
    print("ERROR: Missing Cognito environment variables")
    exit(1)

COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USERPOOL_ID}"
COGNITO_JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"


# --- Firebase Admin SDK Initialization (Commented out - Only needed if using other Firebase services) ---
# cred_path = os.getenv("FIREBASE_ADMIN_SDK_CREDENTIALS")
# if not cred_path or not os.path.exists(cred_path):
#     print("Warning: Firebase Admin SDK credentials path not set or invalid.")
#     # exit(1) # Don't exit if only using Cognito for auth
# elif not firebase_admin._apps:
#     try:
#         cred = credentials.Certificate(cred_path)
#         firebase_admin.initialize_app(cred)
#         print("Firebase Admin SDK initialized successfully (if needed for other services).")
#     except Exception as e:
#         print(f"Error initializing Firebase Admin SDK: {e}")
#         # exit(1) # Don't exit if only using Cognito for auth
# else:
#     print("Firebase Admin SDK already initialized (if needed for other services).")
# --- End Firebase Init ---


# --- FastAPI Application Instance Creation ---
app = FastAPI(
    title="Prescription App Backend API (Cognito Auth)",
    description="API using AWS Cognito for authentication."
)

# --- JWK Cache & Fetching ---
# Cache for JWKs to avoid fetching them on every request
jwks_cache: Optional[List[Dict[str, Any]]] = None

async def get_jwks() -> List[Dict[str, Any]]:
    """Fetches and caches Cognito JSON Web Keys."""
    global jwks_cache
    # Re-fetch periodically in a real app, but cache for now
    if jwks_cache is None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(COGNITO_JWKS_URL)
                response.raise_for_status() # Raise HTTPStatusError for bad responses (4xx or 5xx)
                jwks_cache = response.json()["keys"]
                print(f"Fetched Cognito JWKs successfully from {COGNITO_JWKS_URL}")
            except httpx.RequestError as e:
                print(f"Error fetching JWKs: {e}")
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not fetch authentication keys")
            except Exception as e:
                print(f"Error processing JWKs: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing authentication keys")
    if jwks_cache is None: # Check again in case fetching failed silently somehow
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication keys unavailable")
    return jwks_cache

# --- Pydantic Models ---

# --- Database Placeholder Functions (Rewritten for DynamoDB) ---


# --- Backend Token Generation Function ---
def create_final_api_token(user_id: str, cognito_sub: str) -> str:
    """Creates the main API session JWT containing internal user ID."""
    payload = {
        "sub": user_id, # Use internal DB ID as subject
        "cognito_sub": cognito_sub, # Include cognito sub if needed later
        "aud": "api_access", # Audience claim: main API access
        "exp": time.time() + (API_TOKEN_EXPIRY_MINUTES * 60),
        "iat": time.time()
    }
    # Use pyjwt (imported as jwt) or jose.jwt - stick to one for consistency
    # Using pyjwt here as it was likely installed already
    token = pyjwt.encode(payload, API_JWT_SECRET, algorithm=JWT_ALGORITHM)
    print(f"JWT: Generated final API token for internal ID: {user_id}")
    return token

# --- Authentication Dependencies ---
oauth2_scheme_api = OAuth2PasswordBearer(tokenUrl="dummy") # For extracting Bearer token

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
        # For local testing, you might return a dummy user or raise an error
        # In a real deployed environment, this should be a hard failure.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials (Authorizer context missing)"
        )

async def verify_api_token(token: str = Depends(oauth2_scheme_api)) -> Dict[str, Any]:
    """Dependency to verify the backend's own final API session token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate API credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Using pyjwt here for consistency with generation function
        payload = pyjwt.decode(
            token,
            API_JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience="api_access" # Check audience for API access
        )
        internal_user_id: str = payload.get("sub")
        if internal_user_id is None:
            raise credentials_exception

        # Check if user user_id exists in our real DB now
        if not db_get_user_by_id(internal_user_id):
             print(f"API Token valid, but user ID {internal_user_id} not found in DB.")
             raise credentials_exception # Treat as invalid if user doesn't exist

        print(f"Backend API token verified for internal user ID: {internal_user_id}")
        return payload # Contains 'sub' (internal_id) and 'cognito_sub'

    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API token has expired")
    except pyjwt.InvalidAudienceError:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token audience")
    except pyjwt.PyJWTError as e:
         print(f"API token validation error: {e}")
         raise credentials_exception

# --- Request Model for Cognito Token Input ---

# --- API Endpoints ---

@app.get("/health", tags=["Health Check"])
def health_check():
    """A simple endpoint to confirm the API is running."""
    return {"status": "ok"}

@app.post("/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def cognito_login(
    cognito_claims: Dict[str, Any] = Depends(get_cognito_user_info)
):
    """
    Handles first-time login/registration after successful Cognito authentication.
    API Gateway Cognito Authorizer validates the token. This function then finds
    or creates a user in the local DB and returns the backend's own API session token.
    The App Client ID from the token determines the user's role.
    """
    try:
        cognito_sub = cognito_claims.get("sub")
        phone_number = cognito_claims.get("phone_number")
        email = cognito_claims.get("email")
        # Securely determine the app type from the token's audience claim
        app_client_id = cognito_claims.get("aud")

        if not cognito_sub:
            raise HTTPException(status_code=400, detail="Cognito SUB missing from token.")

        # Determine app type based on the client ID
        if app_client_id == PATIENT_APP_CLIENT_ID:
            app_type = 'PATIENT'
        elif app_client_id == DOCTOR_APP_CLIENT_ID:
            app_type = 'DOCTOR'
        else:
            print(f"ERROR: Unrecognized App Client ID: {app_client_id}")
            raise HTTPException(status_code=400, detail="Invalid App Client ID in token.")

        # Find or create user in local DB, now with secure app context
        db_find_or_create_user_by_cognito_sub(cognito_sub, phone_number, email, app_type)
        
        # We need the full user ID to generate a token and the full profile for the response
        user_record = db_get_user_by_cognito_sub(cognito_sub)
        if not user_record or not user_record.get("userId"):
             raise HTTPException(status_code=500, detail="Failed to retrieve user record after creation.")
        
        internal_user_id = user_record["userId"]

        # Issue the final backend API token
        final_api_token = create_final_api_token(internal_user_id, cognito_sub)

        # Get the newly structured full profile
        user_profile_for_response = db_get_full_user_profile(internal_user_id)
        if not user_profile_for_response:
            raise HTTPException(status_code=500, detail="Failed to construct user profile for response.")

        return LoginResponse(
            message="Login successful.",
            api_token=final_api_token,
            user_profile=UserResponse(**user_profile_for_response)
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error during Cognito login processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during login.")


@app.post("/users/complete-profile", response_model=UserResponse, tags=["User Profile"])
async def complete_user_profile(
    profile_data: ProfileData,
    token_payload: Dict[str, Any] = Depends(verify_api_token) # Now requires the FINAL backend api_token
):
    """
    Updates the profile for the currently logged-in user.
    Requires a valid backend api_token.
    """
    try:
        internal_user_id = token_payload.get("sub")
        if not internal_user_id:
             raise HTTPException(status_code=400, detail="User ID missing from token payload.")

        print(f"Completing profile for internal user ID: {internal_user_id}")

        # Update user profile in your database using internal_user_id
        updated_user = db_update_user_profile(internal_user_id, profile_data)

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User record not found to update profile."
            )

        # Return the updated, nested user profile
        return UserResponse(**updated_user)

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error completing profile: {e}")
        raise HTTPException(status_code=500, detail="Error completing user profile.")


@app.get("/users/me", response_model=UserResponse, tags=["User Profile"])
async def read_users_me(token_payload: Dict[str, Any] = Depends(verify_api_token)):
    """
    Get profile information for the currently authenticated user.
    Verifies the final backend api_token.
    """
    internal_user_id = token_payload.get("sub")
    user_data = db_get_full_user_profile(internal_user_id)

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found in database")

    return UserResponse(**user_data)

# --- Prescription Endpoints ---

@app.get("/users/search", response_model=List[UserResponse], tags=["Prescriptions"])
async def search_patients(
    q: str,
    token_payload: Dict[str, Any] = Depends(verify_api_token)
):
    """
    Search for patients by name. Doctor-only endpoint.
    NOTE: This uses a scan operation, which is not efficient for large tables.
          For a production system, a dedicated search index (e.g., Elasticsearch) is recommended.
    """
    user_id = token_payload.get("sub")
    user = db_get_full_user_profile(user_id)
    if 'DOCTOR' not in user.get('roles', []):
        raise HTTPException(status_code=403, detail="Only doctors can search for patients.")

    try:
        # Scan the entire Users table. This is inefficient but allows for case-insensitive filtering in code.
        response = users_table.scan()
        
        users = []
        q_lower = q.lower() # Convert search query to lowercase once

        for item in response.get('Items', []):
            # Server-side filtering for role and name (case-insensitive)
            if 'PATIENT' in item.get('roles', []):
                first_name = item.get('firstName', '') or ''
                last_name = item.get('lastName', '') or ''
                
                if q_lower in first_name.lower() or q_lower in last_name.lower():
                    full_profile = db_get_full_user_profile(item['userId'])
                    if full_profile:
                        users.append(UserResponse(**full_profile))
        
        return users
    except Exception as e:
        print(f"Error during patient search: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while searching for patients.")

@app.post("/prescriptions", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED, tags=["Prescriptions"])
async def create_prescription(
    prescription_data: PrescriptionCreate,
    token_payload: Dict[str, Any] = Depends(verify_api_token)
):
    """
    Creates a new prescription. Doctor-only endpoint.
    """
    doctor_id = token_payload.get("sub")
    user = db_get_full_user_profile(doctor_id)

    # Authorization Check
    if not user or 'DOCTOR' not in user.get('roles', []):
        raise HTTPException(status_code=403, detail="User is not authorized to create prescriptions.")
    
    # Ensure patient exists
    patient_user = db_get_full_user_profile(prescription_data.patientId)
    if not patient_user or 'PATIENT' not in patient_user.get('roles', []):
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    timestamp = datetime.now(timezone.utc).isoformat()
    prescription_id = str(uuid.uuid4())
    
    new_prescription = {
        "prescriptionId": prescription_id,
        "patientId": prescription_data.patientId,
        "doctorId": doctor_id,
        "createdAt": timestamp,
        "expiresAt": prescription_data.expiresAt,
        "status": "ACTIVE",
        "diagnosis": prescription_data.diagnosis,
        "medications": [med.dict() for med in prescription_data.medications]
    }
    
    try:
        prescriptions_table.put_item(Item=new_prescription)
        print(f"DB Write: Created prescription {prescription_id} by doctor {doctor_id} for patient {prescription_data.patientId}")
        return PrescriptionResponse(**new_prescription)
    except Exception as e:
        print(f"Error creating prescription: {e}")
        raise HTTPException(status_code=500, detail="Could not create prescription.")

@app.get("/prescriptions", response_model=List[PrescriptionResponse], tags=["Prescriptions"])
async def list_prescriptions(token_payload: Dict[str, Any] = Depends(verify_api_token)):
    """
    Lists prescriptions for the logged-in user.
    If the user is a doctor, it returns prescriptions they've issued.
    If the user is a patient, it returns prescriptions they've received.
    """
    user_id = token_payload.get("sub")
    user = db_get_full_user_profile(user_id)
    roles = user.get('roles', [])
    
    print(f"LIST PRESCRIPTIONS: Called for user {user_id} with roles {roles}")

    try:
        # Collect prescriptions from all relevant roles
        all_prescriptions = []

        if 'DOCTOR' in roles:
            response = prescriptions_table.query(
                IndexName='doctorId-createdAt-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('doctorId').eq(user_id)
            )
            all_prescriptions.extend(response.get('Items', []))
        
        if 'PATIENT' in roles:
            response = prescriptions_table.query(
                IndexName='patientId-createdAt-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('patientId').eq(user_id)
            )
            all_prescriptions.extend(response.get('Items', []))

        # Remove duplicates if a user somehow prescribed to themselves
        # This is an edge case but good practice
        unique_prescriptions = {p['prescriptionId']: p for p in all_prescriptions}.values()

        print(f"LIST PRESCRIPTIONS: Raw DynamoDB query response: {list(unique_prescriptions)}")

        # Enrich prescriptions with patient/doctor names
        enriched_prescriptions = []
        for item in unique_prescriptions:
            # For doctors viewing their list, add the patient's name
            if 'DOCTOR' in roles:
                patient_id = item.get('patientId')
                if patient_id:
                    patient_user = db_get_user_by_id(patient_id)
                    if patient_user:
                        item['patientFirstName'] = patient_user.get('firstName')
                        item['patientLastName'] = patient_user.get('lastName')
            
            # For patients viewing their list, add the doctor's name
            if 'PATIENT' in roles:
                doctor_id = item.get('doctorId')
                if doctor_id:
                    doctor_user = db_get_user_by_id(doctor_id)
                    if doctor_user:
                        item['doctorFirstName'] = doctor_user.get('firstName')
                        item['doctorLastName'] = doctor_user.get('lastName')

            enriched_prescriptions.append(PrescriptionResponse(**item))

        return enriched_prescriptions
    except Exception as e:
        print(f"Error listing prescriptions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve prescriptions.")


@app.get("/prescriptions/{prescription_id}", response_model=PrescriptionResponse, tags=["Prescriptions"])
async def get_prescription(prescription_id: str, token_payload: Dict[str, Any] = Depends(verify_api_token)):
    """
    Retrieves a single prescription by its ID.
    Ensures the logged-in user is either the patient or the doctor on the prescription.
    """
    user_id = token_payload.get("sub")
    
    try:
        response = prescriptions_table.get_item(Key={'prescriptionId': prescription_id})
        prescription = response.get('Item')
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found.")
            
        # Ownership check
        if prescription.get('patientId') != user_id and prescription.get('doctorId') != user_id:
            raise HTTPException(status_code=403, detail="You are not authorized to view this prescription.")
            
        return PrescriptionResponse(**prescription)
    except Exception as e:
        print(f"Error retrieving prescription {prescription_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve prescription.")

@app.put("/prescriptions/{prescription_id}/cancel", response_model=PrescriptionResponse, tags=["Prescriptions"])
async def cancel_prescription(prescription_id: str, token_payload: Dict[str, Any] = Depends(verify_api_token)):
    """
    Cancels a prescription. Only the issuing doctor can perform this action.
    """
    doctor_id = token_payload.get("sub")
    
    try:
        response = prescriptions_table.get_item(Key={'prescriptionId': prescription_id})
        prescription = response.get('Item')
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found.")
        
        # Ownership and status check
        if prescription.get('doctorId') != doctor_id:
            raise HTTPException(status_code=403, detail="Only the issuing doctor can cancel this prescription.")
        if prescription.get('status') != 'ACTIVE':
            raise HTTPException(status_code=400, detail=f"Prescription is already in '{prescription.get('status')}' state.")

        # Update the status to CANCELLED
        updated_response = prescriptions_table.update_item(
            Key={'prescriptionId': prescription_id},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': 'CANCELLED'},
            ReturnValues="ALL_NEW"
        )
        
        return PrescriptionResponse(**updated_response.get('Attributes', {}))
        
    except Exception as e:
        print(f"Error cancelling prescription {prescription_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not cancel prescription.")

# --- Mangum Handler ---
# This handler is the entry point for AWS Lambda
handler = Mangum(app, lifespan="off")


# --- Uvicorn Development Server Runner ---
if __name__ == "__main__":
    print("Starting FastAPI development server...")
    # Ensure dependencies are installed: pip install "uvicorn[standard]" fastapi httpx "python-jose[cryptography]" PyJWT
    # Make sure env variables are set: COGNITO_REGION, COGNITO_USERPOOL_ID, COGNITO_APP_CLIENT_ID, API_JWT_SECRET
    # Optional: FIREBASE_ADMIN_SDK_CREDENTIALS (if using other Firebase services)
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    