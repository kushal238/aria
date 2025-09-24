# app/routers/users.py
#
# This router handles endpoints related to user management,
# such as retrieving user profiles and completing sign-up.

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status

from ..models import UserResponse, ProfileData
from ..crud import (
    db_update_user_profile,
    db_get_full_user_profile,
    db_get_user_by_id,
    db_get_user_by_cognito_sub,
)
from ..security import get_cognito_user_info
from ..database import users_table

router = APIRouter()


@router.post("/users/complete-profile", response_model=UserResponse, tags=["User Profile"])
async def complete_user_profile(
    profile_data: ProfileData,
    cognito_claims: Dict[str, Any] = Depends(get_cognito_user_info)
):
    """
    Updates the profile for the currently logged-in user.
    Uses Cognito authorizer claims to resolve the internal user ID.
    """
    try:
        cognito_sub = cognito_claims.get("sub")
        if not cognito_sub:
            raise HTTPException(status_code=400, detail="Cognito SUB missing from token.")

        user_record = db_get_user_by_cognito_sub(cognito_sub)
        if not user_record or not user_record.get("userId"):
            raise HTTPException(status_code=404, detail="User not found for Cognito SUB.")
        internal_user_id = user_record["userId"]

        print(f"Completing profile for internal user ID: {internal_user_id}")

        updated_user = db_update_user_profile(internal_user_id, profile_data)

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User record not found to update profile."
            )

        return UserResponse(**updated_user)

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error completing profile: {e}")
        raise HTTPException(status_code=500, detail="Error completing user profile.")


@router.get("/users/me", response_model=UserResponse, tags=["User Profile"])
async def read_users_me(cognito_claims: Dict[str, Any] = Depends(get_cognito_user_info)):
    """
    Get profile information for the currently authenticated user.
    Uses Cognito claims to resolve the internal user ID.
    """
    cognito_sub = cognito_claims.get("sub")
    user_record = db_get_user_by_cognito_sub(cognito_sub)
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found in database")

    user_data = db_get_full_user_profile(user_record["userId"])
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found in database")

    return UserResponse(**user_data)


@router.get("/users/search", response_model=List[UserResponse], tags=["Users"])
async def search_patients(
    q: str,
    cognito_claims: Dict[str, Any] = Depends(get_cognito_user_info)
):
    """
    Search for patients by name. Doctor-only endpoint.
    NOTE: This uses a scan operation, which is not efficient for large tables.
          For a production system, a dedicated search index is recommended.
    """
    requester = db_get_user_by_cognito_sub(cognito_claims.get("sub"))
    if not requester:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = db_get_full_user_profile(requester["userId"])
    if 'DOCTOR' not in user.get('roles', []):
        raise HTTPException(status_code=403, detail="Only doctors can search for patients.")

    try:
        response = users_table.scan()
        
        users = []
        q_lower = q.lower()

        for item in response.get('Items', []):
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
