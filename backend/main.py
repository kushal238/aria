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
        # For now, we'll exit to prevent the app from running in an insecure state.
        exit(1)

# Load secrets securely
API_JWT_SECRET = get_api_jwt_secret()

JWT_ALGORITHM = "HS256"
API_TOKEN_EXPIRY_MINUTES = 60 # e.g., 1 hour for final token

# --- DynamoDB Configuration ---
USERS_TABLE_NAME = os.getenv("USERS_TABLE_NAME", "Users")
PATIENTS_TABLE_NAME = os.getenv("PATIENTS_TABLE_NAME", "Patients")
DOCTORS_TABLE_NAME = os.getenv("DOCTORS_TABLE_NAME", "Doctors")
PRESCRIPTIONS_TABLE_NAME = os.getenv("PRESCRIPTIONS_TABLE_NAME", "Prescriptions")

dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table(USERS_TABLE_NAME)
patients_table = dynamodb.Table(PATIENTS_TABLE_NAME)
doctors_table = dynamodb.Table(DOCTORS_TABLE_NAME)
prescriptions_table = dynamodb.Table(PRESCRIPTIONS_TABLE_NAME)


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
class PatientProfile(BaseModel):
    status: str
    date_of_birth: Optional[str] = None
    sex_assigned_at_birth: Optional[str] = None
    gender_identity: Optional[str] = None
    blood_type: Optional[str] = None
    # Add other patient-specific fields here from the Patients table

class MedicationItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = None

class PrescriptionBase(BaseModel):
    patientId: str
    expiresAt: str
    diagnosis: Optional[str] = None
    medications: List[MedicationItem]

class PrescriptionCreate(PrescriptionBase):
    pass

class PrescriptionResponse(PrescriptionBase):
    prescriptionId: str
    doctorId: str
    createdAt: str
    status: str
    # Add fields for patient's name for easier display on the frontend
    patientFirstName: Optional[str] = None
    patientLastName: Optional[str] = None
    # Add fields for doctor's name for the patient's view
    doctorFirstName: Optional[str] = None
    doctorLastName: Optional[str] = None

class DoctorProfile(BaseModel):
    status: str
    license_number: Optional[str] = None
    specialization: Optional[str] = None
    qualifications: Optional[List[str]] = None
    clinic_address: Optional[str] = None
    # Add other doctor-specific fields here from the Doctors table

class UserResponse(BaseModel): # The new top-level response model
    internal_user_id: str
    cognito_sub: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    roles: List[str]
    patient_profile: Optional[PatientProfile] = None
    doctor_profile: Optional[DoctorProfile] = None

class ProfileData(BaseModel):
    # Fields for the Users table (all optional for partial updates)
    first_name: Optional[str] = None
    middle_name: Optional[str] = None 
    last_name: Optional[str] = None
    email: Optional[str] = None
    abha_id: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Fields for the Patients table
    date_of_birth: Optional[str] = None # E.g., "YYYY-MM-DD"
    sex_assigned_at_birth: Optional[str] = None # E.g., "MALE", "FEMALE"
    gender_identity: Optional[str] = None # E.g., "MAN", "WOMAN", "NON_BINARY"
    blood_type: Optional[str] = None # E.g., "A+", "O-"

    # --- Doctor-Specific Fields ---
    license_number: Optional[str] = None
    specialization: Optional[str] = None
    qualifications: Optional[List[str]] = None
    clinic_address: Optional[str] = None

class LoginResponse(BaseModel): # Response model for successful login
    message: str
    api_token: str # The backend's own session token
    user_profile: UserResponse


# --- Database Placeholder Functions (Rewritten for DynamoDB) ---

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
class CognitoToken(BaseModel):
    # Flutter will send the Cognito ID token after successful login
    idToken: str # Keep alias consistent if Flutter sends 'idToken'

# --- API Endpoints ---

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
    