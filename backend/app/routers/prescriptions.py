# app/routers/prescriptions.py
#
# This router handles all endpoints related to medical prescriptions, including
# creating, listing, and managing them.

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
import boto3

from ..models import PrescriptionResponse, PrescriptionCreate
from ..crud import db_get_full_user_profile, db_get_user_by_id
from ..security import verify_api_token
from ..database import prescriptions_table

router = APIRouter()


@router.post("/prescriptions", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED, tags=["Prescriptions"])
async def create_prescription(
    prescription_data: PrescriptionCreate,
    token_payload: Dict[str, Any] = Depends(verify_api_token)
):
    """
    Creates a new prescription. Doctor-only endpoint.
    """
    doctor_id = token_payload.get("sub")
    user = db_get_full_user_profile(doctor_id)

    if not user or 'DOCTOR' not in user.get('roles', []):
        raise HTTPException(status_code=403, detail="User is not authorized to create prescriptions.")
    
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
        return PrescriptionResponse(**new_prescription)
    except Exception as e:
        print(f"Error creating prescription: {e}")
        raise HTTPException(status_code=500, detail="Could not create prescription.")


@router.get("/prescriptions", response_model=List[PrescriptionResponse], tags=["Prescriptions"])
async def list_prescriptions(token_payload: Dict[str, Any] = Depends(verify_api_token)):
    """
    Lists prescriptions for the logged-in user.
    """
    user_id = token_payload.get("sub")
    user = db_get_full_user_profile(user_id)
    roles = user.get('roles', [])
    
    try:
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

        # This is an edge case but good practice
        unique_prescriptions = {p['prescriptionId']: p for p in all_prescriptions}.values()

        print(f"LIST PRESCRIPTIONS: Raw DynamoDB query response: {list(unique_prescriptions)}")

        # Enrich prescriptions with patient/doctor names
        enriched_prescriptions = []
        for item in unique_prescriptions:
            # Always enrich with patient info
            patient_id = item.get('patientId')
            if patient_id:
                patient_user = db_get_user_by_id(patient_id)
                if patient_user:
                    item['patientFirstName'] = patient_user.get('firstName')
                    item['patientLastName'] = patient_user.get('lastName')
            
            # Always enrich with doctor info
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


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionResponse, tags=["Prescriptions"])
async def get_prescription(prescription_id: str, token_payload: Dict[str, Any] = Depends(verify_api_token)):
    """
    Retrieves a single prescription by its ID.
    """
    user_id = token_payload.get("sub")
    
    try:
        response = prescriptions_table.get_item(Key={'prescriptionId': prescription_id})
        prescription = response.get('Item')
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found.")
            
        if prescription.get('patientId') != user_id and prescription.get('doctorId') != user_id:
            raise HTTPException(status_code=403, detail="You are not authorized to view this prescription.")
            
        return PrescriptionResponse(**prescription)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not retrieve prescription.")


@router.put("/prescriptions/{prescription_id}/cancel", response_model=PrescriptionResponse, tags=["Prescriptions"])
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
        
        if prescription.get('doctorId') != doctor_id:
            raise HTTPException(status_code=403, detail="Only the issuing doctor can cancel this prescription.")
        if prescription.get('status') != 'ACTIVE':
            raise HTTPException(status_code=400, detail=f"Prescription is already in '{prescription.get('status')}' state.")

        updated_response = prescriptions_table.update_item(
            Key={'prescriptionId': prescription_id},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': 'CANCELLED'},
            ReturnValues="ALL_NEW"
        )
        
        return PrescriptionResponse(**updated_response.get('Attributes', {}))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not cancel prescription.")
