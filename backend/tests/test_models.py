# backend/tests/test_models.py
#
# This file contains the unit tests for the Pydantic models defined in `app/models.py`.
# Unit tests are designed to test small, isolated pieces of code (like a single model)
# to ensure they behave as expected. They are crucial for verifying data integrity and
# validation logic.

import pytest
# We import the Pydantic models we want to test directly from their module.
from backend.app.models import UserResponse, PatientProfile

# --- Test Data Fixtures ---
# Test fixtures are predefined, consistent data sets used as input for tests.
# This ensures that our tests are repeatable and not subject to random variations.

# A dictionary representing a complete and valid user profile. This data structure
# mirrors what we might get from a database query, and it should parse
# successfully into our UserResponse model without any errors.
VALID_USER_DATA = {
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

# A dictionary representing an invalid user profile. Pydantic models have required
# fields. This data is missing 'internal_user_id' and 'roles', which should cause the
# UserResponse model to raise a validation error upon parsing.
INVALID_USER_DATA_MISSING_FIELD = {
    "cognito_sub": "cognito-sub-abc",
    "first_name": "Test",
    "email": "test@example.com"
}

# --- Test Cases ---

def test_user_response_model_success():
    """
    Tests the "happy path" for the UserResponse model.
    It verifies that the model can be successfully created from a valid Python dictionary.
    """
    # The core of the test: we attempt to create an instance of the UserResponse model
    # by unpacking the VALID_USER_DATA dictionary. If the dictionary's structure or
    # data types don't match the model's definition, Pydantic will raise a
    # ValidationError, and the test will fail.
    user = UserResponse(**VALID_USER_DATA)

    # After successful creation, we assert that the data was parsed correctly
    # and is accessible as attributes on the resulting Python object.
    assert user.internal_user_id == "test-user-123"
    assert user.first_name == "Test"
    
    # We also check that nested models were parsed correctly. The `patient_profile`
    # attribute should be an instance of the PatientProfile class, not a dictionary.
    assert isinstance(user.patient_profile, PatientProfile)
    assert user.patient_profile.status == "ACTIVE"
    assert user.doctor_profile is None

def test_user_response_model_validation_error():
    """
    Tests the "sad path" for the UserResponse model.
    It verifies that the model correctly raises an exception when it receives
    data that is missing required fields.
    """
    # `pytest.raises` is a context manager that checks if a specific type of
    # exception is raised within its block. The test will only pass if a
    # ValidationError (or any Exception, as specified here for simplicity)
    # is raised. If no exception is raised, the test will fail.
    with pytest.raises(Exception): # Pydantic's ValidationError
        UserResponse(**INVALID_USER_DATA_MISSING_FIELD)
