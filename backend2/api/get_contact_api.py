"""
Get Contact API endpoint
Retrieves existing patient contact information
Parameters: name, dob
Used for booking appointments with existing patients
Uses local caching with 24-hour refresh for contacts
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException

from api.models import GetContactRequest
from services.local_cache_service import LocalCacheService
from services.getkolla_service import GetKollaService

router = APIRouter(prefix="/api", tags=["contacts"])

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

cache_service = LocalCacheService()

@router.post("/get_contact")
async def get_contact(request: GetContactRequest):
    """
    Retrieves existing patient contact information
    Parameters: name, dob
    Used for booking appointments with existing patients
    """
    try:        
        # Print DOB if provided (as requested)
        if request.dob:
            print(f"Fetching contact for patient DOB: {request.dob}")
            
        # First check local cache (handle case where dob might be None)
        cached_contact = cache_service.get_contact_by_patient(request.name, request.dob or "")
        
        if cached_contact:
            return {
                "success": True,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "contact_info": cached_contact,
                "source": "cache"
            }
          # If not in cache or cache is stale, fetch from Kolla API
        contact_info = await fetch_contact_from_kolla(request.name, request.dob or "")
        
        if contact_info:
            # Store in cache
            contact_id = contact_info.get("id", f"contact_{request.name}_{request.dob or 'unknown'}_{datetime.now().timestamp()}")
            cache_service.store_contact(contact_id, request.name, request.dob or "", contact_info)
            
            return {
                "success": True,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "contact_info": contact_info,
                "source": "api"
            }
        else:
            return {
                "success": False,
                "message": "No contact information found for the specified patient",
                "patient_name": request.name,
                "patient_dob": request.dob,
                "contact_info": None
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving contact information: {str(e)}")

async def fetch_contact_from_kolla(patient_name: str, patient_dob: str) -> Optional[Dict[str, Any]]:
    """Fetch contact information from Kolla API for a specific patient"""
    try:
        getkolla_service = GetKollaService()
        
        # First, try to find the patient through recent appointments
        today = datetime.now()
        start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")  # Look back 1 year
        end_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")    # Look ahead 60 days        # Get appointments to find patient contact info
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        appointments_list = getkolla_service.get_booked_appointments(start_dt, end_dt)
        
        if appointments_list:
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
                
                # Extract DOB if available (though usually not present in Kolla API)
                apt_patient_dob = contact_info.get("birth_date", "")
                
                # Match by name (and optionally DOB if provided)
                name_matches = (apt_patient_name and 
                               apt_patient_name.lower().replace(" ", "") == patient_name.lower().replace(" ", ""))
                
                dob_matches = True  # Default to True if no DOB filtering needed
                if patient_dob and apt_patient_dob:
                    dob_matches = apt_patient_dob == patient_dob
                
                if name_matches and dob_matches:
                    
                    # Extract and format contact information from the contact field
                    formatted_contact = {
                        "patient_id": contact_info.get("remote_id"),
                        "name": apt_patient_name,
                        "given_name": contact_info.get("given_name"),
                        "family_name": contact_info.get("family_name"),
                        "preferred_name": contact_info.get("preferred_name"),
                        "birth_date": apt_patient_dob,
                        "contact_id": appointment.get("contact_id"),
                        # Note: Most additional fields aren't available in basic contact info
                        # from the appointments API, but we include what we have
                        "appointment_info": {
                            "last_appointment_date": appointment.get("start_time", "").split("T")[0] if appointment.get("start_time") else None,
                            "last_appointment_type": appointment.get("short_description"),
                            "provider": appointment.get("providers", [{}])[0].get("display_name", "") if appointment.get("providers") else "",
                            "operatory": appointment.get("resources", [{}])[0].get("display_name", "") if appointment.get("resources") else ""
                        },
                        "source": "appointment_lookup"                    }
                    
                    return formatted_contact
        
        # If no contact found through appointments, try direct patient search
        # This would require a patient search endpoint if available
        contact_info = await search_patient_directly(patient_name, patient_dob)
        
        return contact_info
        
    except Exception as e:
        print(f"Error fetching contact from Kolla: {e}")
        return None

def extract_primary_email(patient_info: Dict[str, Any]) -> Optional[str]:
    """Extract primary email from patient info"""
    # Try various email field formats
    if patient_info.get("email"):
        return patient_info["email"]
    
    email_addresses = patient_info.get("email_addresses", [])
    if email_addresses:
        # Look for primary email
        for email in email_addresses:
            if email.get("is_primary") or email.get("type") == "primary":
                return email.get("email")
        # Return first email if no primary found
        return email_addresses[0].get("email")
    
    return None

def extract_primary_phone(patient_info: Dict[str, Any]) -> Optional[str]:
    """Extract primary phone from patient info"""
    # Try various phone field formats
    if patient_info.get("phone"):
        return patient_info["phone"]
    
    if patient_info.get("number"):
        return patient_info["number"]
    
    phone_numbers = patient_info.get("phone_numbers", [])
    if phone_numbers:
        # Look for primary phone
        for phone in phone_numbers:
            if phone.get("is_primary") or phone.get("type") == "primary":
                return phone.get("number")
        # Return first phone if no primary found
        return phone_numbers[0].get("number")
    
    return None

def extract_primary_address(patient_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract primary address from patient info"""
    addresses = patient_info.get("addresses", [])
    if addresses:
        # Look for primary address
        for address in addresses:
            if address.get("is_primary") or address.get("type") == "primary":
                return address
        # Return first address if no primary found
        return addresses[0]
    
    return None

def get_last_visit_date(appointment: Dict[str, Any]) -> Optional[str]:
    """Extract last visit date from appointment"""
    start_time = appointment.get("start_time")
    if start_time:
        try:
            return datetime.fromisoformat(start_time.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except:
            pass
    return None

async def search_patient_directly(patient_name: str, patient_dob: str) -> Optional[Dict[str, Any]]:
    """Direct patient search if available through Kolla API"""
    try:
        # This would use a direct patient search endpoint if available
        # For now, return None as we'll rely on appointment-based search
        return None
        
    except Exception as e:
        print(f"Error in direct patient search: {e}")
        return None

@router.get("/get_contact/{patient_name}/{patient_dob}")
async def get_contact_by_url(patient_name: str, patient_dob: str):
    """
    Alternative GET endpoint for retrieving contact information
    URL format: /api/get_contact/{patient_name}/{patient_dob}
    """
    request = GetContactRequest(name=patient_name, dob=patient_dob)
    return await get_contact(request)

@router.post("/get_contact/refresh")
async def refresh_contact_cache(request: GetContactRequest):
    """Manually refresh the contact cache for a specific patient"""
    try:
        # Force fetch from API
        contact_info = await fetch_contact_from_kolla(request.name, request.dob)
        
        # Update cache
        if contact_info:
            contact_id = contact_info.get("id", f"contact_{request.name}_{request.dob}_{datetime.now().timestamp()}")
            cache_service.store_contact(contact_id, request.name, request.dob, contact_info)
        
        return {
            "success": True,
            "message": "Contact cache refreshed",
            "patient_name": request.name,
            "patient_dob": request.dob,
            "contact_found": contact_info is not None,
            "contact_info": contact_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing contact cache: {str(e)}")

@router.get("/contacts/search")
async def search_contacts(
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None
):
    """
    Search contacts with flexible parameters
    """
    try:
        # This would implement a broader contact search
        # For now, we can only search by name and DOB
        if name:
            # Would need DOB for specific search
            return {
                "success": False,
                "message": "Contact search by name only requires DOB parameter. Use /api/get_contact endpoint instead.",
                "suggestion": "Use POST /api/get_contact with name and dob parameters"
            }
        
        return {
            "success": False,
            "message": "Contact search requires specific parameters",
            "available_search_methods": [
                "POST /api/get_contact with name and dob",
                "GET /api/get_contact/{name}/{dob}"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching contacts: {str(e)}")
