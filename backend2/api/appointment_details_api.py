import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.local_cache_service import LocalCacheService

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

router = APIRouter(prefix="/api", tags=["appointment-details"])
cache_service = LocalCacheService()

class AppointmentDetailsRequest(BaseModel):
    name: str
    dob: str

@router.post("/get_appointment_details")
async def get_appointment_details(request: AppointmentDetailsRequest):
    """
    Get detailed appointment information for a patient
    Parameters: name (required), dob (required)
    """
    try:
        # Print DOB as requested
        print(f"Fetching appointment details for patient DOB: {request.dob}")
        
        # First check local cache
        cached_appointment = cache_service.get_appointments_by_patient(request.name, request.dob)
        
        if cached_appointment:
            return {
                "success": True,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "appointment_details": cached_appointment,
                "source": "cache"
            }
        
        # If not in cache, this would fetch from Kolla API
        # For now, return a not found response
        return {
            "success": False,
            "message": "No appointment details found for the specified patient",
            "patient_name": request.name,
            "patient_dob": request.dob,
            "appointment_details": None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving appointment details: {str(e)}")

# Endpoints removed as requested
