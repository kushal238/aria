# app/models.py
#
# This module contains all Pydantic models used for data validation,
# serialization, and API request/response schemas.

from typing import Optional, List
from pydantic import BaseModel, Field

class PatientProfile(BaseModel):
    status: str
    date_of_birth: Optional[str] = None
    sex_assigned_at_birth: Optional[str] = None
    gender_identity: Optional[str] = None
    blood_type: Optional[str] = None
    # Add other patient-specific fields here from the Patients table

class MedicationItem(BaseModel):
    # SNOMED CT Coding Information
    system: str = Field("http://snomed.info/sct", alias="system")
    # Allow optional for free-text entries; server normalizes to UNMAPPED
    code: Optional[str] = Field(default=None, alias="code")
    display: Optional[str] = Field(default=None, alias="display")
    
    # Original doctor input for reference and fallback
    original_input: Optional[str] = None
    
    # Structured dosage information
    # Optional free-text name captured from UI; server may use it as fallback
    name: Optional[str] = None
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

class CognitoToken(BaseModel):
    # Flutter will send the Cognito ID token after successful login
    idToken: str # Keep alias consistent if Flutter sends 'idToken'
