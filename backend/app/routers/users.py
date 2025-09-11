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
)
from ..security import verify_api_token
from ..database import users_table

router = APIRouter()


@router.post("/users/complete-profile", response_model=UserResponse, tags=["User Profile"])
async def complete_user_profile(
    profile_data: ProfileData,
    token_payload: Dict[str, Any] = Depends(verify_api_token)
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


@router.get("/users/search", response_model=List[UserResponse], tags=["Users"])
async def search_patients(
    q: str,
    token_payload: Dict[str, Any] = Depends(verify_api_token)
):
    """
    Search for patients by name. Doctor-only endpoint.
    NOTE: This uses a scan operation, which is not efficient for large tables.
          For a production system, a dedicated search index is recommended.
    """
    user_id = token_payload.get("sub")
    user = db_get_full_user_profile(user_id)
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
