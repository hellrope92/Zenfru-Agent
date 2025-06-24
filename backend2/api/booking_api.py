"""
Booking-related API endpoints
Handles appointment booking, rescheduling, and booking management
"""
import json
import uuid
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, HTTPException

# Import shared models
from .models import BookAppointmentRequest, RescheduleRequest, ContactInfo

# Import dependencies (will be injected from main.py)
from services.getkolla_service import GetKollaService

router = APIRouter(prefix="/api", tags=["booking"])

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

KOLLA_RESOURCES_URL = f"{KOLLA_BASE_URL}/resources"

def parse_contact_info(contact_data: Union[str, Dict[str, Any]]) -> Dict[str, str]:
    """Parse contact information from various formats"""
    if isinstance(contact_data, str):
        # Assume it's a phone number if it's a string
        return {"phone": contact_data, "email": ""}
    elif isinstance(contact_data, dict):
        return {
            "phone": contact_data.get("number", contact_data.get("phone", "")),
            "email": contact_data.get("email", "")
        }
    else:
        return {"phone": "", "email": ""}

def convert_time_to_datetime(date_str: str, time_str: str) -> datetime:
    """Convert date and time strings to datetime object"""
    try:
        # Parse the date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Parse the time (handle both 12-hour and 24-hour formats)
        if "AM" in time_str or "PM" in time_str:
            time_obj = datetime.strptime(time_str, "%I:%M %p")
        else:
            time_obj = datetime.strptime(time_str, "%H:%M")
        
        # Combine date and time
        combined_datetime = date_obj.replace(
            hour=time_obj.hour,
            minute=time_obj.minute,
            second=0,
            microsecond=0
        )
        
        return combined_datetime
    except Exception as e:
        print(f"Error converting time: {e}")
        # Return a default datetime if parsing fails
        return datetime.now()

def get_kolla_contact_id(contact_info: dict) -> Optional[str]:
    """Check if contact exists in Kolla, return contact_id if found, else None."""
    url = f"{KOLLA_BASE_URL}/contacts"
    response = requests.get(url, headers=KOLLA_HEADERS)
    if response.status_code == 200:
        contacts = response.json().get('contacts', [])
        # Try to match by phone or email
        for c in contacts:
            for phone in c.get('phone_numbers', []):
                if phone.get('number') and contact_info.get('number') and phone['number'] == contact_info['number']:
                    return c.get('name')
            for email in c.get('email_addresses', []):
                if email.get('address') and contact_info.get('email') and email['address'] == contact_info['email']:
                    return c.get('name')
    return None

def create_kolla_contact(contact_info: dict) -> Optional[str]:
    """Create a new contact in Kolla, return contact_id if successful."""
    url = f"{KOLLA_BASE_URL}/contacts"
    payload = contact_info.copy()
    # Kolla expects 'name' to be a unique resource string, so omit it on create
    payload.pop('name', None)
    response = requests.post(url, headers=KOLLA_HEADERS, data=json.dumps(payload))
    if response.status_code in (200, 201):
        return response.json().get('name')
    return None

def get_kolla_resources():
    """Fetch all resources from Kolla and return as a list."""
    response = requests.get(KOLLA_RESOURCES_URL, headers=KOLLA_HEADERS)
    if response.status_code == 200:
        return response.json().get('resources', [])
    return []

def find_resource(resources, resource_type, display_name=None):
    """Find a resource by type (and optionally display_name)."""
    for r in resources:
        if r.get('type') == resource_type:
            if display_name:
                if r.get('display_name', '').lower() == display_name.lower():
                    return r
            else:
                return r
    return None

async def book_patient_appointment(request: BookAppointmentRequest, getkolla_service: GetKollaService):
    """Book a new patient appointment using Kolla API, handling contact lookup/creation."""
    print(f"\U0001F4C5 BOOK_PATIENT_APPOINTMENT:")
    print(f"   Name: {request.name}")
    print(f"   Contact: {request.contact}")
    print(f"   Requested date: {request.date}")
    print(f"   Day: {request.day}")
    print(f"   DOB: {request.dob}")
    print(f"   Time: {request.time}")
    print(f"   Service: {request.service_booked}")
    print(f"   Doctor: {request.doctor_for_appointment}")
    print(f"   New Patient: {request.is_new_patient}")
    print(f"   Patient Details: {request.patient_details}")
    try:
        # Use expanded contact info if provided
        if hasattr(request, 'contact_info') and request.contact_info:
            contact_info = request.contact_info.dict(exclude_none=True)
        elif isinstance(request.contact, dict):
            contact_info = request.contact
        else:
            contact_info = {'number': request.contact} if isinstance(request.contact, str) else {}

        # Default phone_numbers and email_addresses if only value is sent
        if 'number' in contact_info and 'phone_numbers' not in contact_info:
            contact_info['phone_numbers'] = [{"number": contact_info['number'], "type": "MOBILE"}]
        if 'email' in contact_info and 'email_addresses' not in contact_info:
            contact_info['email_addresses'] = [{"address": contact_info['email'], "type": "HOME"}]

        # 1. Check if contact exists in Kolla
        contact_id = get_kolla_contact_id(contact_info)
        # 2. If not, create contact
        if not contact_id:
            contact_id = create_kolla_contact(contact_info)
            if not contact_id:
                return {
                    "success": False,
                    "message": "Failed to create or find contact in Kolla.",
                    "status": "error",
                    "error": "contact_creation_failed"
                }
        # 3. Prepare appointment data for Kolla
        start_datetime = convert_time_to_datetime(request.date, request.time)
        service_duration = getkolla_service._get_service_duration(request.service_booked)
        end_datetime = start_datetime + timedelta(minutes=service_duration)

        # Fetch resources from Kolla
        resources = get_kolla_resources()
        # Find provider resource by display name if provided
        provider_display_name = getattr(request, 'doctor_for_appointment', None)
        provider_resource = None
        if provider_display_name:
            provider_resource = find_resource(resources, "PROVIDER", display_name=provider_display_name)
        if not provider_resource:
            provider_resource = find_resource(resources, "PROVIDER")
        # Find operatory resource by display name if provided
        operatory_val = getattr(request, 'operatory', None) or contact_info.get('operatory', None)
        operatory_resource = None
        if operatory_val:
            # Try to match by display_name
            operatory_resource = find_resource(resources, "OPERATORY", display_name=operatory_val)
            if not operatory_resource:
                # Try to match by resource name or remote_id
                for r in resources:
                    if r.get('type') == 'OPERATORY' and (r.get('name') == operatory_val or r.get('remote_id') == operatory_val):
                        operatory_resource = r
                        break
        if not operatory_resource:
            operatory_resource = find_resource(resources, "OPERATORY")
        if not operatory_resource:
            return {
                "success": False,
                "message": "No operatory resource found in Kolla.",
                "status": "error",
                "error": "operatory_not_found"
            }        # Prepare providers list
        providers = []
        if provider_resource:
            providers.append({
                "name": provider_resource.get("name"),
                "remote_id": provider_resource.get("remote_id", ""),
                "type": "PROVIDER"
            })
        
        appointment_data = {
            "contact_id": contact_id,
            "contact": {
                "name": contact_id,
                "remote_id": contact_info.get("remote_id", ""),
                "given_name": contact_info.get("given_name", ""),
                "family_name": contact_info.get("family_name", "")
            },
            "wall_start_time": start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "wall_end_time": end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "providers": providers,
            "appointment_type_id": request.service_booked,
            "operatory": operatory_resource.get("name"),  # Always use resource name
            "short_description": contact_info.get("short_description", ""),
            "notes": contact_info.get("notes", ""),
            "additional_data": contact_info.get("additional_data", {})
        }
        
        # Set contact name as combination of given_name and family_name
        given_name = contact_info.get("given_name", "").strip()
        family_name = contact_info.get("family_name", "").strip()
        if given_name and family_name:
            appointment_data["contact"]["name"] = f"{given_name} {family_name}"
        elif given_name:
            appointment_data["contact"]["name"] = given_name
        elif family_name:
            appointment_data["contact"]["name"] = family_name
        # If no given/family name, keep contact_id as name
        # 4. Book appointment in Kolla
        url = f"{KOLLA_BASE_URL}/appointments"
        response = requests.post(url, headers=KOLLA_HEADERS, data=json.dumps(appointment_data))
        if response.status_code in (200, 201):
            appointment_id = response.json().get('name', f"APT-{uuid.uuid4().hex[:8].upper()}")
            print(f"   ✅ Appointment successfully booked through Kolla API!")
            print(f"   📋 Appointment ID: {appointment_id}")
            return {
                "success": True,
                "appointment_id": appointment_id,
                "message": f"Appointment successfully booked for {request.name}",
                "status": "confirmed",
                "appointment_details": {
                    "name": request.name,
                    "date": request.date,
                    "time": request.time,
                    "service": request.service_booked,
                    "doctor": request.doctor_for_appointment,
                    "duration_minutes": service_duration
                }
            }
        else:
            print(f"   ❌ Failed to book appointment through Kolla API")
            return {
                "success": False,
                "message": f"Failed to book appointment for {request.name}. Please try again or contact the clinic directly.",
                "status": "failed",
                "error": response.text
            }
    except Exception as e:
        print(f"   ❌ Error booking appointment: {e}")
        return {
            "success": False,
            "message": f"An error occurred while booking the appointment. Please contact the clinic directly.",
            "status": "error",
            "error": str(e)
        }

async def reschedule_patient_appointment(request: RescheduleRequest):
    """Reschedule an existing patient appointment using Kolla API"""
    
    print(f"🔄 RESCHEDULE_PATIENT_APPOINTMENT:")
    print(f"   Appointment ID: {request.appointment_id}")
    print(f"   New Start Time: {request.start_time}")
    print(f"   New End Time: {request.end_time}")
    print(f"   Notes: {request.notes}")
    
    try:
        # Convert ISO datetime strings to the format Kolla expects
        start_dt = datetime.fromisoformat(request.start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(request.end_time.replace('Z', '+00:00'))
        
        # Format for Kolla API (assuming it expects local time format)
        wall_start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        wall_end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare update data for Kolla
        update_data = {
            "wall_start_time": wall_start_time,
            "wall_end_time": wall_end_time
        }
        
        # Add notes if provided
        if request.notes:
            update_data["notes"] = request.notes
        
        # Make API call to update the appointment in Kolla
        url = f"{KOLLA_BASE_URL}/appointments/{request.appointment_id}"
        response = requests.patch(url, headers=KOLLA_HEADERS, data=json.dumps(update_data))
        
        if response.status_code in (200, 204):
            print(f"   ✅ Appointment successfully rescheduled through Kolla API!")
            print(f"   📋 Updated Appointment ID: {request.appointment_id}")
            
            return {
                "success": True,
                "message": f"Appointment {request.appointment_id} successfully rescheduled",
                "status": "confirmed",
                "appointment_details": {
                    "appointment_id": request.appointment_id,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "notes": request.notes,
                    "wall_start_time": wall_start_time,
                    "wall_end_time": wall_end_time,
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            print(f"   ❌ Failed to reschedule appointment through Kolla API")
            print(f"   Error response: {response.text}")
            return {
                "success": False,
                "message": f"Failed to reschedule appointment {request.appointment_id}. Please try again or contact the clinic directly.",
                "status": "failed",
                "error": response.text
            }
            
    except Exception as e:
        print(f"   ❌ Error rescheduling appointment: {e}")
        return {
            "success": False,
            "message": f"An error occurred while rescheduling the appointment. Please contact the clinic directly.",
            "status": "error",
            "error": str(e)
        }
