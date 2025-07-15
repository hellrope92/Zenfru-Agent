import requests
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from services.patient_interaction_logger import patient_logger

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/api", tags=["confirm"])

# Kolla API configuration
KOLLA_BASE_URL = os.getenv("KOLLA_BASE_URL", "https://unify.kolla.dev/dental/v1")
KOLLA_HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {os.getenv('KOLLA_BEARER_TOKEN')}",
    "connector-id": os.getenv("KOLLA_CONNECTOR_ID", "eaglesoft"),
    "consumer-id": os.getenv("KOLLA_CONSUMER_ID", "dajc")
}

async def get_contact_by_phone_filter(patient_phone: str) -> Optional[Dict[str, Any]]:
    """Fetch contact information from Kolla API using phone filter"""
    try:
        contacts_url = f"{KOLLA_BASE_URL}/contacts"
        
        # Build filter for phone number search
        # Phone number is already normalized (e.g., "5551234567")
        filter_query = f"type='PATIENT' AND state='ACTIVE' AND phone='{patient_phone}'"
        
        params = {"filter": filter_query}
        
        print(f"📞 Calling Kolla API: {contacts_url}")
        print(f"   Filter: {filter_query}")
        print(f"   Normalized phone: {patient_phone}")
        
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, params=params, timeout=10)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return None
            
        contacts_data = response.json()
        contacts = contacts_data.get("contacts", [])
        
        print(f"   ✅ Found {len(contacts)} contacts matching phone filter")
        
        if contacts:
            # Return the first matching contact
            contact = contacts[0]
            print(f"   📋 Contact: {contact.get('given_name', '')} {contact.get('family_name', '')}")
            return contact
        
        print(f"   ⚠️ No contact found for phone: {patient_phone}")
        return None
        
    except Exception as e:
        print(f"   ❌ Error fetching contact by phone filter: {e}")
        return None

async def get_appointments_by_contact_filter(contact_id: str) -> List[Dict[str, Any]]:
    """Get appointments for a specific contact using appointments filter"""
    try:
        appointments_url = f"{KOLLA_BASE_URL}/appointments"
        
        # Build filter for contact-specific appointments
        filter_query = f"contact_id='{contact_id}' AND state='SCHEDULED'"
        
        params = {"filter": filter_query}
        
        print(f"📅 Calling Kolla API: {appointments_url}")
        print(f"   Filter: {filter_query}")
        
        response = requests.get(appointments_url, headers=KOLLA_HEADERS, params=params, timeout=10)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return []
            
        appointments_data = response.json()
        appointments = appointments_data.get("appointments", [])
        
        print(f"   ✅ Found {len(appointments)} appointments for contact: {contact_id}")
        
        # Sort by start_time descending to get latest appointments first
        if appointments:
            appointments.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        
        return appointments
        
    except Exception as e:
        print(f"   ❌ Error fetching appointments by contact filter: {e}")
        return []

async def find_appointment_by_phone(phone_number: str) -> Optional[str]:
    """
    Find the latest appointment for a patient by phone number using Kolla API filters.
    Returns appointment_id if found, None otherwise.
    """
    try:
        # Normalize phone number to standard format (e.g., "5551234567")
        normalized_phone = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        print(f"🔍 Finding appointment for phone: {phone_number} (normalized: {normalized_phone})")
        
        # Step 1: Find contact by phone using filter
        contact_info = await get_contact_by_phone_filter(normalized_phone)
        
        if not contact_info:
            print(f"   ⚠️ No contact found for phone: {normalized_phone}")
            return None
        
        # Step 2: Get contact_id for appointments filter
        contact_id = contact_info.get("name")  # This is usually like "contacts/123"
        
        if not contact_id:
            print(f"   ⚠️ No contact ID found for contact")
            return None
        
        print(f"   📋 Found contact: {contact_info.get('given_name', '')} {contact_info.get('family_name', '')} ({contact_id})")
        
        # Step 3: Get appointments for this contact using filter
        appointments = await get_appointments_by_contact_filter(contact_id)
        
        if not appointments:
            print(f"   ⚠️ No appointments found for contact: {contact_id}")
            return None
        
        # Step 4: Get the latest appointment (already sorted by start_time desc)
        latest_appointment = appointments[0]
        appointment_id = latest_appointment.get("name")  # This is the appointment ID
        
        print(f"   ✅ Found latest appointment: {appointment_id}")
        
        return appointment_id
        
    except Exception as e:
        print(f"   ❌ Error finding appointment by phone: {e}")
        return None

class ConfirmRequest(BaseModel):
    appointment_id: str
    name: Optional[str] = None
    dob: Optional[str] = None  # Date of birth
    confirmed: bool = True
    confirmation_type: Optional[str] = "confirmationTypes/0"  # Fixed: valid confirmation type
    notes: Optional[str] = None

class ConfirmByPhoneRequest(BaseModel):
    phone: str
    name: Optional[str] = None
    dob: Optional[str] = None  # Date of birth
    confirmed: bool = True
    confirmation_type: Optional[str] = "confirmationTypes/0"
    notes: Optional[str] = None

@router.post("/confirm_by_phone")
async def confirm_by_phone(request: ConfirmByPhoneRequest):
    """
    Confirm the latest appointment for a patient using their phone number.
    This endpoint finds the patient's latest appointment and confirms it.
    """
    try:
        print(f"✅ CONFIRM_BY_PHONE:")
        print(f"   Phone: {request.phone}")
        print(f"   Name: {request.name}")
        print(f"   DOB: {request.dob}")
        print(f"   Confirmed: {request.confirmed}")
        print(f"   Notes: {request.notes}")
        
        # Normalize phone number
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Find the latest appointment for this phone number
        appointment_id = await find_appointment_by_phone(normalized_phone)
        
        if not appointment_id:
            return {
                "success": False,
                "message": "No appointment found for the provided phone number",
                "phone": request.phone,
                "status": "not_found"
            }
        
        # Create a ConfirmRequest and delegate to existing function
        confirm_request = ConfirmRequest(
            appointment_id=appointment_id,
            name=request.name,
            dob=request.dob,
            confirmed=request.confirmed,
            confirmation_type=request.confirmation_type,
            notes=request.notes
        )
        
        # Call the existing confirm function
        result = await confirm_appointment_endpoint(confirm_request)
        
        # Add phone number to the result for reference
        if isinstance(result, dict):
            result["phone"] = request.phone
            result["normalized_phone"] = normalized_phone
        
        return result
        
    except Exception as e:
        print(f"   ❌ Error in confirm_by_phone: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Log failed confirmation interaction
        patient_logger.log_interaction(
            interaction_type="confirmation",
            success=False,
            phone_number=request.phone,
            error_message=str(e),
            details={
                "confirmed": request.confirmed,
                "confirmation_type": request.confirmation_type,
                "notes": request.notes,
                "patient_dob": request.dob,
                "error_type": "exception",
                "confirmation_method": "by_phone"
            }
        )
        
        return {
            "success": False,
            "message": "An error occurred while confirming the appointment. Please contact the clinic directly.",
            "status": "error",
            "error": str(e),
            "phone": request.phone
        }

@router.post("/confirm_appointment")
async def confirm_appointment_endpoint(request: ConfirmRequest):
    """Confirm an appointment using Kolla API with proper format."""
    try:
        print(f"✅ CONFIRM_APPOINTMENT:")
        print(f"   Appointment ID: {request.appointment_id}")
        print(f"   Name: {request.name}")
        print(f"   DOB: {request.dob}")
        print(f"   Confirmed: {request.confirmed}")
        print(f"   Notes: {request.notes}")
        
        url = f"{KOLLA_BASE_URL}/appointments/{request.appointment_id}:confirm"
        
        # Prepare the payload in the format expected by Kolla API
        payload = {
            "confirmed": request.confirmed,
            "additional_data": {
                "confirmation_type": request.confirmation_type
            }
        }
        
        # Add notes if provided
        if request.notes:
            payload["notes"] = request.notes
            
        # Add name if provided
        if request.name:
            payload["name"] = request.name
            
        # Print DOB if provided (as requested)
        if request.dob:
            print(f"   Confirming appointment for patient DOB: {request.dob}")
        
        print(f"   Sending POST to: {url}")
        print(f"   Payload: {payload}")
            
        response = requests.post(url, headers=KOLLA_HEADERS, json=payload, timeout=10)
        print(f"   Response status: {response.status_code}")
        print(f"   Response text: {response.text}")
        
        if response.status_code in (200, 204):
            print(f"   ✅ Success: Appointment confirmed")
            
            # Log successful confirmation interaction
            patient_logger.log_interaction(
                interaction_type="confirmation",
                success=True,
                appointment_id=request.appointment_id,
                details={
                    "confirmed": request.confirmed,
                    "confirmation_type": request.confirmation_type,
                    "notes": request.notes,
                    "patient_dob": request.dob,
                    "api_method": "kolla_filter_based"
                }
            )
            
            return {
                "success": True,
                "message": f"Appointment {request.appointment_id} confirmed successfully.",
                "appointment_id": request.appointment_id,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "confirmed": request.confirmed,
                "confirmation_type": request.confirmation_type,
                "notes": request.notes,
                "status": "confirmed"
            }
        else:
            print(f"   ❌ Failed: {response.text}")
            
            # Log failed confirmation interaction
            patient_logger.log_interaction(
                interaction_type="confirmation",
                success=False,
                appointment_id=request.appointment_id,
                error_message=f"Kolla API error: {response.text}",
                details={
                    "confirmed": request.confirmed,
                    "confirmation_type": request.confirmation_type,
                    "notes": request.notes,
                    "patient_dob": request.dob,
                    "status_code": response.status_code,
                    "api_method": "kolla_filter_based"
                }
            )
            
            return {
                "success": False,
                "message": f"Failed to confirm appointment: {response.text}",
                "status_code": response.status_code,
                "appointment_id": request.appointment_id,
                "status": "failed"
            }
    except Exception as e:
        print(f"   ❌ Error confirming appointment: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Log failed confirmation interaction due to exception
        patient_logger.log_interaction(
            interaction_type="confirmation",
            success=False,
            appointment_id=request.appointment_id,
            error_message=str(e),
            details={
                "confirmed": request.confirmed,
                "confirmation_type": request.confirmation_type,
                "notes": request.notes,
                "patient_dob": request.dob,
                "error_type": "exception",
                "api_method": "kolla_filter_based"
            }
        )
        
        raise HTTPException(status_code=500, detail=f"Error confirming appointment: {str(e)}")
