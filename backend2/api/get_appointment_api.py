"""
Get Appointment API endpoint
Retrieves existing appointment information for a patient
Parameters: name (required), dob (optional)
Used for rescheduling and confirming appointments
Uses local caching with 24-hour refresh for appointments

Note: Matching is performed by patient name only since the Kolla API 
appointment structure doesn't include DOB information.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException

from api.models import GetAppointmentRequest
from services.local_cache_service import LocalCacheService
from services.getkolla_service import GetKollaService

router = APIRouter(prefix="/api", tags=["appointments"])

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

cache_service = LocalCacheService()

@router.post("/get_appointment")
async def get_appointment(request: GetAppointmentRequest):
    """
    Retrieves existing appointment information for a patient
    Parameters: name (required), dob (optional)
    Used for rescheduling and confirming appointments
      Note: Matching is performed by name only since DOB is not available in the API response.
    """
    try:
        # Print DOB if provided (as requested)
        if request.dob:
            print(f"Fetching appointments for patient DOB: {request.dob}")
            
        # First check local cache (using name only for matching)
        cached_appointments = cache_service.get_appointments_by_patient(request.name, request.dob or "")
        
        if cached_appointments:
            return {
                "success": True,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "appointments": cached_appointments,
                "total_appointments": len(cached_appointments),
                "source": "cache"
            }
          # If not in cache or cache is stale, fetch from Kolla API
        appointments = await fetch_appointments_from_kolla(request.name, request.dob or "")
        
        if appointments:
            # Store in cache
            for appointment in appointments:
                appointment_id = appointment.get("id", f"apt_{request.name}_{request.dob or 'unknown'}_{datetime.now().timestamp()}")
                cache_service.store_appointment(appointment_id, request.name, request.dob or "", appointment)
            
            return {
                "success": True,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "appointments": appointments,
                "total_appointments": len(appointments),
                "source": "api"
            }
        else:
            return {
                "success": False,
                "message": "No appointments found for the specified patient",
                "patient_name": request.name,
                "patient_dob": request.dob,
                "appointments": [],
                "total_appointments": 0
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving appointments: {str(e)}")

async def fetch_appointments_from_kolla(patient_name: str, patient_dob: str = "") -> List[Dict[str, Any]]:
    """
    Fetch appointments from Kolla API for a specific patient
    
    Matches appointments by patient name only since DOB is not available in the API response.
    """
    try:
        getkolla_service = GetKollaService()
        
        # Search for appointments in the next 60 days and past 30 days
        today = datetime.now()
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")        # Get all appointments in the date range
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        appointments_list = getkolla_service.get_booked_appointments(start_dt, end_dt)
        
        if not appointments_list:
            return []        # Filter appointments by patient name
        patient_appointments = []
        
        for appointment in appointments_list:
            # Extract patient information from contact field (based on actual API structure)
            contact_info = appointment.get("contact", {})
            
            # Build patient name from contact information
            given_name = contact_info.get("given_name", "").strip()
            family_name = contact_info.get("family_name", "").strip()
            contact_name = contact_info.get("name", "").strip()
            
            # Try different name combinations
            if contact_name:
                apt_patient_name = contact_name
            elif given_name and family_name:
                apt_patient_name = f"{given_name} {family_name}"
            elif given_name:
                apt_patient_name = given_name
            else:
                apt_patient_name = ""
            
            # Normalize names for comparison (case-insensitive, remove extra spaces)
            if (apt_patient_name and 
                apt_patient_name.lower().replace(" ", "") == patient_name.lower().replace(" ", "")):                # Enrich appointment data
                enriched_appointment = {
                    **appointment,
                    "patient_matched": True,
                    "search_name": patient_name,
                    "search_dob": patient_dob,
                    "matched_contact_name": apt_patient_name,
                    "appointment_date": appointment.get("start_time", "").split("T")[0] if appointment.get("start_time") else None,
                    "appointment_time": appointment.get("start_time", "").split("T")[1] if appointment.get("start_time") else None,
                    "status": "confirmed" if appointment.get("confirmed") else "unconfirmed",
                    "cancelled": appointment.get("cancelled", False),
                    "completed": appointment.get("completed", False),
                    "duration_minutes": calculate_duration(appointment.get("start_time"), appointment.get("end_time")),
                    "provider": appointment.get("providers", [{}])[0].get("display_name", "") if appointment.get("providers") else "",
                    "operatory": appointment.get("resources", [{}])[0].get("display_name", "") if appointment.get("resources") else "",
                    "notes": appointment.get("notes", "")
                }
                
                patient_appointments.append(enriched_appointment)
        
        return patient_appointments
        
    except Exception as e:
        print(f"Error fetching appointments from Kolla: {e}")
        return []

def calculate_duration(start_time: str, end_time: str) -> Optional[int]:
    """Calculate appointment duration in minutes"""
    try:
        if start_time and end_time:
            start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            return int((end - start).total_seconds() / 60)
    except:
        pass
    return None

@router.get("/get_appointment/{patient_name}/{patient_dob}")
async def get_appointment_by_url(patient_name: str, patient_dob: str = ""):
    """
    Alternative GET endpoint for retrieving appointments
    URL format: /api/get_appointment/{patient_name}/{patient_dob}
    Note: patient_dob is optional and not used for matching
    """
    request = GetAppointmentRequest(name=patient_name, dob=patient_dob if patient_dob else None)
    return await get_appointment(request)

@router.get("/get_appointment/{patient_name}")
async def get_appointment_by_name_only(patient_name: str):
    """
    GET endpoint for retrieving appointments by name only
    URL format: /api/get_appointment/{patient_name}
    """
    request = GetAppointmentRequest(name=patient_name)
    return await get_appointment(request)

@router.post("/get_appointment/refresh")
async def refresh_appointments_cache(request: GetAppointmentRequest):
    """Manually refresh the appointments cache for a specific patient"""
    try:
        # Force fetch from API
        appointments = await fetch_appointments_from_kolla(request.name, request.dob or "")
        
        # Update cache
        if appointments:
            for appointment in appointments:
                appointment_id = appointment.get("id", f"apt_{request.name}_{request.dob or 'unknown'}_{datetime.now().timestamp()}")
                cache_service.store_appointment(appointment_id, request.name, request.dob or "", appointment)
        
        return {
            "success": True,
            "message": "Appointments cache refreshed",
            "patient_name": request.name,
            "patient_dob": request.dob,
            "appointments_found": len(appointments),
            "appointments": appointments
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing appointments cache: {str(e)}")

@router.get("/appointments/search")
async def search_appointments(
    name: Optional[str] = None,
    dob: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Search appointments with flexible parameters
    """
    try:
        if name and dob:
            # Use the main get_appointment function
            request = GetAppointmentRequest(name=name, dob=dob)
            return await get_appointment(request)
        
        # For other search criteria, fetch from API
        getkolla_service = GetKollaService()
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        all_appointments = getkolla_service.get_appointments(start_date, end_date)
        
        return {
            "success": True,
            "search_criteria": {
                "name": name,
                "dob": dob,
                "start_date": start_date,
                "end_date": end_date
            },
            "appointments": all_appointments.get("appointments", []),
            "total_appointments": len(all_appointments.get("appointments", []))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching appointments: {str(e)}")
