import requests
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from services.patient_interaction_logger import patient_logger
import logging

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

logger = logging.getLogger(__name__)

async def fetch_patient_details_by_contact_id(contact_id: str) -> Dict[str, Any]:
    """
    Fetch detailed patient information using contact ID from Kolla API
    Returns contact details including phone number for reporting
    """
    try:
        # Extract the actual contact ID number from formats like "contacts/10026"
        if "/" in contact_id:
            contact_number = contact_id.split('/')[-1]
        else:
            contact_number = contact_id
        
        contacts_url = f"{KOLLA_BASE_URL}/contacts/{contact_number}"
        
        logger.info(f"📞 Fetching patient details from: {contacts_url}")
        
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, timeout=10)
        logger.info(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"   ❌ API Error: {response.text}")
            return {
                "patient_name": "Unknown Patient",
                "contact_number": "N/A",
                "given_name": "",
                "family_name": ""
            }
            
        contact_data = response.json()
        
        # Extract patient details
        given_name = contact_data.get('given_name', '')
        family_name = contact_data.get('family_name', '')
        
        # Build full name
        if given_name and family_name:
            patient_name = f"{given_name} {family_name}"
        elif given_name:
            patient_name = given_name
        elif family_name:
            patient_name = family_name
        else:
            patient_name = "Unknown Patient"
        
        # Extract contact number with multiple fallbacks
        contact_number = (
            contact_data.get('primary_phone_number') or 
            contact_data.get('phone') or 
            contact_data.get('mobile_phone') or
            (contact_data.get('phone_numbers', [{}])[0].get('number') if contact_data.get('phone_numbers') else None) or
            "N/A"
        )
        
        logger.info(f"   ✅ Patient details: {patient_name}, Phone: {contact_number}")
        
        return {
            "patient_name": patient_name,
            "contact_number": contact_number,
            "given_name": given_name,
            "family_name": family_name,
            "full_contact_data": contact_data
        }
        
    except Exception as e:
        logger.error(f"   ❌ Error fetching patient details: {e}")
        return {
            "patient_name": "Unknown Patient",
            "contact_number": "N/A",
            "given_name": "",
            "family_name": ""
        }

async def get_contact_by_phone_filter(patient_phone: str) -> Optional[Dict[str, Any]]:
    """Fetch contact information from Kolla API using phone filter"""
    try:
        contacts_url = f"{KOLLA_BASE_URL}/contacts"
        
        # Build filter for phone number search
        # Phone number is already normalized (e.g., "5551234567")
        filter_query = f"type='PATIENT' AND state='ACTIVE' AND phone='{patient_phone}'"
        
        params = {"filter": filter_query}
        
        logger.info(f"📞 Calling Kolla API: {contacts_url}")
        logger.info(f"   Filter: {filter_query}")
        logger.info(f"   Normalized phone: {patient_phone}")
        
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, params=params, timeout=10)
        logger.info(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"   ❌ API Error: {response.text}")
            return None
            
        contacts_data = response.json()
        contacts = contacts_data.get("contacts", [])
        
        logger.info(f"   ✅ Found {len(contacts)} contacts matching phone filter")
        
        if contacts:
            # Return the first matching contact
            contact = contacts[0]
            logger.info(f"   📋 Contact: {contact.get('given_name', '')} {contact.get('family_name', '')}")
            return contact
        
        logger.warning(f"   ⚠️ No contact found for phone: {patient_phone}")
        return None
        
    except Exception as e:
        logger.error(f"   ❌ Error fetching contact by phone filter: {e}")
        return None

async def get_appointments_by_contact_filter(contact_id: str) -> List[Dict[str, Any]]:
    """Get appointments for a specific contact using appointments filter"""
    try:
        appointments_url = f"{KOLLA_BASE_URL}/appointments"
        
        # Build filter for contact-specific appointments
        filter_query = f"contact_id='{contact_id}' AND state='SCHEDULED'"
        
        params = {"filter": filter_query}
        
        logger.info(f"📅 Calling Kolla API: {appointments_url}")
        logger.info(f"   Filter: {filter_query}")
        
        response = requests.get(appointments_url, headers=KOLLA_HEADERS, params=params, timeout=10)
        logger.info(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"   ❌ API Error: {response.text}")
            return []
            
        appointments_data = response.json()
        appointments = appointments_data.get("appointments", [])
        
        logger.info(f"   ✅ Found {len(appointments)} appointments for contact: {contact_id}")
        
        # Sort by start_time descending to get latest appointments first
        if appointments:
            appointments.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        
        return appointments
        
    except Exception as e:
        logger.error(f"   ❌ Error fetching appointments by contact filter: {e}")
        return []

async def find_appointment_by_phone(phone_number: str) -> Optional[str]:
    """
    Find the latest appointment for a patient by phone number using Kolla API filters.
    Returns appointment_id if found, None otherwise.
    """
    try:
        # Normalize phone number to standard format (e.g., "5551234567")
        normalized_phone = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        logger.info(f"🔍 Finding appointment for phone: {phone_number} (normalized: {normalized_phone})")
        
        # Step 1: Find contact by phone using filter
        contact_info = await get_contact_by_phone_filter(normalized_phone)
        
        if not contact_info:
            logger.warning(f"   ⚠️ No contact found for phone: {normalized_phone}")
            return None
        
        # Step 2: Get contact_id for appointments filter
        contact_id = contact_info.get("name")  # This is usually like "contacts/123"
        
        if not contact_id:
            logger.warning(f"   ⚠️ No contact ID found for contact")
            return None
        
        logger.info(f"   📋 Found contact: {contact_info.get('given_name', '')} {contact_info.get('family_name', '')} ({contact_id})")
        
        # Step 3: Get appointments for this contact using filter
        appointments = await get_appointments_by_contact_filter(contact_id)
        
        if not appointments:
            logger.warning(f"   ⚠️ No appointments found for contact: {contact_id}")
            return None
        
        # Step 4: Get the latest appointment (already sorted by start_time desc)
        latest_appointment = appointments[0]
        appointment_id = latest_appointment.get("name")  # This is the appointment ID
        
        logger.info(f"   ✅ Found latest appointment: {appointment_id}")
        
        return appointment_id
        
    except Exception as e:
        logger.error(f"   ❌ Error finding appointment by phone: {e}")
        return None

class ConfirmRequest(BaseModel):
    appointment_id: str
    name: Optional[str] = None
    dob: Optional[str] = None  # Date of birth
    confirmed: bool = True
    confirmation_type: Optional[str] = "confirmationTypes/1"  # Fixed: valid confirmation type based on Kolla docs
    notes: Optional[str] = None

class ConfirmByPhoneRequest(BaseModel):
    phone: str
    name: Optional[str] = None
    dob: Optional[str] = None  # Date of birth
    confirmed: bool = True
    confirmation_type: Optional[str] = "confirmationTypes/1"
    notes: Optional[str] = None

@router.post("/confirm_by_phone", status_code=200)
async def confirm_by_phone(request: ConfirmByPhoneRequest):
    """
    Confirm the latest appointment for a patient using their phone number.
    This endpoint finds the patient's latest appointment and confirms it.
    """
    try:
        logger.info(f"Confirm by phone called for {request.phone}")
        
        # Normalize phone number
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Find the latest appointment for this phone number
        appointment_id = await find_appointment_by_phone(normalized_phone)
        
        if not appointment_id:
            logger.warning(f"No appointment found for phone: {request.phone}")
            raise HTTPException(status_code=404, detail="No appointment found for provided phone")
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in confirm_by_phone", exc_info=True)
        patient_logger.log_interaction(
            interaction_type="confirmation",
            success=False,
            contact_number=request.phone,  # Use contact_number instead of phone_number
            error_message=str(e),
            details={
                "confirmation_method": "by_phone"
            }
        )
        raise HTTPException(status_code=500, detail="Internal error confirming appointment by phone")

@router.post("/confirm_appointment")
async def confirm_appointment_endpoint(request: ConfirmRequest):
    """Confirm an appointment using Kolla API with proper format."""
    try:
        logger.info(f"Confirm appointment endpoint called for {request.appointment_id}")

        # Ensure appointment_id is in correct format (strip 'appointments/' if present)
        apt_id = request.appointment_id
        if apt_id.startswith("appointments/"):
            apt_id = apt_id.split("/", 1)[1]

        # Fetch appointment details to verify existence
        details_url = f"{KOLLA_BASE_URL}/appointments/{apt_id}"
        details_response = requests.get(details_url, headers=KOLLA_HEADERS, timeout=10)
        logger.info(f"   Fetching appointment details: {details_url}")
        logger.debug(f"   Details response {details_response.status_code}: {details_response.text}")

        appointment_data = None
        if details_response.status_code == 200:
            try:
                appointment_data = details_response.json()
            except Exception as e:
                logger.warning(f"⚠️ Could not parse appointment details JSON: {e}")
                appointment_data = None

        expected_name = f"appointments/{apt_id}"
        if not appointment_data or appointment_data.get("name") != expected_name:
            logger.warning(f"⚠️ No valid appointment details found for ID: {apt_id}")
            patient_logger.log_interaction(
                interaction_type="confirmation",
                success=False,
                appointment_id=request.appointment_id,
                patient_name=request.name,  # Use the provided name if available
                reason=request.notes,  # Use the notes as the reason for logging
                error_message="Appointment not found or invalid data",
                details={
                    "confirmed": request.confirmed,
                    "confirmation_type": request.confirmation_type,
                    "notes": request.notes,
                    "patient_dob": request.dob,
                    "api_method": "kolla_filter_based"
                }
            )
            raise HTTPException(status_code=404, detail=f"Appointment {apt_id} not found or invalid.")
        
        logger.info("✅ Appointment validation passed - proceeding with confirmation")

        url = f"{KOLLA_BASE_URL}/appointments/{apt_id}:confirm"

        # Prepare the payload in the format expected by Kolla API
        # Kolla expects 'name' as 'appointments/{id}'
        kolla_name = f"appointments/{apt_id}"
        payload = {
            "name": kolla_name,
            "confirmed": request.confirmed,
            "confirmation_type": request.confirmation_type
        }

        # Add notes if provided
        if request.notes:
            payload["notes"] = request.notes
            
        # Print DOB if provided (as requested)
        if request.dob:
            logger.info(f"   Confirming appointment for patient DOB: {request.dob}")
        
        logger.info(f"   Sending POST to: {url}")
        logger.debug(f"   Payload: {payload}")
            
        response = requests.post(url, headers=KOLLA_HEADERS, json=payload, timeout=10)
        logger.debug(f"Kolla API response {response.status_code}: {response.text}")
        
        if response.status_code in (200, 204):
            logger.info("✅ Appointment confirmed successfully")
            
            # Verify confirmation by fetching the appointment again
            verify_response = requests.get(details_url, headers=KOLLA_HEADERS, timeout=10)
            
            actual_confirmed_status = False
            if verify_response.status_code == 200:
                try:
                    verify_data = verify_response.json()
                    actual_confirmed_status = verify_data.get("confirmed", False)
                    if actual_confirmed_status:
                        logger.info("✅ Confirmation verified successfully")
                    else:
                        logger.warning("⚠️ Confirmation API succeeded but appointment status not updated")
                except Exception as e:
                    logger.warning(f"Could not verify confirmation: {e}")
            
            # Extract patient details using contact ID for accurate information
            contact_info = appointment_data.get("contact", {})
            contact_id = contact_info.get("name", "")
            
            # Fetch detailed patient information using contact ID
            if contact_id:
                patient_details = await fetch_patient_details_by_contact_id(contact_id)
                patient_name = patient_details["patient_name"]
                contact_number = patient_details["contact_number"]
            else:
                # Fallback to basic extraction
                patient_name = f"{contact_info.get('given_name', '')} {contact_info.get('family_name', '')}".strip()
                if not patient_name:
                    patient_name = request.name
                
                # Extract contact number
                contact_number = (contact_info.get('primary_phone_number') or 
                                contact_info.get('phone') or 
                                (contact_info.get('phone_numbers', [{}])[0].get('number') if contact_info.get('phone_numbers') else None))
            
            service_type = appointment_data.get("short_description") or appointment_data.get("service_type")
            
            # Get doctor from providers
            doctor = None
            providers = appointment_data.get("providers", [])
            if providers:
                doctor = providers[0].get("display_name") or providers[0].get("name")
                
            # Get doctor from resources if not found in providers
            if not doctor:
                resources = appointment_data.get("resources", [])
                for resource in resources:
                    if resource.get("type") == "operatory":
                        doctor = resource.get("display_name")
                        break
            patient_logger.log_interaction(
                interaction_type="confirmation",
                success=True,
                appointment_id=request.appointment_id,
                patient_name=patient_name,
                contact_number=contact_number,
                service_type=service_type,
                doctor=doctor,
                reason=request.notes,  # Use the notes as the reason for logging
                details={
                    "confirmed": request.confirmed,
                    "confirmation_type": request.confirmation_type,
                    "notes": request.notes,
                    "patient_dob": request.dob,
                    "api_method": "kolla_filter_based",
                    "api_response_status": response.status_code,
                    "confirmation_verified": actual_confirmed_status
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
            logger.error(f"   ❌ Failed: {response.text}")
            
            # Extract patient details for logging failed attempt
            contact_info = appointment_data.get("contact", {})
            patient_name = f"{contact_info.get('given_name', '')} {contact_info.get('family_name', '')}".strip()
            if not patient_name:
                patient_name = request.name
            
            # Extract contact number
            contact_number = None
            if contact_info:
                contact_number = (contact_info.get('primary_phone_number') or 
                                contact_info.get('phone') or 
                                (contact_info.get('phone_numbers', [{}])[0].get('number') if contact_info.get('phone_numbers') else None))
            
            service_type = appointment_data.get("short_description") or appointment_data.get("service_type")
            
            # Get doctor from providers
            doctor = None
            providers = appointment_data.get("providers", [])
            if providers:
                doctor = providers[0].get("display_name") or providers[0].get("name")
            
            # Log failed confirmation interaction
            patient_logger.log_interaction(
                interaction_type="confirmation",
                success=False,
                appointment_id=request.appointment_id,
                patient_name=patient_name,
                contact_number=contact_number,
                service_type=service_type,
                doctor=doctor,
                reason=request.notes,  # Use the notes as the reason for logging
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in confirm_appointment_endpoint", exc_info=True)
        
        # Try to extract patient details from appointment data if available
        patient_name = request.name
        contact_number = None
        service_type = None
        doctor = None
        
        try:
            if 'appointment_data' in locals() and appointment_data:
                contact_info = appointment_data.get("contact", {})
                if contact_info:
                    given_name = contact_info.get('given_name', '')
                    family_name = contact_info.get('family_name', '')
                    if given_name and family_name:
                        patient_name = f"{given_name} {family_name}"
                    elif given_name:
                        patient_name = given_name
                    elif family_name:
                        patient_name = family_name
                    
                    contact_number = (contact_info.get('primary_phone_number') or 
                                    contact_info.get('phone') or 
                                    (contact_info.get('phone_numbers', [{}])[0].get('number') if contact_info.get('phone_numbers') else None))
                
                service_type = appointment_data.get("short_description") or appointment_data.get("service_type")
                providers = appointment_data.get("providers", [])
                if providers:
                    doctor = providers[0].get('display_name') or providers[0].get('name')
        except:
            pass  # If we can't extract details, that's okay
        
        # Log failed confirmation interaction due to exception
        patient_logger.log_interaction(
            interaction_type="confirmation",
            success=False,
            appointment_id=request.appointment_id,
            patient_name=patient_name,
            contact_number=contact_number,
            service_type=service_type,
            doctor=doctor,
            reason=request.notes,  # Use the notes as the reason for logging
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
        
        raise HTTPException(status_code=500, detail="Internal error confirming appointment")
