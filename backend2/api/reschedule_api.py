import json
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
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

# Doctor and Hygienist to Provider ID mappings
DOCTOR_PROVIDER_MAPPING = {
    # Doctors
    "Dr. Yuzvyak": "100",              # Maps to "Andriy Yuzvyak"
    "Dr. Hanna": "001",                # Maps to "Dr. Nancy  Hanna"
    "Dr. Parmar": "101",               # Maps to "Akshay Parmar"
    "Dr. Lee": "102",                  # Maps to "Daniel Lee"
    # Add full name variations for better matching
    "Akshay Parmar": "101",
    "Daniel Lee": "102",
    "Andriy Yuzvyak": "100",
    "Nancy Hanna": "001",
    # Hygienists
    "Nadia Khan": "H20",               # Maps to "Nadia Khan RDH"
    "Nadia Khan RDH": "H20",
    "Nadia": "H20",
    "Imelda Soledad": "6",             # Maps to "Imelda Soledad RDH"
    "Imelda Soledad RDH": "6",
    "Imelda": "6",
}

# Alternative mapping using exact display names from Kolla
KOLLA_DISPLAY_NAME_MAPPING = {
    # Doctors
    "Dr. Nancy  Hanna": "001",         # Note: two spaces in display name
    "Andriy Yuzvyak": "100",
    "Akshay Parmar": "101",
    "Daniel Lee": "102",
    # Hygienists
    "Nadia Khan RDH": "H20",
    "Imelda Soledad RDH": "6",
}

# Provider to Operatory mappings
PROVIDER_OPERATORY_MAPPING = {
    # Doctors
    "100": "resources/operatory_8",    # Dr. Andriy Yuzvyak
    "001": "resources/operatory_7",    # Dr. Nancy Hanna
    "101": "resources/operatory_11",   # Dr. Akshay Parmar
    "102": "resources/operatory_10",   # Dr. Daniel Lee
    # Hygienists
    "H20": "resources/operatory_12",   # Nadia Khan RDH
    "6": "resources/operatory_13",     # Imelda Soledad RDH
}

# Operatory remote_id mappings for the resources array
OPERATORY_REMOTE_ID_MAPPING = {
    "resources/operatory_7": "7",
    "resources/operatory_8": "8",
    "resources/operatory_10": "10",
    "resources/operatory_11": "11",
    "resources/operatory_12": "12",
    "resources/operatory_13": "13",
}

def get_provider_and_operatory_from_doctor_name(doctor_name: str) -> Dict[str, Any]:
    """
    Get provider ID and operatory information based on doctor/hygienist name
    Returns dict with provider_id, operatory_resource, and display info
    """
    try:
        print(f"   🔍 Looking up provider: '{doctor_name}'")
        
        # Try primary mapping first
        provider_id = DOCTOR_PROVIDER_MAPPING.get(doctor_name)
        
        # If not found, try Kolla display name mapping
        if not provider_id:
            provider_id = KOLLA_DISPLAY_NAME_MAPPING.get(doctor_name)
        
        # If still not found, try case-insensitive matching
        if not provider_id:
            doctor_name_lower = doctor_name.lower()
            for key, value in DOCTOR_PROVIDER_MAPPING.items():
                if key.lower() == doctor_name_lower:
                    provider_id = value
                    break
        
        if not provider_id:
            print(f"   ⚠️ Provider '{doctor_name}' not found in mappings, using default")
            return {
                "provider_id": "001",  # Default to Dr. Hanna
                "operatory_resource": "resources/operatory_7",
                "operatory_remote_id": "7",
                "display_name": doctor_name,
                "found": False,
                "provider_type": "doctor"
            }
        
        # Get operatory for this provider
        operatory_resource = PROVIDER_OPERATORY_MAPPING.get(provider_id, "resources/operatory_7")
        operatory_remote_id = OPERATORY_REMOTE_ID_MAPPING.get(operatory_resource, "7")
        
        # Determine provider type
        provider_type = "hygienist" if provider_id in ["H20", "6"] else "doctor"
        
        print(f"   ✅ Found mapping: {doctor_name} -> Provider {provider_id} ({provider_type}) -> {operatory_resource} (Remote ID: {operatory_remote_id})")
        
        return {
            "provider_id": provider_id,
            "operatory_resource": operatory_resource,
            "operatory_remote_id": operatory_remote_id,
            "display_name": doctor_name,
            "found": True,
            "provider_type": provider_type
        }
        
    except Exception as e:
        print(f"   ❌ Error mapping provider name: {e}")
        return {
            "provider_id": "001",  # Default to Dr. Hanna
            "operatory_resource": "resources/operatory_7",
            "operatory_remote_id": "7",
            "display_name": doctor_name,
            "found": False,
            "provider_type": "doctor"
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

from pydantic import Extra

class FlexibleRescheduleRequest(BaseModel):
    appointment_id: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: Optional[str] = None
    new_doctor: Optional[str] = None  # New field for specifying doctor

    class Config:
        extra = Extra.allow

class RescheduleByPhoneRequest(BaseModel):
    phone: str
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    notes: Optional[str] = None
    new_doctor: Optional[str] = None  # New field for specifying doctor

    class Config:
        extra = Extra.allow

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
        print(f"   New Doctor: {request.new_doctor}")
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
            notes=request.notes,
            new_doctor=request.new_doctor
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
        
        # Log failed rescheduling interaction with phone number as contact
        patient_logger.log_interaction(
            interaction_type="rescheduling",
            success=False,
            contact_number=request.phone,  # Use the phone number as contact
            reason=request.notes,  # Use the notes as the reason for logging
            error_message=str(e),
            details={
                "date": request.date,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "new_doctor": request.new_doctor,
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

def get_doctor_for_date(target_date: str) -> Optional[Dict[str, Any]]:
    """
    Get the doctor scheduled for a specific date from schedule.json
    Returns doctor info with name and provider_id, or None if not found
    """
    try:
        # Load schedule.json
        schedule_file = Path(__file__).parent.parent / "schedule.json"
        
        if not schedule_file.exists():
            print(f"   ⚠️ Schedule file not found: {schedule_file}")
            return None
        
        with open(schedule_file, 'r') as f:
            schedule = json.load(f)
        
        # Parse the target date to get day of week
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            day_name = date_obj.strftime("%A")  # Get full day name (Monday, Tuesday, etc.)
        except ValueError:
            print(f"   ❌ Invalid date format: {target_date}")
            return None
        
        # Get schedule for that day
        day_schedule = schedule.get(day_name)
        
        if not day_schedule:
            print(f"   ⚠️ No schedule found for {day_name}")
            return None
        
        # Check if clinic is closed
        if day_schedule.get("closed", False):
            print(f"   ⚠️ Clinic is closed on {day_name}")
            return None
        
        # Get doctor for that day
        doctor_name = day_schedule.get("doctor")
        if not doctor_name:
            print(f"   ⚠️ No doctor scheduled for {day_name}")
            return None
        
        # Get provider ID using the new mapping function
        doctor_info = get_provider_and_operatory_from_doctor_name(doctor_name)
        
        print(f"   📋 Doctor for {day_name} ({target_date}): {doctor_name} (Provider ID: {doctor_info['provider_id']})")
        
        return {
            "name": doctor_name,
            "provider_id": doctor_info["provider_id"],
            "operatory_resource": doctor_info["operatory_resource"],
            "operatory_remote_id": doctor_info["operatory_remote_id"],
            "display_name": doctor_name,
            "day_schedule": day_schedule
        }
        
    except Exception as e:
        print(f"   ❌ Error getting doctor for date: {e}")
        return None

def find_operatory_for_provider(provider_id: str, preferred_operatory_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Find an appropriate operatory resource for a given provider using the mapping
    Returns operatory resource info or None if not found
    """
    try:
        # If we have a preferred operatory ID, try to use it
        if preferred_operatory_id:
            return {
                "name": f"resources/{preferred_operatory_id}",
                "remote_id": preferred_operatory_id,
                "type": "operatory", 
                "display_name": f"Operatory {preferred_operatory_id}"
            }
        
        # Use the provider operatory mapping
        operatory_resource = PROVIDER_OPERATORY_MAPPING.get(provider_id, "resources/operatory_7")  # Default to operatory_7
        operatory_remote_id = OPERATORY_REMOTE_ID_MAPPING.get(operatory_resource, "7")
        
        return {
            "name": operatory_resource,
            "remote_id": operatory_remote_id,
            "type": "operatory",
            "display_name": f"Operatory {operatory_remote_id}"
        }
        
    except Exception as e:
        print(f"   ❌ Error finding operatory for provider {provider_id}: {e}")
        return None

@router.post("/reschedule_patient_appointment")
async def reschedule_patient_appointment(request: FlexibleRescheduleRequest):
    """
    Reschedule an existing appointment using EagleSoft-compatible workflow:
    1. Cancel the existing appointment
    2. Create a new appointment with the new time details
    Accepts: appointment_id, date, start_time, end_time, notes, new_doctor
    """
    try:
        print(f"🔄 RESCHEDULE_PATIENT_APPOINTMENT (Cancel + Create New):")
        print(f"   Appointment ID: {request.appointment_id}")
        print(f"   Date: {request.date}")
        print(f"   Start Time: {request.start_time}")
        print(f"   End Time: {request.end_time}")
        print(f"   New Doctor: {request.new_doctor}")
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
        original_date = original_appointment.get("date", "")
        original_notes = original_appointment.get("notes", "")
        
        print(f"   📋 Original appointment details:")
        print(f"   Contact: {contact_info.get('given_name', '')} {contact_info.get('family_name', '')} ({contact_id})")
        print(f"   Original Date: {original_date}")
        print(f"   New Date: {request.date}")
        print(f"   Providers: {[p.get('remote_id', 'N/A') for p in providers]}")
        print(f"   Resources: {original_resources}")
        print(f"   Operatory: '{original_operatory}'")
        print(f"   Service: {original_service}")
        
        # ENHANCED RESCHEDULE LOGIC: Handle new_doctor or date-based provider changes
        updated_providers = providers
        updated_resources = original_resources
        doctor_change_reason = None
        
        if request.new_doctor:
            # New provider specified - use the mapping to get provider and operatory
            print(f"   👨‍⚕️ New provider specified: {request.new_doctor}")
            doctor_mapping = get_provider_and_operatory_from_doctor_name(request.new_doctor)
            
            # Update provider information
            updated_providers = [{
                "name": f"providers/{doctor_mapping['provider_id']}", 
                "remote_id": doctor_mapping['provider_id'],
                "type": "provider",
                "display_name": doctor_mapping['display_name']
            }]
            
            # Update operatory based on provider mapping
            operatory_resource = {
                "name": doctor_mapping['operatory_resource'],
                "remote_id": doctor_mapping['operatory_remote_id'],
                "type": "operatory",
                "display_name": f"Operatory {doctor_mapping['operatory_remote_id']}"
            }
            
            updated_resources = [operatory_resource]
            original_operatory = doctor_mapping['operatory_resource']
            doctor_change_reason = f"Provider changed to {request.new_doctor} ({doctor_mapping['provider_type']})"
            
            print(f"   ✅ Updated provider: {doctor_mapping['display_name']} (ID: {doctor_mapping['provider_id']}, Type: {doctor_mapping['provider_type']})")
            print(f"   ✅ Updated operatory: {doctor_mapping['operatory_resource']} (Remote ID: {doctor_mapping['operatory_remote_id']})")
            
        elif original_date != request.date:
            # Different date but no specific doctor - get doctor scheduled for new date
            print(f"   🔄 Different date detected - looking up doctor for {request.date}")
            doctor_info = get_doctor_for_date(request.date)
            
            if doctor_info:
                print(f"   👨‍⚕️ Updating provider for new date: {doctor_info['name']} (ID: {doctor_info['provider_id']})")
                # Update provider information
                updated_providers = [{
                    "name": f"providers/{doctor_info['provider_id']}", 
                    "remote_id": doctor_info['provider_id'],
                    "type": "provider",
                    "display_name": doctor_info['name']
                }]
                # Update operatory based on provider mapping
                operatory_resource = {
                    "name": doctor_info['operatory_resource'],
                    "remote_id": doctor_info['operatory_remote_id'],
                    "type": "operatory",
                    "display_name": f"Operatory {doctor_info['operatory_remote_id']}"
                }
                updated_resources = [operatory_resource]
                original_operatory = doctor_info['operatory_resource']
                doctor_change_reason = f"Provider updated for new date: {doctor_info['name']}"
                # original_notes already set above
                print(f"   ✅ Updated provider for date: {doctor_info['name']} (ID: {doctor_info['provider_id']})")
                print(f"   ✅ Updated operatory: {doctor_info['operatory_resource']} (Remote ID: {doctor_info['operatory_remote_id']})")
            else:
                print(f"   ⚠️ Could not find doctor for {request.date}, keeping original provider")
        else:
            print(f"   ⏰ Same date and no new doctor specified - keeping original provider and operatory")

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
        print(f"📅 Step 3: Creating new appointment with updated details...")
        
        # Combine date and time for new appointment
        wall_start_time = combine_date_time_to_wall(request.date, request.start_time)
        wall_end_time = combine_date_time_to_wall(request.date, request.end_time)
        
        if not wall_start_time or not wall_end_time:
            return {
                "success": False,
                "message": "Invalid date or time format provided",
                "status": "invalid_time_format"
            }

        # Prepare new appointment data using updated providers and resources
        new_appointment_data = {
            "contact_id": contact_id,
            "contact": contact_info,
            "wall_start_time": wall_start_time,
            "wall_end_time": wall_end_time,
            "providers": updated_providers,  # Use updated providers
            "appointment_type_id": "appointmenttypes/1",
            "scheduler": {
                "name": "",
                "remote_id": "HO7",
                "type": "",
                "display_name": ""
            },
            "short_description": request.notes or "Rescheduled appointment",
            "notes": original_notes,
            "additional_data": original_appointment.get("additional_data", {})
        }
        
        # Handle operatory and resources - use updated resources
        if updated_resources:
            new_appointment_data["resources"] = updated_resources
        
        if original_operatory:
            new_appointment_data["operatory"] = original_operatory
        else:
            # If no operatory specified, create a default operatory resource
            print(f"   ⚠️ No operatory found, creating default operatory resource")
            default_operatory_resource = {
                "name": "resources/operatory_7",  # Default to operatory_7
                "remote_id": "7",
                "type": "operatory",
                "display_name": "Operatory 7"
            }
            
            # Add to resources if not already present
            if not updated_resources:
                new_appointment_data["resources"] = [default_operatory_resource]
            else:
                # Check if there's already an operatory resource
                has_operatory = any(res.get("type") == "operatory" for res in updated_resources)
                if not has_operatory:
                    new_appointment_data["resources"] = updated_resources + [default_operatory_resource]
                else:
                    new_appointment_data["resources"] = updated_resources

        print(f"   📋 New appointment data:")
        print(f"   Time: {wall_start_time} - {wall_end_time}")
        print(f"   Resources: {new_appointment_data.get('resources', [])}")
        print(f"   Operatory: {new_appointment_data.get('operatory', '')}")
        print(f"   Notes: {request.notes}")

        # Create the new appointment
        url = f"{KOLLA_BASE_URL}/appointments"
        response = requests.post(url, headers=KOLLA_HEADERS, json=new_appointment_data, timeout=10)
        print(f"   Response status: {response.status_code}")
        print(f"   Response text: {response.text}")
        
        if response.status_code in (200, 201):
            new_appointment_id = response.json().get('name', f"NEW-{appointment_id}")
            print(f"   ✅ Success: New appointment created with ID: {new_appointment_id}")
            
            # Fetch detailed patient information using contact ID
            patient_details = await fetch_patient_details_by_contact_id(contact_id)
            patient_name = patient_details["patient_name"]
            contact_number = patient_details["contact_number"]
            
            # Extract service and doctor info (use updated providers for logging)
            service_type = original_service if original_service != "Rescheduled Appointment" else None
            doctor = None
            if updated_providers:
                doctor = updated_providers[0].get('display_name') or updated_providers[0].get('name') or updated_providers[0].get('remote_id')
            
            # Create enhanced reschedule note based on changes
            reschedule_note = ""
            if request.new_doctor:
                reschedule_note = f"Rescheduled to {request.date} at {request.start_time}-{request.end_time} with {request.new_doctor}"
            elif original_date != request.date:
                doctor_info = get_doctor_for_date(request.date)
                doctor_name = doctor_info['name'] if doctor_info else f"Provider {updated_providers[0].get('remote_id', 'Unknown')}"
                reschedule_note = f"Rescheduled from {original_date} to {request.date} at {request.start_time}-{request.end_time} with {doctor_name}"
            else:
                reschedule_note = f"Rescheduled time to {request.start_time}-{request.end_time} on {request.date}"
            
            # Log successful rescheduling interaction
            patient_logger.log_interaction(
                interaction_type="rescheduling",
                success=True,
                patient_name=patient_name,
                contact_number=contact_number,
                appointment_id=appointment_id,
                service_type=service_type,
                doctor=doctor,
                reason=request.notes,  # Use the notes as the reason for logging
                details={
                    "original_appointment_id": appointment_id,
                    "new_appointment_id": new_appointment_id,
                    "original_date": original_date,
                    "new_date": request.date,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "new_doctor": request.new_doctor,
                    "doctor_change_reason": doctor_change_reason,
                    "notes": request.notes,
                    "appointment_date": request.date,
                    "appointment_wall_start_time": wall_start_time,
                    "appointment_wall_end_time": wall_end_time,
                    "reschedule_timestamp": datetime.now().isoformat(),
                    "wall_start_time": wall_start_time,
                    "wall_end_time": wall_end_time,
                    "api_method": "cancel_and_create",
                    "contact_id": contact_id,
                    "date_changed": original_date != request.date,
                    "doctor_changed": request.new_doctor is not None,
                    "intelligent_reschedule": True,
                    "reschedule_note": reschedule_note
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
                "new_doctor": request.new_doctor,
                "doctor_change_reason": doctor_change_reason,
                "wall_start_time": wall_start_time,
                "wall_end_time": wall_end_time,
                "notes": request.notes,
                "status": "rescheduled"
            }
        else:
            print(f"   ❌ Failed to create new appointment: {response.text}")
            
            # Fetch detailed patient information using contact ID for failed attempt logging
            patient_details = await fetch_patient_details_by_contact_id(contact_id)
            patient_name = patient_details["patient_name"]
            contact_number = patient_details["contact_number"]
            
            # Extract service and doctor info (use updated providers for logging)
            service_type = original_service if original_service != "Rescheduled Appointment" else None
            doctor = None
            if updated_providers:
                doctor = updated_providers[0].get('display_name') or updated_providers[0].get('name') or updated_providers[0].get('remote_id')
            
            # Log failed rescheduling interaction
            patient_logger.log_interaction(
                interaction_type="rescheduling",
                success=False,
                patient_name=patient_name,
                contact_number=contact_number,
                appointment_id=appointment_id,
                service_type=service_type,
                doctor=doctor,
                reason=request.notes,  # Use the notes as the reason for logging
                error_message=f"Failed to create new appointment: {response.text}",
                details={
                    "original_appointment_id": appointment_id,
                    "original_date": original_date,
                    "new_date": request.date,
                    "start_time": request.start_time,
                    "end_time": request.end_time,
                    "new_doctor": request.new_doctor,
                    "doctor_change_reason": doctor_change_reason,
                    "notes": request.notes,
                    "appointment_date": request.date,
                    "appointment_wall_start_time": wall_start_time,
                    "appointment_wall_end_time": wall_end_time,
                    "reschedule_timestamp": datetime.now().isoformat(),
                    "status_code": response.status_code,
                    "api_method": "cancel_and_create",
                    "step_failed": "create_new_appointment",
                    "date_changed": original_date != request.date,
                    "doctor_changed": request.new_doctor is not None,
                    "intelligent_reschedule": True
                }
            )
            
            return {
                "success": False, 
                "message": f"Original appointment was cancelled, but failed to create new appointment: {response.text}",
                "original_appointment_id": appointment_id,
                "new_doctor": request.new_doctor,
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
        
        # Try to extract patient details from original appointment if available
        patient_name = "Unknown Patient"
        contact_number = "N/A"
        service_type = None
        doctor = None
        
        try:
            if 'original_appointment' in locals() and original_appointment:
                # Try to fetch detailed patient info using contact ID
                contact_info = original_appointment.get("contact", {})
                contact_id = contact_info.get("name", "")
                
                if contact_id:
                    patient_details = await fetch_patient_details_by_contact_id(contact_id)
                    patient_name = patient_details["patient_name"]
                    contact_number = patient_details["contact_number"]
                else:
                    # Fallback to basic extraction
                    given_name = contact_info.get('given_name', '')
                    family_name = contact_info.get('family_name', '')
                    if given_name and family_name:
                        patient_name = f"{given_name} {family_name}"
                    elif given_name:
                        patient_name = given_name
                    elif family_name:
                        patient_name = family_name
                
                service_type = original_appointment.get("short_description")
                providers = original_appointment.get("providers", [])
                if providers:
                    doctor = providers[0].get('display_name') or providers[0].get('name') or providers[0].get('remote_id')
        except:
            pass  # If we can't extract details, that's okay
        
        # Log failed rescheduling interaction due to exception
        patient_logger.log_interaction(
            interaction_type="rescheduling",
            success=False,
            patient_name=patient_name,
            contact_number=contact_number,
            appointment_id=request.appointment_id,
            service_type=service_type,
            doctor=doctor,
            reason=request.notes,  # Use the notes as the reason for logging
            error_message=str(e),
            details={
                "date": request.date,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "new_doctor": request.new_doctor,
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
        
        print(f"📞 Fetching patient details from: {contacts_url}")
        
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, timeout=10)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
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
        
        print(f"   ✅ Patient details: {patient_name}, Phone: {contact_number}")
        
        return {
            "patient_name": patient_name,
            "contact_number": contact_number,
            "given_name": given_name,
            "family_name": family_name,
            "full_contact_data": contact_data
        }
        
    except Exception as e:
        print(f"   ❌ Error fetching patient details: {e}")
        return {
            "patient_name": "Unknown Patient",
            "contact_number": "N/A",
            "given_name": "",
            "family_name": ""
        }

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