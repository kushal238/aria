# backend/tests/test_crud.py
#
# This file contains the unit tests for the database interaction functions
# (CRUD operations) defined in `app/crud.py`.

import pytest
from unittest.mock import MagicMock

# Attempt to import the functions we are planning to move.
# This import will fail initially, which is the first step in TDD.
from backend.app.crud import (
    db_get_user_by_id, 
    db_get_user_by_cognito_sub,
    db_get_full_user_profile,
    db_find_or_create_user_by_cognito_sub,
    db_update_user_profile
)
from backend.app.models import ProfileData

# --- Test Cases ---

def test_db_get_user_by_id_found(mocker):
    """
    Tests the db_get_user_by_id function for the case where a user is found.
    """
    # 1. Arrange: Set up the test environment.
    
    # Create a mock object for the DynamoDB table. A MagicMock can simulate
    # any object and its methods.
    mock_users_table = MagicMock()
    
    # Define the fake data we want mock database call to return.
    fake_user_item = {"userId": "test-user-123", "first_name": "Test"}
    mock_users_table.get_item.return_value = {"Item": fake_user_item}
    
    # Use mocker.patch to replace the real `users_table` object in the `crud` module
    # with mock object for the duration of this test.
    mocker.patch("backend.app.crud.users_table", mock_users_table)

    # 2. Act: Call the function we are testing.
    result = db_get_user_by_id("test-user-123")

    # 3. Assert: Verify the outcome.
    
    # Check that the get_item method on mock table was called correctly.
    mock_users_table.get_item.assert_called_once_with(Key={'userId': "test-user-123"})
    
    # Check that the function returned the user item we defined.
    assert result == fake_user_item

def test_db_get_user_by_id_not_found(mocker):
    """
    Tests the db_get_user_by_id function for the case where a user is not found.
    """
    # 1. Arrange
    mock_users_table = MagicMock()
    # Configure the mock to return a response as if the item was not found.
    mock_users_table.get_item.return_value = {"Item": None}
    mocker.patch("backend.app.crud.users_table", mock_users_table)

    # 2. Act
    result = db_get_user_by_id("non-existent-user")

    # 3. Assert
    mock_users_table.get_item.assert_called_once_with(Key={'userId': "non-existent-user"})
    # Check that the function returns None as expected.
    assert result is None

def test_db_get_user_by_cognito_sub_found(mocker):
    """
    Tests db_get_user_by_cognito_sub for the case where a user is found.
    """
    # Arrange
    mock_users_table = MagicMock()
    fake_user_item = {"userId": "test-user-123", "cognitoSub": "cognito-sub-abc"}
    # The `query` method returns a list of items
    mock_users_table.query.return_value = {"Items": [fake_user_item]}
    mocker.patch("backend.app.crud.users_table", mock_users_table)
    mocker.patch("backend.app.crud.boto3") # Mock boto3.dynamodb.conditions

    # Act
    result = db_get_user_by_cognito_sub("cognito-sub-abc")

    # Assert
    assert result == fake_user_item
    mock_users_table.query.assert_called_once()

def test_db_get_user_by_cognito_sub_not_found(mocker):
    """
    Tests db_get_user_by_cognito_sub for the case where a user is not found.
    """
    # Arrange
    mock_users_table = MagicMock()
    # The `query` method returns an empty list if no items are found
    mock_users_table.query.return_value = {"Items": []}
    mocker.patch("backend.app.crud.users_table", mock_users_table)
    mocker.patch("backend.app.crud.boto3")

    # Act
    result = db_get_user_by_cognito_sub("non-existent-sub")

    # Assert
    assert result is None
    mock_users_table.query.assert_called_once()

def test_db_get_full_user_profile_patient_only(mocker):
    """
    Tests db_get_full_user_profile for a user who is only a patient.
    """
    # Arrange
    # Mock the direct DB calls this function makes
    mock_user_core = {"userId": "patient123", "roles": ["PATIENT"], "firstName": "Pat"}
    # Use camelCase keys to match what DynamoDB returns and the function expects
    mock_patient_profile = {
        "userId": "patient123", 
        "status": "ACTIVE", 
        "bloodType": "A+"
    }
    
    # We mock the `db_get_user_by_id` function that this function calls internally
    mocker.patch("backend.app.crud.db_get_user_by_id", return_value=mock_user_core)
    
    # Mock the table calls for patient and doctor profiles
    mock_patients_table = MagicMock()
    mock_patients_table.get_item.return_value = {"Item": mock_patient_profile}
    mocker.patch("backend.app.crud.patients_table", mock_patients_table)

    mock_doctors_table = MagicMock()
    mocker.patch("backend.app.crud.doctors_table", mock_doctors_table)

    # Act
    result = db_get_full_user_profile("patient123")

    # Assert
    assert result["first_name"] == "Pat"
    assert result["roles"] == ["PATIENT"]
    assert result["patient_profile"]["status"] == "ACTIVE"
    assert result["patient_profile"]["blood_type"] == "A+"
    assert result["doctor_profile"] is None
    mock_patients_table.get_item.assert_called_once_with(Key={'userId': "patient123"})
    # Ensure the doctors table was NOT called
    mock_doctors_table.get_item.assert_not_called()

def test_db_find_or_create_user_new_user(mocker):
    """
    Tests db_find_or_create_user_by_cognito_sub for a brand new user.
    """
    # Arrange
    cognito_sub = "new-user-sub"
    phone = "+15555551234"
    email = "new@example.com"
    app_type = "PATIENT"

    # Mock the internal call to check if the user exists. Return None.
    mocker.patch("backend.app.crud.db_get_user_by_cognito_sub", return_value=None)
    
    # Mock the table write operations
    mock_users_table = MagicMock()
    mock_patients_table = MagicMock()
    mocker.patch("backend.app.crud.users_table", mock_users_table)
    mocker.patch("backend.app.crud.patients_table", mock_patients_table)

    # Act
    result = db_find_or_create_user_by_cognito_sub(cognito_sub, phone, email, app_type)

    # Assert
    # Check that a new user was created in the Users table
    mock_users_table.put_item.assert_called_once()
    # Check that a new patient profile was created in the Patients table
    mock_patients_table.put_item.assert_called_once()

    # Verify the returned user object has the correct details
    assert result["cognitoSub"] == cognito_sub
    assert result["roles"] == ["PATIENT"]

def test_db_update_user_profile(mocker):
    """
    Tests db_update_user_profile for updating a patient's profile.
    """
    # Arrange
    user_id = "user-to-update"
    profile_data = ProfileData(
        first_name="UpdatedFirst",
        last_name="UpdatedLast",
        date_of_birth="2000-01-01"
    )

    # Mock the internal check for the user's roles
    mocker.patch("backend.app.crud.db_get_user_by_id", return_value={"roles": ["PATIENT"]})
    # Mock the final call to get the updated profile
    mocker.patch("backend.app.crud.db_get_full_user_profile", return_value={"status": "ok"})
    
    # Mock the tables that will be updated
    mock_users_table = MagicMock()
    mock_patients_table = MagicMock()
    mocker.patch("backend.app.crud.users_table", mock_users_table)
    mocker.patch("backend.app.crud.patients_table", mock_patients_table)

    # Act
    db_update_user_profile(user_id, profile_data)

    # Assert
    # Verify that the Users table was updated with the correct data
    mock_users_table.update_item.assert_called_once()
    # Verify that the Patients table was updated with the correct data
    mock_patients_table.update_item.assert_called_once()
