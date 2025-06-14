"""
Get Appointment API endpoint
Retrieves existing appointment information for a patient
Parameters: phone (required)
Used for rescheduling and confirming appointments
Uses local caching with 24-hour refresh for appointments

Note: Matching is performed by patient phone number for accurate identification.
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
    Parameters: phone (required)
    Used for rescheduling and confirming appointments
    Note: Matching is performed by phone number for accurate patient identification.
    """
    try:
        # Print phone number as requested
        print(f"Fetching appointments for patient phone: {request.phone}")
        
        # Normalize phone number (remove spaces, dashes, etc.)
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            
        # First check local cache (using phone number for matching)
        cached_appointments = cache_service.get_appointments_by_phone(normalized_phone)
        
        if cached_appointments:
            # Sort cached appointments by start_time to get the latest
            sorted_appointments = sorted(cached_appointments, key=lambda x: x.get("start_time", ""), reverse=True)
            latest_appointment = sorted_appointments[0] if sorted_appointments else None
            
            return {
                "success": True,
                "patient_phone": request.phone,
                "appointment": latest_appointment,
                "source": "cache"
            }
            
        # If not in cache or cache is stale, fetch from Kolla API
        appointments = await fetch_appointments_from_kolla(normalized_phone)
        
        if appointments:
            # Store in cache
            for appointment in appointments:
                appointment["patient_phone"] = normalized_phone
                cache_service.store_appointment(appointment)
            
            # Get the latest appointment (first one since they're sorted by start_time desc)
            latest_appointment = appointments[0] if appointments else None
            
            return {
                "success": True,
                "patient_phone": request.phone,
                "appointment": latest_appointment,
                "source": "api"
            }
        else:
            return {
                "success": False,
                "message": "No appointments found for the specified patient",
                "patient_phone": request.phone,
                "appointment": None
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving appointments: {str(e)}")

async def fetch_appointments_from_kolla(patient_phone: str) -> List[Dict[str, Any]]:
    """
    Fetch appointments from Kolla API for a specific patient using phone number
    
    First searches for contact by phone number, then fetches their appointments using contact_id.
    """
    try:
        # Step 1: Search for contacts (patients) by phone number first
        contacts_search_url = f"{KOLLA_BASE_URL}/contacts"
        
        contacts_response = requests.get(
            contacts_search_url,
            headers=KOLLA_HEADERS,
            timeout=10
        )
        
        if contacts_response.status_code != 200:
            print(f"Error searching for contacts: {contacts_response.status_code}")
            return []
            
        contacts_data = contacts_response.json()
        
        # Step 2: Find contact with matching phone number
        matching_contact = None
        for contact in contacts_data.get("contacts", []):
            if contact.get("type") == "PATIENT":
                # Check all phone numbers for this contact
                phone_numbers = contact.get("phone_numbers", [])
                primary_phone = contact.get("primary_phone_number", "")
                
                # Normalize phone numbers for comparison
                contact_phones = [phone.get("number", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "") 
                                for phone in phone_numbers]
                normalized_primary = primary_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                
                if patient_phone in contact_phones or patient_phone == normalized_primary:
                    matching_contact = contact
                    break
        
        if not matching_contact:
            print(f"No patient found with phone number: {patient_phone}")
            return []
            
        # Step 3: Get contact_id from the matching contact
        contact_remote_id = matching_contact.get("remote_id")  # This is the contact_id we need
        contact_name = matching_contact.get("name")  # This is like "contacts/13"
        
        if not contact_remote_id and not contact_name:
            print("Contact ID not found in response")
            return []
            
        print(f"Found matching contact: {contact_name} with remote_id: {contact_remote_id}")
        
        # Step 4: Fetch all appointments and filter by contact_id
        appointments_url = f"{KOLLA_BASE_URL}/appointments"
        
        appointments_response = requests.get(
            appointments_url,
            headers=KOLLA_HEADERS,
            timeout=10
        )
        
        if appointments_response.status_code != 200:
            print(f"Error fetching appointments: {appointments_response.status_code}")
            return []
            
        appointments_data = appointments_response.json()
        all_appointments = appointments_data.get("appointments", [])
        
        # Step 5: Filter appointments by contact_id and get the latest ones
        patient_appointments = []
        for appointment in all_appointments:
            appointment_contact_id = appointment.get("contact_id")
            
            # Match either by contact name or remote_id
            if (appointment_contact_id == contact_name or 
                appointment_contact_id == f"contacts/{contact_remote_id}"):
                patient_appointments.append(appointment)
        
        if not patient_appointments:
            print(f"No appointments found for contact_id: {contact_name}")
            return []
        
        # Step 6: Sort appointments by start_time to get the latest ones first
        patient_appointments.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        
        # Step 7: Enrich appointment data
        enriched_appointments = []
        for appointment in patient_appointments:
            enriched_appointment = {
                **appointment,
                "patient_matched": True,
                "search_phone": patient_phone,
                "patient_details": matching_contact,
                "appointment_date": appointment.get("start_time", "").split("T")[0] if appointment.get("start_time") else None,
                "appointment_time": appointment.get("start_time", "").split("T")[1] if appointment.get("start_time") else None,
                "wall_date": appointment.get("wall_start_time", "").split(" ")[0] if appointment.get("wall_start_time") else None,
                "wall_time": appointment.get("wall_start_time", "").split(" ")[1] if appointment.get("wall_start_time") else None,
                "status": "confirmed" if appointment.get("confirmed") else "unconfirmed",
                "cancelled": appointment.get("cancelled", False),
                "completed": appointment.get("completed", False),
                "duration_minutes": calculate_duration(appointment.get("start_time"), appointment.get("end_time")),
                "provider": appointment.get("providers", [{}])[0].get("display_name", "") if appointment.get("providers") else "",
                "operatory": appointment.get("resources", [{}])[0].get("display_name", "") if appointment.get("resources") else "",
                "notes": appointment.get("notes", ""),
                "short_description": appointment.get("short_description", "")
            }
            
            enriched_appointments.append(enriched_appointment)
        
        print(f"Found {len(enriched_appointments)} appointments for patient")
        return enriched_appointments
        
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return []
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

@router.get("/get_appointment_by_phone/{patient_phone}")
async def get_appointment_by_phone_only(patient_phone: str):
    """
    GET endpoint for retrieving appointments by phone number only
    URL format: /api/get_appointment_by_phone/{patient_phone}
    """
    request = GetAppointmentRequest(phone=patient_phone)
    return await get_appointment(request)

@router.post("/get_appointment/refresh")
async def refresh_appointments_cache(request: GetAppointmentRequest):
    """Manually refresh the appointments cache for a specific patient"""
    try:
        # Normalize phone number
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Force fetch from API
        appointments = await fetch_appointments_from_kolla(normalized_phone)
        
        # Update cache
        if appointments:
            for appointment in appointments:
                cache_service.store_appointment(appointment)
        
        return {
            "success": True,
            "message": "Appointments cache refreshed",
            "patient_phone": request.phone,
            "appointments_found": len(appointments),
            "appointments": appointments
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing appointments cache: {str(e)}")

@router.get("/appointments/search")
async def search_appointments(
    phone: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Search appointments with flexible parameters
    """
    try:
        if phone:
            # Use the main get_appointment function
            request = GetAppointmentRequest(phone=phone)
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
                "phone": phone,
                "start_date": start_date,
                "end_date": end_date
            },
            "appointments": all_appointments.get("appointments", []),
            "total_appointments": len(all_appointments.get("appointments", []))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching appointments: {str(e)}")
