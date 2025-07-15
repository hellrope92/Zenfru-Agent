import json
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from .models import RescheduleRequest
from services.patient_interaction_logger import patient_logger

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/api", tags=["reschedule"])

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

class FlexibleRescheduleRequest(BaseModel):
    appointment_id: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: Optional[str] = None

class RescheduleByPhoneRequest(BaseModel):
    phone: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: Optional[str] = None

@router.post("/reschedule_by_phone")
async def reschedule_by_phone(request: RescheduleByPhoneRequest):
    """
    Reschedule the latest appointment for a patient using their phone number.
    This endpoint finds the patient's latest appointment and reschedules it.
    """
    try:
        print(f"🔄 RESCHEDULE_BY_PHONE:")
        print(f"   Phone: {request.phone}")
        print(f"   Date: {request.date}")
        print(f"   Start Time: {request.start_time}")
        print(f"   End Time: {request.end_time}")
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
        
        # Create a FlexibleRescheduleRequest and delegate to existing function
        flexible_request = FlexibleRescheduleRequest(
            appointment_id=appointment_id,
            date=request.date,
            start_time=request.start_time,
            end_time=request.end_time,
            notes=request.notes
        )
        
        # Call the existing reschedule function
        result = await reschedule_patient_appointment(flexible_request)
        
        # Add phone number to the result for reference
        if isinstance(result, dict):
            result["phone"] = request.phone
            result["normalized_phone"] = normalized_phone
        
        return result
        
    except Exception as e:
        print(f"   ❌ Error in reschedule_by_phone: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Log failed rescheduling interaction
        patient_logger.log_interaction(
            interaction_type="rescheduling",
            success=False,
            phone_number=request.phone,
            error_message=str(e),
            details={
                "date": request.date,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "notes": request.notes,
                "error_type": "exception",
                "reschedule_method": "by_phone"
            }
        )
        
        return {
            "success": False, 
            "message": "An error occurred while rescheduling the appointment. Please contact the clinic directly.", 
            "status": "error", 
            "error": str(e),
            "phone": request.phone
        }

async def get_appointment_details(appointment_id: str) -> Optional[Dict[str, Any]]:
    """Get appointment details from Kolla API"""
    try:
        url = f"{KOLLA_BASE_URL}/appointments/{appointment_id}"
        print(f"📋 Fetching appointment details: {url}")
        
        response = requests.get(url, headers=KOLLA_HEADERS, timeout=10)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return None
            
        appointment_data = response.json()
        print(f"   ✅ Retrieved appointment details for: {appointment_id}")
        return appointment_data
        
    except Exception as e:
        print(f"   ❌ Error fetching appointment details: {e}")
        return None

async def cancel_appointment(appointment_id: str) -> bool:
    """Cancel an appointment using Kolla API"""
    try:
        url = f"{KOLLA_BASE_URL}/appointments/{appointment_id}:cancel"
        
        # Prepare cancellation payload as per EagleSoft requirements
        cancel_payload = {
            "name": appointment_id,
            "canceler": {
                "name": "resources/provider_HO7",
                "remote_id": "HO7"
            },
            "procedure_code": ""
        }
        
        print(f"❌ Cancelling appointment: {url}")
        print(f"   Payload: {cancel_payload}")
        
        response = requests.post(url, headers=KOLLA_HEADERS, json=cancel_payload, timeout=10)
        print(f"   Response status: {response.status_code}")
        print(f"   Response text: {response.text}")
        
        if response.status_code in (200, 204):
            print(f"   ✅ Successfully cancelled appointment: {appointment_id}")
            return True
        else:
            print(f"   ❌ Failed to cancel appointment: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error cancelling appointment: {e}")
        return False

@router.post("/reschedule_patient_appointment")
async def reschedule_patient_appointment(request: FlexibleRescheduleRequest):
    """
    Reschedule an existing appointment using EagleSoft-compatible workflow:
    1. Cancel the existing appointment
    2. Create a new appointment with the new time details
    Accepts: appointment_id, date, start_time, end_time, notes
    """
    try:
        print(f"🔄 RESCHEDULE_PATIENT_APPOINTMENT (Cancel + Create New):")
        print(f"   Appointment ID: {request.appointment_id}")
        print(f"   Date: {request.date}")
        print(f"   Start Time: {request.start_time}")
        print(f"   End Time: {request.end_time}")
        print(f"   Notes: {request.notes}")
        
        appointment_id = request.appointment_id
        if not appointment_id:
            raise HTTPException(status_code=400, detail="appointment_id is required")

        # Validate that we have the required fields for creating a new appointment
        if not request.date or not request.start_time or not request.end_time:
            raise HTTPException(status_code=400, detail="date, start_time, and end_time are required for rescheduling")

        # Step 1: Get original appointment details before cancelling
        print(f"📋 Step 1: Getting original appointment details...")
        original_appointment = await get_appointment_details(appointment_id)
        
        if not original_appointment:
            return {
                "success": False, 
                "message": f"Could not retrieve original appointment details for {appointment_id}",
                "status": "failed"
            }

        # Extract important details from original appointment
        contact_info = original_appointment.get("contact", {})
        contact_id = contact_info.get("name", "")
        providers = original_appointment.get("providers", [])
        original_resources = original_appointment.get("resources", [])
        original_operatory = original_appointment.get("operatory", "")
        original_service = original_appointment.get("short_description", "Rescheduled Appointment")
        
        print(f"   📋 Original appointment details:")
        print(f"   Contact: {contact_info.get('given_name', '')} {contact_info.get('family_name', '')} ({contact_id})")
        print(f"   Providers: {[p.get('remote_id', 'N/A') for p in providers]}")
        print(f"   Operatory: {original_operatory}")
        print(f"   Service: {original_service}")

        # Step 2: Cancel the existing appointment
        print(f"❌ Step 2: Cancelling original appointment...")
        cancel_success = await cancel_appointment(appointment_id)
        
        if not cancel_success:
            return {
                "success": False,
                "message": f"Failed to cancel original appointment {appointment_id}",
                "status": "cancel_failed"
            }

        # Step 3: Create new appointment with the new time details
        print(f"📅 Step 3: Creating new appointment with updated time...")
        
        # Combine date and time for new appointment
        wall_start_time = combine_date_time_to_wall(request.date, request.start_time)
        wall_end_time = combine_date_time_to_wall(request.date, request.end_time)
        
        if not wall_start_time or not wall_end_time:
            return {
                "success": False,
                "message": "Invalid date or time format provided",
                "status": "invalid_time_format"
            }

        # Prepare new appointment data
        new_appointment_data = {
            "contact_id": contact_id,
            "contact": contact_info,
            "wall_start_time": wall_start_time,
            "wall_end_time": wall_end_time,
            "providers": providers,
            "resources": original_resources,
            "appointment_type_id": "appointmenttypes/1",
            "operatory": original_operatory,
            "scheduler": {
                "name": "",
                "remote_id": "HO7",
                "type": "",
                "display_name": ""
            },
            "short_description": original_service,
            "notes": request.notes or "Rescheduled appointment",
            "additional_data": original_appointment.get("additional_data", {})
        }

        print(f"   📋 New appointment data:")
        print(f"   Time: {wall_start_time} - {wall_end_time}")
        print(f"   Notes: {request.notes}")

        # Create the new appointment
        url = f"{KOLLA_BASE_URL}/appointments"
        response = requests.post(url, headers=KOLLA_HEADERS, json=new_appointment_data, timeout=10)
        print(f"   Response status: {response.status_code}")
        print(f"   Response text: {response.text}")
        
        if response.status_code in (200, 201):
            new_appointment_id = response.json().get('name', f"NEW-{appointment_id}")
            print(f"   ✅ Success: New appointment created with ID: {new_appointment_id}")
            
            # Log successful rescheduling interaction
            patient_logger.log_interaction(
                interaction_type="rescheduling",
                success=True,
                appointment_id=appointment_id,
                details={
                    "original_appointment_id": appointment_id,
                    "new_appointment_id": new_appointment_id,
                    "date": request.date,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "notes": request.notes,
                    "wall_start_time": wall_start_time,
                    "wall_end_time": wall_end_time,
                    "api_method": "cancel_and_create",
                    "contact_id": contact_id
                }
            )
            
            return {
                "success": True, 
                "message": f"Appointment successfully rescheduled from {appointment_id} to {new_appointment_id}",
                "original_appointment_id": appointment_id,
                "new_appointment_id": new_appointment_id,
                "date": request.date,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "wall_start_time": wall_start_time,
                "wall_end_time": wall_end_time,
                "notes": request.notes,
                "status": "rescheduled"
            }
        else:
            print(f"   ❌ Failed to create new appointment: {response.text}")
            
            # Log failed rescheduling interaction
            patient_logger.log_interaction(
                interaction_type="rescheduling",
                success=False,
                appointment_id=appointment_id,
                error_message=f"Failed to create new appointment: {response.text}",
                details={
                    "original_appointment_id": appointment_id,
                    "date": request.date,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "notes": request.notes,
                    "status_code": response.status_code,
                    "api_method": "cancel_and_create",
                    "step_failed": "create_new_appointment"
                }
            )
            
            return {
                "success": False, 
                "message": f"Original appointment was cancelled, but failed to create new appointment: {response.text}",
                "original_appointment_id": appointment_id,
                "status": "partial_failure",
                "status_code": response.status_code
            }
            
    except HTTPException:
        raise
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"   ❌ Error rescheduling appointment: {str(e)}")
        traceback.print_exc()
        
        # Log failed rescheduling interaction due to exception
        patient_logger.log_interaction(
            interaction_type="rescheduling",
            success=False,
            appointment_id=request.appointment_id,
            error_message=str(e),
            details={
                "date": request.date,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "notes": request.notes,
                "error_type": "exception",
                "api_method": "cancel_and_create"
            }
        )
        
        return {
            "success": False, 
            "message": "An error occurred while rescheduling the appointment. Please contact the clinic directly.", 
            "status": "error", 
            "error": str(e)
        }

def combine_date_time(date_str: str, time_str: str) -> Optional[str]:
    """
    Combine separate date and time strings into ISO format.
    """
    try:
        # Parse date
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
        date_obj = None
        
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
        
        if not date_obj:
            return None
        
        # Parse time
        time_formats = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]
        time_obj = None
        
        for fmt in time_formats:
            try:
                time_obj = datetime.strptime(time_str, fmt).time()
                break
            except ValueError:
                continue
        
        if not time_obj:
            return None
        
        # Combine and return ISO format
        dt = datetime.combine(date_obj, time_obj)
        return dt.isoformat() + "Z"
        
    except Exception:
        return None

def combine_date_time_to_wall(date_str: str, time_str: str) -> Optional[str]:
    """
    Combine separate date and time strings into wall time format for Kolla.
    Returns format: "YYYY-MM-DD HH:MM:SS"
    """
    try:
        # Parse date
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
        date_obj = None
        
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
        
        if not date_obj:
            return None
        
        # Parse time
        time_formats = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]
        time_obj = None
        
        for fmt in time_formats:
            try:
                time_obj = datetime.strptime(time_str, fmt).time()
                break
            except ValueError:
                continue
        
        if not time_obj:
            return None
        
        # Combine and return wall time format
        dt = datetime.combine(date_obj, time_obj)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
        
    except Exception:
        return None

# Legacy endpoint for backward compatibility
@router.post("/reschedule_appointment")
async def reschedule_appointment_legacy(request: RescheduleRequest):
    """Legacy reschedule endpoint for backward compatibility"""
    # Convert old format to new format
    flexible_request = FlexibleRescheduleRequest(
        appointment_id=getattr(request, 'appointment_id', '') or request.reason,
        notes=getattr(request, 'reason', None)
    )
    
    return await reschedule_patient_appointment(flexible_request)
