import pytest
import time
import asyncio
from fastapi import HTTPException

# Attempt to import the functions we are planning to move.
from backend.app.security import create_final_api_token, verify_api_token

# Define constants for testing, mirroring what will be in security.py
API_JWT_SECRET = "a_super_secret_key_for_testing"
JWT_ALGORITHM = "HS256"

@pytest.mark.asyncio
async def test_token_creation_and_verification(mocker):
    """
    Tests that a token can be created and then successfully verified.
    This is a key test for the core authentication logic.
    """
    # Arrange
    user_id = "test-user-id"
    cognito_sub = "test-cognito-sub"
    
    # Mock the database check inside verify_api_token to always succeed
    mocker.patch("backend.app.security.db_get_user_by_id", return_value={"userId": user_id})

    # Act
    # 1. Create a token
    token = create_final_api_token(user_id, cognito_sub)
    
    # 2. Verify the token - we must 'await' the async function
    payload = await verify_api_token(token)

    # Assert
    assert payload["sub"] == user_id
    assert payload["cognito_sub"] == cognito_sub

@pytest.mark.asyncio
async def test_verify_expired_token(mocker):
    """
    Tests that an expired token raises an HTTPException.
    """
    # Arrange
    mocker.patch("backend.app.security.db_get_user_by_id", return_value={"userId": "any-user"})
    
    # Create a token that expired 1 second ago
    expired_payload = {
        "sub": "test-user-id",
        "exp": time.time() - 1 
    }
    # We need pyjwt to create this custom token for the test
    import jwt as pyjwt
    expired_token = pyjwt.encode(expired_payload, API_JWT_SECRET, algorithm=JWT_ALGORITHM)

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await verify_api_token(expired_token)
    
    # Check that the exception has the correct 401 status code
    assert excinfo.value.status_code == 401
