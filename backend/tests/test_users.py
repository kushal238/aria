import pytest
from fastapi.testclient import TestClient

# We need to set the env vars before importing the app
import os
os.environ['COGNITO_REGION'] = "us-east-1"
os.environ['COGNITO_USERPOOL_ID'] = "us-east-1_dummy"
os.environ['PATIENT_APP_CLIENT_ID'] = "dummy_patient_client_id"
os.environ['DOCTOR_APP_CLIENT_ID'] = "dummy_doctor_client_id"
os.environ['API_JWT_SECRET_NAME'] = "dummy_secret_name"
os.environ['API_JWT_SECRET'] = "a_super_secret_key_for_testing"

# Now we can safely import the app and the REAL dependency
from backend.app.main import app
from backend.app.security import verify_api_token

client = TestClient(app)

# This is a sample user profile that our mocked database function will return
# It must match the structure expected by the UserResponse Pydantic model
MOCK_USER_PROFILE = {
    "internal_user_id": "test-user-123",
    "cognito_sub": "cognito-sub-abc",
    "phone_number": "+15555555555",
    "first_name": "Test",
    "last_name": "User",
    "email": "test@example.com",
    "roles": ["PATIENT"],
    "patient_profile": {
        "status": "ACTIVE",
        "date_of_birth": "1990-01-01",
        "sex_assigned_at_birth": "MALE",
        "gender_identity": "MAN",
        "blood_type": "O+"
    },
    "doctor_profile": None
}

# This dependency override will replace the real verify_api_token
# with a function that returns a dummy token payload.
def override_verify_api_token():
    return {"sub": "test-user-123"}

app.dependency_overrides[verify_api_token] = override_verify_api_token


def test_get_current_user_profile(mocker):
    """
    Tests the /users/me endpoint.
    This test verifies that if the database returns a valid user profile,
    the UserResponse model (from its new location) correctly parses and
    returns the data.
    """
    # Mock the database function where it is LOOKED UP (now in the users router),
    # not where it is defined (in app/crud.py). This is a key concept of patching.
    mocker.patch(
        "backend.app.routers.users.db_get_full_user_profile", # Correct target
        return_value=MOCK_USER_PROFILE
    )

    # Make the request to the endpoint
    response = client.get("/users/me")

    # Assert the results
    assert response.status_code == 200
    
    # The response JSON should match our Pydantic model structure
    response_data = response.json()
    assert response_data["internal_user_id"] == MOCK_USER_PROFILE["internal_user_id"]
    assert response_data["first_name"] == MOCK_USER_PROFILE["first_name"]
    assert response_data["roles"] == MOCK_USER_PROFILE["roles"]
    assert response_data["patient_profile"]["status"] == "ACTIVE"
