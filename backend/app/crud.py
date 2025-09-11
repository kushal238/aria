# app/crud.py
#
# This module contains all the functions for Create, Read, Update, and Delete
# (CRUD) operations, interacting directly with the database.

from typing import Optional, Dict, Any
from .database import users_table, patients_table, doctors_table
import boto3
import uuid
from datetime import datetime, timezone
from .models import ProfileData

def db_get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Finds a user by their internal userId (Primary Key)."""
    print(f"DB Read: Searching for user with internal ID: {user_id}")
    response = users_table.get_item(Key={'userId': user_id})
    item = response.get('Item')
    if item:
        print(f"DB Read: Found user for ID: {user_id}")
        return item
    print(f"DB Read: User not found for ID: {user_id}")
    return None

def db_get_user_by_cognito_sub(cognito_sub: str) -> Optional[Dict[str, Any]]:
    """Finds a user by their Cognito Sub ID using the GSI."""
    print(f"DB Read: Searching for user with Cognito SUB: {cognito_sub} in GSI 'Index-cognitoSub'")
    response = users_table.query(
        IndexName='Index-cognitoSub',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('cognitoSub').eq(cognito_sub)
    )
    items = response.get('Items', [])
    if items:
        print(f"DB Read: Found user for Cognito SUB: {cognito_sub}")
        return items[0]
    print(f"DB Read: User not found for Cognito SUB: {cognito_sub}")
    return None

def db_get_full_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the complete user profile and structures it into a nested object
    with role-specific profiles.
    """
    print(f"DB Read: Fetching full profile for user ID: {user_id}")
    user_core_profile = db_get_user_by_id(user_id)
    if not user_core_profile:
        return None

    # This will be the final structured response
    full_profile = {
        'internal_user_id': user_core_profile.get('userId'),
        'cognito_sub': user_core_profile.get('cognitoSub'),
        'phone_number': user_core_profile.get('phoneNumber'),
        'first_name': user_core_profile.get('firstName'),
        'last_name': user_core_profile.get('lastName'),
        'email': user_core_profile.get('email'),
        'roles': user_core_profile.get('roles', []),
        'patient_profile': None,
        'doctor_profile': None
    }

    # If the user has a patient role, fetch and nest their patient profile data
    if 'PATIENT' in full_profile['roles']:
        patient_data = patients_table.get_item(Key={'userId': user_id}).get('Item', {})
        if patient_data:
            full_profile['patient_profile'] = {
                'status': patient_data.get('status', 'PROFILE_INCOMPLETE'),
                'date_of_birth': patient_data.get('dateOfBirth'),
                'sex_assigned_at_birth': patient_data.get('sexAssignedAtBirth'),
                'gender_identity': patient_data.get('genderIdentity'),
                'blood_type': patient_data.get('bloodType')
            }

    # If the user has a doctor role, fetch and nest their doctor profile data
    if 'DOCTOR' in full_profile['roles']:
        doctor_data = doctors_table.get_item(Key={'userId': user_id}).get('Item', {})
        if doctor_data:
            full_profile['doctor_profile'] = {
                'status': doctor_data.get('status', 'PROFILE_INCOMPLETE'),
                'license_number': doctor_data.get('licenseNumber'),
                'specialization': doctor_data.get('specialization'),
                'qualifications': doctor_data.get('qualifications'),
                'clinic_address': doctor_data.get('clinicAddress')
            }

    return full_profile

def db_find_or_create_user_by_cognito_sub(cognito_sub: str, phone: Optional[str], email: Optional[str], app_type: str) -> Dict[str, Any]:
    """
    Finds a user by Cognito Sub. If they exist, appends the new role if necessary.
    If they don't exist, creates them with the role from the app_type.
    Also creates corresponding profiles in Patients/Doctors tables.
    """
    user = db_get_user_by_cognito_sub(cognito_sub)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if user:
        # User exists, check if we need to add a new role
        print(f"DB Check: User with ID {user.get('userId')} already exists.")
        user_id = user['userId']
        
        if app_type not in user.get('roles', []):
            print(f"DB Write: Adding role '{app_type}' to user {user_id}")
            user['roles'].append(app_type)
            users_table.update_item(
                Key={'userId': user_id},
                UpdateExpression="SET #r = :r, updatedAt = :ua",
                ExpressionAttributeNames={'#r': 'roles'},
                ExpressionAttributeValues={':r': user['roles'], ':ua': timestamp}
            )

            # Create the corresponding profile table with an INCOMPLETE status
            if app_type == 'PATIENT':
                patients_table.put_item(
                    Item={'userId': user_id, 'createdAt': timestamp, 'updatedAt': timestamp, 'status': 'PROFILE_INCOMPLETE'},
                    ConditionExpression="attribute_not_exists(userId)"
                )
                print(f"DB Write: Created patient profile for existing user {user_id}")
            elif app_type == 'DOCTOR':
                doctors_table.put_item(
                    Item={'userId': user_id, 'createdAt': timestamp, 'updatedAt': timestamp, 'status': 'PROFILE_INCOMPLETE'},
                    ConditionExpression="attribute_not_exists(userId)"
                )
                print(f"DB Write: Created doctor profile for existing user {user_id}")
        
        return user

    else:
        # New user, create everything from scratch
        user_id = str(uuid.uuid4())
        
        # Create the main user record (without a status)
        new_user = {
            'userId': user_id,
            'cognitoSub': cognito_sub,
            'phoneNumber': phone,
            'email': email,
            'createdAt': timestamp,
            'updatedAt': timestamp,
            'roles': [app_type],
            'firstName': None,
            'middleName': None,
            'lastName': None,
            'abhaId': None,
        }
        users_table.put_item(Item=new_user)
        print(f"DB Write: Created user with ID {user_id} and role {app_type} for Cognito Sub: {cognito_sub}")

        # Create the corresponding profile record with an INCOMPLETE status
        if app_type == 'PATIENT':
            new_profile = {'userId': user_id, 'createdAt': timestamp, 'updatedAt': timestamp, 'status': 'PROFILE_INCOMPLETE'}
            patients_table.put_item(Item=new_profile)
            print(f"DB Write: Created patient profile for new user {user_id}")
        elif app_type == 'DOCTOR':
            new_profile = {'userId': user_id, 'createdAt': timestamp, 'updatedAt': timestamp, 'status': 'PROFILE_INCOMPLETE'}
            doctors_table.put_item(Item=new_profile)
            print(f"DB Write: Created doctor profile for new user {user_id}")

        return new_user

def db_update_user_profile(user_id: str, profile: ProfileData) -> Optional[Dict[str, Any]]:
    """
    Updates user profile data across the Users table and the relevant role-specific
    table (Patients or Doctors) based on the user's roles and provided fields.
    Only updates fields that are provided (not None).
    Returns the combined, updated user profile.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # First, get the user's current roles from the DB
    user = db_get_user_by_id(user_id)
    if not user:
        print(f"DB Update Error: User {user_id} not found.")
        return None
    user_roles = user.get('roles', [])

    # 1. Update the Users table (common data) - only if fields are provided
    # ---------------------------------------------------------------------
    user_updates = []
    user_expression_values = {':ua': timestamp}
    user_expression_names = {}

    if profile.first_name is not None:
        user_updates.append("firstName = :fn")
        user_expression_values[':fn'] = profile.first_name
    if profile.middle_name is not None:
        user_updates.append("middleName = :mn")
        user_expression_values[':mn'] = profile.middle_name
    if profile.last_name is not None:
        user_updates.append("lastName = :ln")
        user_expression_values[':ln'] = profile.last_name
    if profile.email is not None:
        user_updates.append("email = :e")
        user_expression_values[':e'] = profile.email
    if profile.abha_id is not None:
        user_updates.append("abhaId = :a")
        user_expression_values[':a'] = profile.abha_id
    if profile.phone_number is not None:
        user_updates.append("phoneNumber = :pn")
        user_expression_values[':pn'] = profile.phone_number

    if user_updates:  # Only update if there are fields to update
        user_update_expression = "SET " + ", ".join(user_updates) + ", updatedAt = :ua"
        
        update_args = {
            'Key': {'userId': user_id},
            'UpdateExpression': user_update_expression,
            'ExpressionAttributeValues': user_expression_values,
            'ReturnValues': "NONE"
        }
        if user_expression_names:
            update_args['ExpressionAttributeNames'] = user_expression_names

        try:
            print(f"DB Write: Updated Users table for user ID: {user_id}")
            users_table.update_item(**update_args)
        except Exception as e:
            print(f"DB Update Error (Users table) for user ID {user_id}: {e}")
            return None 

    # 2. Update the Patients table (if the user has the PATIENT role and patient fields are provided)
    # -----------------------------------------------------------------------------------------------
    if 'PATIENT' in user_roles:
        patient_updates = []
        patient_expression_values = {':ua': timestamp, ':st': 'ACTIVE'}
        patient_expression_names = {'#s': 'status'}

        if profile.date_of_birth is not None:
            patient_updates.append("dateOfBirth = :dob")
            patient_expression_values[':dob'] = profile.date_of_birth
        if profile.sex_assigned_at_birth is not None:
            patient_updates.append("sexAssignedAtBirth = :sab")
            patient_expression_values[':sab'] = profile.sex_assigned_at_birth
        if profile.gender_identity is not None:
            patient_updates.append("genderIdentity = :gi")
            patient_expression_values[':gi'] = profile.gender_identity
        if profile.blood_type is not None:
            patient_updates.append("bloodType = :bt")
            patient_expression_values[':bt'] = profile.blood_type

        if patient_updates:  # Only update if there are patient fields to update
            patient_update_expression = "SET " + ", ".join(patient_updates) + ", updatedAt = :ua, #s = :st"
            
            update_args = {
                'Key': {'userId': user_id},
                'UpdateExpression': patient_update_expression,
                'ExpressionAttributeValues': patient_expression_values,
                'ExpressionAttributeNames': patient_expression_names,
                'ReturnValues': "NONE"
    }

    try:
        patients_table.update_item(**update_args)
        print(f"DB Write: Updated Patients table for user ID: {user_id}")
    except Exception as e:
        print(f"DB Update Error (Patients table) for user ID {user_id}: {e}")
        return None

    # 3. Update the Doctors table (if the user has the DOCTOR role and doctor fields are provided)
    # --------------------------------------------------------------------------------------------
    if 'DOCTOR' in user_roles:
        doctor_updates = []
        doctor_expression_values = {':ua': timestamp, ':st': 'ACTIVE'}
        doctor_expression_names = {'#s': 'status'}

        if profile.license_number is not None:
            doctor_updates.append("licenseNumber = :ln")
            doctor_expression_values[':ln'] = profile.license_number
        if profile.specialization is not None:
            doctor_updates.append("specialization = :sp")
            doctor_expression_values[':sp'] = profile.specialization
        if profile.qualifications is not None:
            doctor_updates.append("qualifications = :qu")
            doctor_expression_values[':qu'] = profile.qualifications
        if profile.clinic_address is not None:
            doctor_updates.append("clinicAddress = :ca")
            doctor_expression_values[':ca'] = profile.clinic_address

        if doctor_updates:  # Only update if there are doctor fields to update
            doctor_update_expression = "SET " + ", ".join(doctor_updates) + ", updatedAt = :ua, #s = :st"

            update_args = {
                'Key': {'userId': user_id},
                'UpdateExpression': doctor_update_expression,
                'ExpressionAttributeValues': doctor_expression_values,
                'ExpressionAttributeNames': doctor_expression_names,
                'ReturnValues': "NONE"
            }

            try:
                doctors_table.update_item(**update_args)
                print(f"DB Write: Updated Doctors table for user ID: {user_id}")
            except Exception as e:
                print(f"DB Update Error (Doctors table) for user ID {user_id}: {e}")
        return None
        
    # 4. Combine and return the results
    # ---------------------------------
    return db_get_full_user_profile(user_id)
