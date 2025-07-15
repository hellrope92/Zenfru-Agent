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

@router.post("/reschedule_patient_appointment")
async def reschedule_patient_appointment(request: FlexibleRescheduleRequest):
    """
    Reschedule an existing appointment using Kolla API.
    Accepts: appointment_id, date, start_time, end_time, notes
    """
    try:
        print(f"🔄 RESCHEDULE_PATIENT_APPOINTMENT:")
        print(f"   Appointment ID: {request.appointment_id}")
        print(f"   Date: {request.date}")
        print(f"   Start Time: {request.start_time}")
        print(f"   End Time: {request.end_time}")
        print(f"   Notes: {request.notes}")
        
        appointment_id = request.appointment_id
        if not appointment_id:
            raise HTTPException(status_code=400, detail="appointment_id is required")

        patch_data = {}
        # Kolla expects wall_start_time and wall_end_time for updates, not start_time/end_time
        if request.date and request.start_time:
            print(f"   Combining date '{request.date}' and start_time '{request.start_time}'")
            wall_start = combine_date_time_to_wall(request.date, request.start_time)
            print(f"   Combined wall_start_time result: {wall_start}")
            if not wall_start:
                raise HTTPException(status_code=400, detail="Invalid date or start_time format")
            patch_data["wall_start_time"] = wall_start
        elif request.start_time:
            raise HTTPException(status_code=400, detail="If you provide start_time, you must also provide date.")
        
        if request.date and request.end_time:
            print(f"   Combining date '{request.date}' and end_time '{request.end_time}'")
            wall_end = combine_date_time_to_wall(request.date, request.end_time)
            print(f"   Combined wall_end_time result: {wall_end}")
            if not wall_end:
                raise HTTPException(status_code=400, detail="Invalid date or end_time format")
            patch_data["wall_end_time"] = wall_end
        elif request.end_time:
            raise HTTPException(status_code=400, detail="If you provide end_time, you must also provide date.")
        
        if request.notes:
            patch_data["notes"] = request.notes

        print(f"   Final patch_data: {patch_data}")

        if not patch_data:
            raise HTTPException(status_code=400, detail="No valid reschedule data provided")

        url = f"{KOLLA_BASE_URL}/appointments/{appointment_id}"
        print(f"   Sending PATCH to: {url}")
        print(f"   Headers: {KOLLA_HEADERS}")
        
        response = requests.patch(url, headers=KOLLA_HEADERS, json=patch_data, timeout=10)
        print(f"   Response status: {response.status_code}")
        print(f"   Response text: {response.text}")
        
        if response.status_code in (200, 204):
            print(f"   ✅ Success: Appointment rescheduled")
            
            # Log successful rescheduling interaction
            patient_logger.log_interaction(
                interaction_type="rescheduling",
                success=True,
                appointment_id=appointment_id,
                details={
                    "date": request.date,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "notes": request.notes,
                    "updated_fields": patch_data,
                    "api_method": "kolla_filter_based"
                }
            )
            
            return {"success": True, "message": f"Appointment {appointment_id} rescheduled successfully", "appointment_id": appointment_id, "updated_fields": patch_data, "status": "rescheduled"}
        else:
            print(f"   ❌ Failed: {response.text}")
            
            # Log failed rescheduling interaction
            patient_logger.log_interaction(
                interaction_type="rescheduling",
                success=False,
                appointment_id=appointment_id,
                error_message=f"Kolla API error: {response.text}",
                details={
                    "date": request.date,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "notes": request.notes,
                    "status_code": response.status_code,
                    "api_method": "kolla_filter_based"
                }
            )
            
            return {"success": False, "message": f"Failed to reschedule appointment: {response.text}", "status_code": response.status_code, "appointment_id": appointment_id, "status": "failed"}
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
                "api_method": "kolla_filter_based"
            }
        )
        
        return {"success": False, "message": "An error occurred while rescheduling the appointment. Please contact the clinic directly.", "status": "error", "error": str(e)}

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
