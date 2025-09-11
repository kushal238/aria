# app/routers/auth.py
#
# This router handles all authentication-related endpoints,
# such as user login and token generation.

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from ..models import LoginResponse, UserResponse
from ..crud import (
    db_find_or_create_user_by_cognito_sub,
    db_get_user_by_cognito_sub,
    db_get_full_user_profile,
)
from ..security import get_cognito_user_info, create_final_api_token
import os

router = APIRouter()

# --- Configuration ---
PATIENT_APP_CLIENT_ID = os.getenv("PATIENT_APP_CLIENT_ID")
DOCTOR_APP_CLIENT_ID = os.getenv("DOCTOR_APP_CLIENT_ID")


@router.post("/auth/login", response_model=LoginResponse, tags=["Authentication"])
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
