import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .models import RescheduleRequest
from services.patient_interaction_logger import patient_logger

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

router = APIRouter(prefix="/api", tags=["reschedule"])

async def find_appointment_by_phone(phone_number: str) -> Optional[str]:
    """
    Find the latest appointment for a patient by phone number.
    Returns appointment_id if found, None otherwise.
    """
    try:
        # Normalize phone number
        normalized_phone = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Step 1: Search for contacts by phone number
        contacts_url = f"{KOLLA_BASE_URL}/contacts"
        contacts_response = requests.get(contacts_url, headers=KOLLA_HEADERS, timeout=10)
        
        if contacts_response.status_code != 200:
            print(f"Error searching for contacts: {contacts_response.status_code}")
            return None
            
        contacts_data = contacts_response.json()
        
        # Step 2: Find contact with matching phone number
        matching_contact = None
        for contact in contacts_data.get("contacts", []):
            if contact.get("type") == "PATIENT":
                # Check all phone numbers for this contact
                phone_numbers = contact.get("phone_numbers", [])
                primary_phone = contact.get("primary_phone_number", "")
                
                # Normalize contact phone numbers for comparison
                contact_phones = [phone.get("number", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "") 
                                for phone in phone_numbers]
                normalized_primary = primary_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                
                if normalized_phone in contact_phones or normalized_phone == normalized_primary:
                    matching_contact = contact
                    break
        
        if not matching_contact:
            print(f"No patient found with phone number: {phone_number}")
            return None
            
        # Step 3: Get contact_id
        contact_remote_id = matching_contact.get("remote_id")
        contact_name = matching_contact.get("name")  # Like "contacts/13"
        
        print(f"Found matching contact: {contact_name} with remote_id: {contact_remote_id}")
        
        # Step 4: Fetch all appointments and filter by contact_id
        appointments_url = f"{KOLLA_BASE_URL}/appointments"
        appointments_response = requests.get(appointments_url, headers=KOLLA_HEADERS, timeout=10)
        
        if appointments_response.status_code != 200:
            print(f"Error fetching appointments: {appointments_response.status_code}")
            return None
            
        appointments_data = appointments_response.json()
        all_appointments = appointments_data.get("appointments", [])
        
        # Step 5: Filter appointments by contact_id
        patient_appointments = []
        for appointment in all_appointments:
            appointment_contact_id = appointment.get("contact_id")
            
            # Match either by contact name or remote_id
            if (appointment_contact_id == contact_name or 
                appointment_contact_id == f"contacts/{contact_remote_id}"):
                patient_appointments.append(appointment)
        
        if not patient_appointments:
            print(f"No appointments found for contact_id: {contact_name}")
            return None
        
        # Step 6: Sort appointments by start_time to get the latest one
        patient_appointments.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        latest_appointment = patient_appointments[0]
        
        appointment_id = latest_appointment.get("name")  # This is the appointment ID
        print(f"Found latest appointment: {appointment_id} for phone: {phone_number}")
        
        return appointment_id
        
    except Exception as e:
        print(f"Error finding appointment by phone: {e}")
        return None

class FlexibleRescheduleRequest(BaseModel):
    appointment_id: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: Optional[str] = None

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
        response = requests.patch(url, headers=KOLLA_HEADERS, data=json.dumps(patch_data))
        print(f"   Response status: {response.status_code}")
        
        if response.status_code in (200, 204):
            print(f"   ✅ Success: Appointment rescheduled")
            
            # Log successful rescheduling interaction - let the logger fetch patient details
            patient_logger.log_interaction(
                interaction_type="rescheduling",
                success=True,
                appointment_id=appointment_id,
                details={
                    "date": request.date,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "notes": request.notes,
                    "updated_fields": patch_data
                }
            )
            
            return {"success": True, "message": f"Appointment {appointment_id} rescheduled successfully", "appointment_id": appointment_id, "updated_fields": patch_data, "status": "rescheduled"}
        else:
            print(f"   ❌ Failed: {response.text}")
            
            # Log failed rescheduling interaction - let the logger fetch patient details
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
                    "status_code": response.status_code
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
        
        # Log failed rescheduling interaction due to exception - let the logger fetch patient details
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
                "error_type": "exception"
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
