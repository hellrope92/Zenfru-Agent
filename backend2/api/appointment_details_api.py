import requests
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from services.local_cache_service import LocalCacheService
from services.auth_service import require_api_key
import json

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
    phone: str

@router.post("/get_appointment_details")
async def get_appointment_details(request: AppointmentDetailsRequest, authenticated: bool = Depends(require_api_key)):
    """
    Get detailed appointment information for a patient using phone number
    Parameters: phone (required) - Patient's phone number for identification
    """
    try:
        # Fetching appointment details for patient by phone
         
        # Normalize phone number (remove spaces, dashes, etc.)
        normalized_phone = ''.join(filter(str.isdigit, request.phone))
        
        # First check local cache for appointments by phone
        cached_appointment = cache_service.get_appointments_by_phone(normalized_phone)
        
        if cached_appointment:
            return {
                "success": True,
                "patient_phone": request.phone,
                "appointment_details": cached_appointment,
                "source": "cache",
                "message": "Appointment details retrieved from cache"
            }
        
        # If not in cache, fetch from Kolla API using phone number
        try:
            # Search for patient by phone number first
            patient_search_url = f"{KOLLA_BASE_URL}/patients/search"
            search_params = {
                "phone": normalized_phone,
                "limit": 1
            }
            
            patient_response = requests.get(
                patient_search_url,
                headers=KOLLA_HEADERS,
                params=search_params,
                timeout=10
            )
            
            if patient_response.status_code == 200:
                patient_data = patient_response.json()
                
                if patient_data.get("patients") and len(patient_data["patients"]) > 0:
                    patient = patient_data["patients"][0]
                    patient_id = patient.get("id")
                    
                    # Now fetch appointments for this patient
                    appointments_url = f"{KOLLA_BASE_URL}/appointments"
                    appointments_params = {
                        "patient_id": patient_id,
                        "status": "confirmed,scheduled",
                        "limit": 10
                    }
                    
                    appointments_response = requests.get(
                        appointments_url,
                        headers=KOLLA_HEADERS,
                        params=appointments_params,
                        timeout=10
                    )
                    
                    if appointments_response.status_code == 200:
                        appointments_data = appointments_response.json()
                        appointments = appointments_data.get("appointments", [])
                        
                        for appointment in appointments:
                            cache_service.store_appointment(appointment)
                        
                        return {
                            "success": True,
                            "patient_phone": request.phone,
                            "patient_details": patient,
                            "appointment_details": appointments,
                            "source": "api",
                            "message": f"Found {len(appointments)} appointment(s) for patient"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Error fetching appointments: {appointments_response.status_code}",
                            "patient_phone": request.phone,
                            "appointment_details": None
                        }
                else:
                    return {
                        "success": False,
                        "message": "No patient found with the provided phone number",
                        "patient_phone": request.phone,
                        "appointment_details": None
                    }
            else:
                return {
                    "success": False,
                    "message": f"Error searching for patient: {patient_response.status_code}",
                    "patient_phone": request.phone,
                    "appointment_details": None
                }
                
        except requests.RequestException:
            raise HTTPException(status_code=503, detail="Unable to connect to appointment system")
        
    except Exception:
        raise HTTPException(status_code=500, detail="Error retrieving appointment details")

# Endpoints removed as requested
