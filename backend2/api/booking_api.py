"""
Booking-related API endpoints
Handles appointment booking, rescheduling, and booking management
"""
import json
import uuid
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Import shared models
from .models import BookAppointmentRequest, RescheduleRequest, ContactInfo

# Import dependencies (will be injected from main.py)
from services.getkolla_service import GetKollaService
from services.patient_interaction_logger import patient_logger

router = APIRouter(prefix="/api", tags=["booking"])

# Provider ID mappings (updated to match exact Kolla display names)
DOCTOR_PROVIDER_MAPPING = {
    "Dr. Yuzvyak": "100",              # Maps to "Andriy Yuzvyak"
    "Dr. Hanna": "001",                # Maps to "Dr. Nancy  Hanna" 
    "Dr. Parmar": "101",               # Maps to "Akshay Parmar"
    "Dr. Lee": "102",                  # Maps to "Daniel Lee"
    # Add full name variations for better matching
    "Akshay Parmar": "101",
    "Daniel Lee": "102", 
    "Andriy Yuzvyak": "100",
    "Nancy Hanna": "001",
}

# Alternative mapping using exact display names from Kolla
KOLLA_DISPLAY_NAME_MAPPING = {
    "Dr. Nancy  Hanna": "001",         # Note: two spaces in display name
    "Andriy Yuzvyak": "100",
    "Akshay Parmar": "101", 
    "Daniel Lee": "102"
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

# Helper functions for provider auto-selection
def load_schedule():
    """Load static schedule from schedule.json"""
    schedule_file = Path(__file__).parent.parent.parent / "schedule.json"
    try:
        with open(schedule_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading schedule.json: {e}")
        return {}

def get_provider_for_appointment_date(appointment_date: str) -> Optional[str]:
    """Get the provider remote_id for a specific appointment date"""
    try:
        # Parse date and get day name
        date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
        day_name = date_obj.strftime("%A")
        
        # Load schedule
        schedule = load_schedule()
        day_schedule = schedule.get(day_name, {})
        
        # Get doctor name from schedule
        doctor_name = day_schedule.get("doctor", "")
        if not doctor_name:
            print(f"⚠️ No doctor scheduled for {day_name}")
            return None
            
        # Map doctor name to provider ID
        provider_id = DOCTOR_PROVIDER_MAPPING.get(doctor_name, "")
        if not provider_id:
            print(f"⚠️ No provider mapping found for {doctor_name}")
            return None
            
        print(f"📅 Auto-selected provider for {day_name} ({appointment_date}): {doctor_name} -> {provider_id}")
        return provider_id
        
    except Exception as e:
        print(f"❌ Error determining provider for date {appointment_date}: {e}")
        return None

def get_hygienist_provider_for_appointment_date(appointment_date: str, hygienist_name: str = None) -> Optional[str]:
    """Get the hygienist provider remote_id for a specific appointment date"""
    try:
        # Parse date and get day name
        date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
        day_name = date_obj.strftime("%A")
        
        # Load schedule
        schedule = load_schedule()
        day_schedule = schedule.get(day_name, {})
        
        # Get hygienists for this day
        hygienists = day_schedule.get("hygienists", [])
        if not hygienists:
            print(f"⚠️ No hygienists scheduled for {day_name}")
            return None
        
        # If specific hygienist requested, find them
        if hygienist_name:
            for hygienist in hygienists:
                if hygienist.get("name", "").lower() == hygienist_name.lower():
                    provider_id = hygienist.get("provider_id", "")
                    print(f"🦷 Found specific hygienist for {day_name} ({appointment_date}): {hygienist_name} -> {provider_id}")
                    return provider_id
            print(f"⚠️ Requested hygienist {hygienist_name} not found for {day_name}")
            return None
        else:
            # Return first available hygienist
            first_hygienist = hygienists[0]
            provider_id = first_hygienist.get("provider_id", "")
            hygienist_name = first_hygienist.get("name", "")
            print(f"🦷 Auto-selected hygienist for {day_name} ({appointment_date}): {hygienist_name} -> {provider_id}")
            return provider_id
            
    except Exception as e:
        print(f"❌ Error determining hygienist provider for date {appointment_date}: {e}")
        return None

# Load configuration from environment variables
KOLLA_BASE_URL = os.getenv('KOLLA_BASE_URL', 'https://unify.kolla.dev/dental/v1')
KOLLA_BEARER_TOKEN = os.getenv('KOLLA_BEARER_TOKEN', '')
KOLLA_CONNECTOR_ID = os.getenv('KOLLA_CONNECTOR_ID', 'eaglesoft')
KOLLA_CONSUMER_ID = os.getenv('KOLLA_CONSUMER_ID', 'dajc')

KOLLA_HEADERS = {
    'connector-id': KOLLA_CONNECTOR_ID,
    'consumer-id': KOLLA_CONSUMER_ID,
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': f'Bearer {KOLLA_BEARER_TOKEN}'
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

def find_existing_contact_by_phone(phone_number: str) -> Optional[str]:
    """Find existing contact by phone number using Kolla filter, return contact_id if found."""
    if not phone_number:
        return None
    
    # Clean phone number (remove spaces, dashes, parentheses)
    clean_phone = ''.join(filter(str.isdigit, phone_number))
    
    try:
        # Use Kolla filter API like in get_contact_api.py
        contacts_url = f"{KOLLA_BASE_URL}/contacts?filter=phone=%27{clean_phone}%27"
        
        print(f"🔍 Searching for existing contact with phone: {phone_number} (cleaned: {clean_phone})")
        print(f"📞 Calling Kolla API: {contacts_url}")
        
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, timeout=30)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code == 200:
            contacts_data = response.json()
            contacts = contacts_data.get('contacts', [])
            
            print(f"   ✅ Found {len(contacts)} contacts matching phone filter")
            
            if contacts:
                # Return the first matching contact's ID
                contact = contacts[0]
                contact_id = contact.get('name')
                contact_name = f"{contact.get('given_name', '')} {contact.get('family_name', '')}".strip()
                print(f"   📋 Found existing contact: {contact_name} (ID: {contact_id}) with phone: {clean_phone}")
                return contact_id
            else:
                print(f"   ❌ No existing contact found with phone: {phone_number}")
                return None
        else:
            print(f"   ❌ API Error: {response.status_code}, {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("   ❌ Contact search timed out")
        return None
    except Exception as e:
        print(f"   ❌ Error searching for existing contact: {e}")
        return None

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

def create_kolla_contact(contact_info: dict, appointment_date: str = None) -> Optional[str]:
    """Create a new contact in Kolla, return contact_id if successful."""
    url = f"{KOLLA_BASE_URL}/contacts"
    payload = contact_info.copy()
    
    print(f"📋 Input contact_info: {json.dumps(contact_info, indent=2)}")
    
    # Kolla expects 'name' to be a unique resource string, so omit it on create
    payload.pop('name', None)
    
    # Remove fields that should not be sent during contact creation
    fields_to_remove = ['guarantor']  # Remove guarantor, but keep preferred_provider for processing
    for field in fields_to_remove:
        payload.pop(field, None)
    
    # Set default required fields for Kolla contact creation (do this FIRST to avoid conflicts)
    payload['state'] = 'ACTIVE'  # Contact state (always ACTIVE)
    payload['type'] = 'PATIENT'  # Contact type (always PATIENT)
    
    # Set gender - handle various input formats
    print(f"👤 Processing gender: '{payload.get('gender', 'NOT_FOUND')}'")
    if 'gender' not in payload or not payload['gender']:
        payload['gender'] = 'GENDER_UNSPECIFIED'
        print(f"   ➜ Set to default: GENDER_UNSPECIFIED")
    else:
        # Normalize gender values to match Kolla's expected format
        gender_value = str(payload['gender']).upper()
        print(f"   ➜ Normalized to: {gender_value}")
        valid_genders = ['MALE', 'FEMALE', 'OTHER', 'GENDER_UNSPECIFIED']
        if gender_value in ['M', 'MALE']:
            payload['gender'] = 'MALE'
            print(f"   ➜ Final: MALE")
        elif gender_value in ['F', 'FEMALE']:
            payload['gender'] = 'FEMALE'
            print(f"   ➜ Final: FEMALE")
        elif gender_value not in valid_genders:
            payload['gender'] = 'GENDER_UNSPECIFIED'
            print(f"   ➜ Invalid, set to: GENDER_UNSPECIFIED")
        else:
            print(f"   ➜ Final: {payload['gender']}")
    
    # Ensure phone_numbers is properly formatted
    if 'phone_numbers' not in payload and payload.get('number'):
        # Clean the phone number for storage (Kolla stores without formatting)
        clean_number = ''.join(filter(str.isdigit, payload['number']))
        payload['phone_numbers'] = [{"number": clean_number, "type": "MOBILE"}]
    elif 'phone_numbers' in payload:
        # Ensure phone types are set correctly and clean phone numbers
        for phone in payload['phone_numbers']:
            if 'type' not in phone or not phone['type']:
                phone['type'] = 'MOBILE'
            # Clean phone number for consistent storage
            if 'number' in phone:
                phone['number'] = ''.join(filter(str.isdigit, phone['number']))
    
    # Set primary phone number (cleaned)
    if payload.get('phone_numbers') and len(payload['phone_numbers']) > 0:
        payload['primary_phone_number'] = payload['phone_numbers'][0]['number']
    
    # Ensure email_addresses is properly formatted
    if 'email_addresses' not in payload and payload.get('email'):
        payload['email_addresses'] = [{"address": payload['email'], "type": "HOME"}]
    elif 'email_addresses' in payload:
        # Ensure email types are set correctly
        for email in payload['email_addresses']:
            if 'type' not in email or not email['type']:
                email['type'] = 'HOME'
    
    # Set primary email address
    if payload.get('email_addresses') and len(payload['email_addresses']) > 0:
        payload['primary_email_address'] = payload['email_addresses'][0]['address']
    else:
        payload['primary_email_address'] = ""
    
    # Ensure addresses is properly formatted with better defaults
    if 'addresses' not in payload:
        # Build address from individual fields if provided, with proper defaults
        has_address_fields = any(payload.get(field) for field in ['street_address', 'city', 'state_address', 'postal_code', 'country_code'])
        

        address = {
            "street_address": payload.pop('street_address', ""),
            "city": payload.pop('city', ""),
            "state": payload.pop('state_address', "NJ"),
            "postal_code": payload.pop('postal_code', ""),
            "country_code": payload.pop('country_code', "US"),
            "type": "HOME"
        }
        
        if has_address_fields:
            print(f"   📋 Final address object: {address}")
        
        payload['addresses'] = [address]
    else:
        # Ensure address types are set correctly and all required fields exist
        for address in payload['addresses']:
            if 'type' not in address or not address['type']:
                address['type'] = 'HOME'
            # Ensure all address fields exist
            address.setdefault('street_address', '')
            address.setdefault('city', '')
            address.setdefault('state', '')
            address.setdefault('postal_code', '')
            address.setdefault('country_code', '')
    
    # Set opt-ins to true for SMS and email by default for new patients
    if 'opt_ins' not in payload:
        payload['opt_ins'] = {
            "sms": True,
            "email": True
        }
    
    # Set first_visit to appointment date for new patients
    if appointment_date and 'first_visit' not in payload:
        payload['first_visit'] = appointment_date
    
    # Handle preferred provider
    if 'preferred_provider' in payload:
        preferred_provider = payload.pop('preferred_provider')  # Remove from payload to process separately
    else:
        preferred_provider = {
            "name": "resources/provider_001",
            "remote_id": "001", 
            "type": "PROVIDER",
            "display_name": ""
        }
    
    # Handle preferred hygienist in additional_data
    additional_data = payload.get('additional_data', {})
    
    # Set preferred hygienist - always include this field
    if payload.get('preferred_hygienist_id'):
        hygienist_id = payload.pop('preferred_hygienist_id')
        hygienist_name = payload.pop('preferred_hygienist_name', f"resources/provider_{hygienist_id}")
        additional_data.update({
            "preferred_hygienist_id": "H04",
            "preferred_hygienist_name": "resources/provider_HO4",
            "preferred_hygienist_type": "PROVIDER"
        })
    else:
        # Default to HO4 as preferred hygienist (matching your example)
        additional_data.update({
            "preferred_hygienist_id": "HO4",
            "preferred_hygienist_name": "resources/provider_HO4",
            "preferred_hygienist_type": "PROVIDER"
        })
    
    payload['additional_data'] = additional_data
    
    # Clean up individual fields that are now in structured format
    fields_to_clean = ['number', 'email']
    for field in fields_to_clean:
        payload.pop(field, None)
    
    print(f"Creating contact with payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=KOLLA_HEADERS, data=json.dumps(payload), timeout=30)
        print(f"Contact creation response: {response.status_code}, {response.text}")
        
        if response.status_code in (200, 201):
            contact_id = response.json().get('name')
            
            # After successful contact creation, update with preferred_provider
            if contact_id and preferred_provider:
                update_contact_preferred_provider(contact_id, preferred_provider)
            
            return contact_id
        else:
            print(f"Contact creation failed with status {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("Contact creation timed out")
        return None
    except Exception as e:
        print(f"Error creating contact: {e}")
        return None

def update_contact_preferred_provider(contact_id: str, preferred_provider: dict):
    """Update contact with preferred provider after creation"""
    try:
        url = f"{KOLLA_BASE_URL}/contacts/{contact_id}"
        payload = {
            "preferred_provider": preferred_provider
        }
        
        response = requests.patch(url, headers=KOLLA_HEADERS, data=json.dumps(payload), timeout=10)
        if response.status_code in (200, 201):
            print(f"✅ Updated preferred provider for contact {contact_id}")
        else:
            print(f"⚠️ Failed to update preferred provider: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"⚠️ Error updating preferred provider: {e}")

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

# def debug_available_providers(resources):
#     """Debug function to log all available providers"""
#     print(f"🔍 DEBUG: Available providers in Kolla:")
#     providers = [r for r in resources if r.get('type') == 'PROVIDER']
#     for provider in providers:
#         print(f"   - Name: {provider.get('name')} | Remote ID: {provider.get('remote_id')} | Display: '{provider.get('display_name')}' | Position: {provider.get('additional_data', {}).get('position', 'N/A')}")
#     return providers

# def debug_provider_operatory_mappings():
#     """Debug function to show provider-operatory mappings"""
#     print(f"🔍 DEBUG: Provider-Operatory Mappings:")
#     for provider_id, operatory_name in PROVIDER_OPERATORY_MAPPING.items():
#         operatory_remote_id = OPERATORY_REMOTE_ID_MAPPING.get(operatory_name, "N/A")
#         print(f"   Provider {provider_id} → {operatory_name} (remote_id: {operatory_remote_id})")

async def check_time_slot_availability(start_datetime: datetime, end_datetime: datetime, operatory_name: str = None) -> dict:
    """
    Check if the requested time slot is available by querying existing appointments.
    Returns dict with availability info and potential adjusted end time for minor conflicts.
    
    Returns:
    {
        "available": bool,
        "adjusted_end_time": datetime or None,
        "conflict_details": dict or None
    }
    """
    try:
        # Get all appointments from Kolla
        url = f"{KOLLA_BASE_URL}/appointments"
        response = requests.get(url, headers=KOLLA_HEADERS, timeout=10)
        
        if response.status_code != 200:
            print(f"Error fetching appointments for availability check: {response.status_code}")
            # If we can't check, allow the booking (fail open)
            return {"available": True, "adjusted_end_time": None, "conflict_details": None}
            
        appointments_data = response.json()
        existing_appointments = appointments_data.get("appointments", [])
        
        # Convert our datetime to the format we expect from Kolla
        requested_start = start_datetime.strftime("%Y-%m-%d %H:%M:%S")
        requested_end = end_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"   Checking availability for: {requested_start} - {requested_end}")
        if operatory_name:
            print(f"   In operatory: {operatory_name}")
        
        # Check each existing appointment for conflicts
        for appointment in existing_appointments:
            # Skip cancelled or completed appointments
            if appointment.get("cancelled") or appointment.get("completed"):
                continue
                
            # Get appointment times
            appt_wall_start = appointment.get("wall_start_time", "")
            appt_wall_end = appointment.get("wall_end_time", "")
            appt_operatory = None
            
            # Check operatory if specified
            if operatory_name:
                resources = appointment.get("resources", [])
                for resource in resources:
                    if resource.get("type") == "operatory":
                        appt_operatory = resource.get("name")
                        break
                
                # If different operatory, no conflict
                if appt_operatory and appt_operatory != operatory_name:
                    continue
            
            # Check for time overlap
            if appt_wall_start and appt_wall_end:
                try:
                    # Parse existing appointment times
                    existing_start = datetime.strptime(appt_wall_start, "%Y-%m-%d %H:%M:%S")
                    existing_end = datetime.strptime(appt_wall_end, "%Y-%m-%d %H:%M:%S")
                    
                    # Check if there's any overlap
                    # Overlap occurs if: start_time < existing_end AND end_time > existing_start
                    if start_datetime < existing_end and end_datetime > existing_start:
                        appt_id = appointment.get("name", "Unknown")
                        
                        # Check if we can adjust the end time for minor conflicts
                        # Case 1: Our appointment starts before existing but ends slightly into it
                        if (start_datetime < existing_start and 
                            end_datetime > existing_start and 
                            end_datetime <= existing_end):
                            
                            # Calculate the overlap duration
                            overlap_minutes = (end_datetime - existing_start).total_seconds() / 60
                            
                            # If overlap is 15 minutes or less, adjust to end before existing appointment
                            if overlap_minutes <= 15:
                                adjusted_end = existing_start
                                # Ensure minimum 30-minute appointment duration
                                min_duration_minutes = 30
                                if (adjusted_end - start_datetime).total_seconds() / 60 >= min_duration_minutes:
                                    print(f"   🔧 Minor conflict detected ({overlap_minutes:.0f} min overlap)")
                                    print(f"   Existing: {appt_wall_start} - {appt_wall_end}")
                                    print(f"   Requested: {requested_start} - {requested_end}")
                                    print(f"   ✅ Auto-adjusting end time to: {adjusted_end.strftime('%Y-%m-%d %H:%M:%S')}")
                                    
                                    return {
                                        "available": True,
                                        "adjusted_end_time": adjusted_end,
                                        "conflict_details": {
                                            "original_end": end_datetime,
                                            "adjusted_minutes": overlap_minutes,
                                            "conflicting_appointment": appt_id
                                        }
                                    }
                        
                        # If we can't adjust, it's a real conflict
                        print(f"   ❌ Time conflict found with appointment {appt_id}")
                        print(f"   Existing: {appt_wall_start} - {appt_wall_end}")
                        print(f"   Requested: {requested_start} - {requested_end}")
                        
                        return {
                            "available": False,
                            "adjusted_end_time": None,
                            "conflict_details": {
                                "conflicting_appointment": appt_id,
                                "existing_start": appt_wall_start,
                                "existing_end": appt_wall_end
                            }
                        }
                        
                except ValueError as e:
                    print(f"   Warning: Could not parse appointment time format: {e}")
                    continue
        
        print(f"   ✅ Time slot is available")
        return {"available": True, "adjusted_end_time": None, "conflict_details": None}
        
    except Exception as e:
        print(f"   Error checking time slot availability: {e}")
        # If there's an error checking, allow the booking (fail open)
        return {"available": True, "adjusted_end_time": None, "conflict_details": None}

async def book_patient_appointment(request: BookAppointmentRequest, getkolla_service: GetKollaService):
    """Book a new patient appointment using Kolla API, always creating a new contact."""
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
    print(f"   Slots Needed: {getattr(request, 'slots_needed', 1)}")
    print(f"   Is Cleaning: {getattr(request, 'iscleaning', False)}")
    print(f"   Patient Details: {request.patient_details}")
    
    # Extract contact number for logging
    contact_number = None
    if isinstance(request.contact, str):
        contact_number = request.contact
    elif isinstance(request.contact, dict):
        contact_number = request.contact.get('number') or request.contact.get('phone_number')
    elif hasattr(request.contact, 'number'):
        contact_number = request.contact.number
    
    try:
        # Use expanded contact info if provided
        if hasattr(request, 'contact_info') and request.contact_info:
            contact_info = request.contact_info.model_dump(exclude_none=True)
        elif isinstance(request.contact, dict):
            contact_info = request.contact
        else:
            contact_info = {'number': request.contact} if isinstance(request.contact, str) else {}

        # Default phone_numbers and email_addresses if only value is sent
        if 'number' in contact_info and 'phone_numbers' not in contact_info:
            contact_info['phone_numbers'] = [{"number": contact_info['number'], "type": "MOBILE"}]
        if 'email' in contact_info and 'email_addresses' not in contact_info:
            contact_info['email_addresses'] = [{"address": contact_info['email'], "type": "HOME"}]

        # Extract names from the request.name if given_name and family_name are not provided
        if 'given_name' not in contact_info or 'family_name' not in contact_info:
            name_parts = request.name.strip().split(' ', 1)
            if 'given_name' not in contact_info:
                contact_info['given_name'] = name_parts[0] if name_parts else request.name
            if 'family_name' not in contact_info and len(name_parts) > 1:
                contact_info['family_name'] = name_parts[1]
            elif 'family_name' not in contact_info:
                contact_info['family_name'] = ""

        # Set birth_date from dob if provided
        if request.dob and 'birth_date' not in contact_info:
            contact_info['birth_date'] = request.dob

        # Extract address fields from request if provided, and they are not already in contact_info
        address_fields = ['street_address', 'city', 'postal_code', 'country_code']
        print(f"🏠 Extracting address fields from request...")
        for field in address_fields:
            if hasattr(request, field) and getattr(request, field) is not None and field not in contact_info:
                contact_info[field] = getattr(request, field)
                print(f"   ✅ Added {field} = '{getattr(request, field)}' from request root")
        
        # Handle address state field separately to avoid conflict with contact state
        if hasattr(request, 'state') and request.state is not None and 'state_address' not in contact_info:
            contact_info['state_address'] = request.state  # Address state (e.g., "NJ")
            print(f"   ✅ Added state_address = '{request.state}' from request root")
        elif hasattr(request, 'state_address') and request.state_address is not None and 'state_address' not in contact_info:
             contact_info['state_address'] = request.state_address
             print(f"   ✅ Added state_address = '{request.state_address}' from request root")
        
        # Extract gender from request if provided and not in contact_info
        if hasattr(request, 'gender') and request.gender is not None and 'gender' not in contact_info:
            contact_info['gender'] = request.gender
            print(f"   ✅ Added gender = '{request.gender}' from request root")

        # Set required Kolla contact fields (these are different from address fields)
        contact_info.setdefault('state', 'ACTIVE')  # Contact status
        contact_info.setdefault('type', 'PATIENT')  # Contact type
        
        # Set default gender ONLY if not already provided
        if 'gender' not in contact_info or not contact_info['gender']:
            contact_info['gender'] = 'GENDER_UNSPECIFIED'
        
        # Set default preferred provider
        if 'preferred_provider' not in contact_info:
            contact_info['preferred_provider'] = {
                "name": "resources/provider_001",
                "remote_id": "001",
                "type": "PROVIDER", 
                "display_name": ""
            }

        # Check if contact already exists by phone number before creating new one
        contact_id = None
        phone_number = None
        is_new_contact = False
        
        # Extract phone number from contact info
        if 'phone_numbers' in contact_info and contact_info['phone_numbers']:
            phone_number = contact_info['phone_numbers'][0].get('number', '')
        elif 'number' in contact_info:
            phone_number = contact_info['number']
        elif isinstance(request.contact, str):
            phone_number = request.contact
        elif isinstance(request.contact, dict):
            phone_number = request.contact.get('number') or request.contact.get('phone_number')
        
        if phone_number:
            print(f"🔍 Checking for existing contact with phone: {phone_number}")
            contact_id = find_existing_contact_by_phone(phone_number)
        
        # Create new contact only if one doesn't exist
        if not contact_id:
            print(f"   Creating new patient contact in Kolla...")
            contact_id = create_kolla_contact(contact_info, request.date)
            is_new_contact = True
            if not contact_id:
                return {
                    "success": False,
                    "message": "Failed to create new patient contact in Kolla.",
                    "status": "error",
                    "error": "contact_creation_failed"
                }
        else:
            print(f"   Using existing contact: {contact_id}")
            is_new_contact = False

        # 2. Prepare appointment data for Kolla
        try:
            start_datetime = convert_time_to_datetime(request.date, request.time)
            
            # Calculate service duration considering slots_needed
            base_service_duration = getkolla_service._get_service_duration(request.service_booked)
            slots_needed = getattr(request, 'slots_needed', 1)  # Default to 1 slot if not specified
            
            # Each slot is typically 30 minutes, so multiply base duration by slots_needed
            if slots_needed > 1:
                service_duration = base_service_duration * slots_needed
                print(f"📅 Adjusted duration for {slots_needed} slots: {base_service_duration} min → {service_duration} min")
            else:
                service_duration = base_service_duration
                print(f"📅 Using base duration: {service_duration} min")
                
            end_datetime = start_datetime + timedelta(minutes=service_duration)
        except Exception as e:
            print(f"Error preparing appointment data: {e}")
            return {
                "success": False,
                "message": "Invalid date or time format provided.",
                "status": "error",
                "error": f"date_time_conversion_failed: {str(e)}"
            }

        # Fetch resources from Kolla
        try:
            resources = get_kolla_resources()
            # Debug: log available providers for testing
            # debug_available_providers(resources)
            # # Debug: log provider-operatory mappings
            # debug_provider_operatory_mappings()
        except Exception as e:
            print(f"Error fetching resources: {e}")
            return {
                "success": False,
                "message": "Failed to fetch clinic resources.",
                "status": "error",
                "error": f"resource_fetch_failed: {str(e)}"
            }

        # Auto-select provider based on appointment date/day and appointment type
        is_cleaning_appointment = getattr(request, 'iscleaning', False)
        auto_provider_id = None
        
        if is_cleaning_appointment:
            # For hygienist appointments, get hygienist provider ID
            hygienist_name = getattr(request, 'doctor_for_appointment', None)  # doctor_for_appointment might contain hygienist name
            auto_provider_id = get_hygienist_provider_for_appointment_date(request.date, hygienist_name)
            print(f"🦷 Cleaning appointment - Auto-selected hygienist provider: {auto_provider_id}")
        else:
            # For doctor appointments, get doctor provider ID
            auto_provider_id = get_provider_for_appointment_date(request.date)
            print(f"👨‍⚕️ Doctor appointment - Auto-selected doctor provider: {auto_provider_id}")
        
        provider_resource = None
        
        if auto_provider_id:
            # Find provider resource by the auto-selected provider ID
            for r in resources:
                if r.get('type') == 'PROVIDER' and r.get('remote_id') == auto_provider_id:
                    provider_resource = r
                    appointment_type = "hygienist" if is_cleaning_appointment else "doctor"
                    print(f"✅ Auto-selected {appointment_type} provider: {r.get('display_name', 'N/A')} ({auto_provider_id})")
                    break
            
            if not provider_resource:
                appointment_type = "hygienist" if is_cleaning_appointment else "doctor"
                print(f"⚠️ Auto-selected {appointment_type} provider {auto_provider_id} not found in resources, falling back to request provider")
        
        # Fallback: Find provider resource by display name if provided and auto-selection failed
        if not provider_resource:
            provider_display_name = getattr(request, 'doctor_for_appointment', None)
            if provider_display_name:
                print(f"📋 Attempting to find provider for: {provider_display_name}")
                
                # Method 1: Try exact display name match
                provider_resource = find_resource(resources, "PROVIDER", display_name=provider_display_name)
                if provider_resource:
                    print(f"✅ Found provider by exact display name: {provider_resource.get('display_name')} ({provider_resource.get('remote_id')})")
                
                # Method 2: Try using DOCTOR_PROVIDER_MAPPING
                if not provider_resource and provider_display_name in DOCTOR_PROVIDER_MAPPING:
                    mapped_provider_id = DOCTOR_PROVIDER_MAPPING[provider_display_name]
                    for r in resources:
                        if r.get('type') == 'PROVIDER' and r.get('remote_id') == mapped_provider_id:
                            provider_resource = r
                            print(f"✅ Found provider by mapping: {provider_display_name} -> {mapped_provider_id} -> {r.get('display_name')}")
                            break
                
                # Method 3: Try using KOLLA_DISPLAY_NAME_MAPPING  
                if not provider_resource:
                    for kolla_name, remote_id in KOLLA_DISPLAY_NAME_MAPPING.items():
                        if provider_display_name.lower() in kolla_name.lower() or kolla_name.lower() in provider_display_name.lower():
                            for r in resources:
                                if r.get('type') == 'PROVIDER' and r.get('remote_id') == remote_id:
                                    provider_resource = r
                                    print(f"✅ Found provider by Kolla name match: {provider_display_name} -> {kolla_name} -> {remote_id}")
                                    break
                            if provider_resource:
                                break
                
                # Method 4: Try partial name matching
                if not provider_resource:
                    for r in resources:
                        if r.get('type') == 'PROVIDER':
                            display_name = r.get('display_name', '').lower()
                            request_name = provider_display_name.lower()
                            # Check if any significant part of the names match
                            if ('hanna' in request_name and 'hanna' in display_name) or \
                               ('parmar' in request_name and 'parmar' in display_name) or \
                               ('yuzvyak' in request_name and 'yuzvyak' in display_name) or \
                               ('lee' in request_name and 'lee' in display_name):
                                provider_resource = r
                                print(f"✅ Found provider by partial name match: {provider_display_name} -> {r.get('display_name')} ({r.get('remote_id')})")
                                break
                
                if not provider_resource:
                    print(f"⚠️ Could not find provider for: {provider_display_name}")
        
        # Final fallback: Use any available provider
        if not provider_resource:
            provider_resource = find_resource(resources, "PROVIDER")
            print(f"⚠️ Using fallback provider: {provider_resource.get('display_name', 'N/A') if provider_resource else 'None'}")
        
        # Find operatory resource - assign based on provider
        operatory_resource = None
        
        if provider_resource:
            # Try to get provider-specific operatory
            provider_remote_id = provider_resource.get('remote_id', '')
            operatory_info = get_operatory_for_provider(provider_remote_id)
            
            if operatory_info:
                # Find the operatory resource in the resources list
                operatory_name = operatory_info['name']
                for r in resources:
                    if r.get('type') == 'OPERATORY' and r.get('name') == operatory_name:
                        operatory_resource = r
                        print(f"✅ Using provider-specific operatory: {r.get('display_name', operatory_name)} for {provider_resource.get('display_name', 'N/A')}")
                        break
        
        # Fallback to request operatory if provider-specific operatory not found
        if not operatory_resource:
            operatory_val = getattr(request, 'operatory', None) or contact_info.get('operatory', None)
            if operatory_val:
                # Try to match by display_name
                operatory_resource = find_resource(resources, "OPERATORY", display_name=operatory_val)
                if not operatory_resource:
                    # Try to match by resource name or remote_id
                    for r in resources:
                        if r.get('type') == 'OPERATORY' and (r.get('name') == operatory_val or r.get('remote_id') == operatory_val):
                            operatory_resource = r
                            print(f"✅ Using requested operatory: {r.get('display_name', operatory_val)}")
                            break
        
        # Final fallback: Use operatory_1 as default
        if not operatory_resource:
            for r in resources:
                if r.get('type') == 'OPERATORY' and r.get('name') == 'resources/operatory_1':
                    operatory_resource = r
                    print(f"⚠️ Using fallback operatory: {r.get('display_name', 'operatory_1')}")
                    break
        
        # Last resort: Use any operatory
        if not operatory_resource:
            operatory_resource = find_resource(resources, "OPERATORY")
            if operatory_resource:
                print(f"⚠️ Using any available operatory: {operatory_resource.get('display_name', 'N/A')}")
        
        if not operatory_resource:
            return {
                "success": False,
                "message": "No operatory resource found in Kolla.",
                "status": "error",
                "error": "operatory_not_found"
            }

        # # 3. Check for existing appointments at the requested time to prevent double booking
        availability_check = await check_time_slot_availability(start_datetime, end_datetime, operatory_resource.get("name"))
        
        # if not availability_check["available"]:
        #     return {
        #         "success": False,
        #         "message": f"The requested time slot from {request.time} on {request.date} is already booked. Please choose a different time.",
        #         "status": "time_slot_unavailable",
        #         "error": "time_slot_conflict"
        #     }
        
        # Use adjusted end time if provided (for minor conflicts)
        original_end_datetime = end_datetime
        # if availability_check["adjusted_end_time"]:
        #     end_datetime = availability_check["adjusted_end_time"]
        #     adjusted_minutes = availability_check["conflict_details"]["adjusted_minutes"]
        #     print(f"   🔧 Using adjusted appointment duration: {adjusted_minutes:.0f} minutes shorter")
        #     print(f"   Original: {original_end_datetime.strftime('%H:%M')} → Adjusted: {end_datetime.strftime('%H:%M')}")

        # Prepare providers list
        providers = []
        if provider_resource:
            providers.append({
                "name": provider_resource.get("name"),
                "remote_id": provider_resource.get("remote_id", ""),
                "type": "PROVIDER"
            })
        
        # Prepare resources list (for UI display)
        resources_list = []
        if operatory_resource:
            resources_list.append({
                "name": operatory_resource.get("name"),
                "remote_id": operatory_resource.get("remote_id", ""),
                "type": "operatory",
                "display_name": operatory_resource.get("display_name", "")
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
            "resources": resources_list,  # Add resources array for UI
            "appointment_type_id": "appointmenttypes/1",
            "operatory": operatory_resource.get("name"),  # Always use resource name
            "scheduler": {
                "name": "",
                "remote_id": "HO7",
                "type": "",
                "display_name": ""
            },
            "short_description":  request.service_booked or "New Patient Appointment through Zenfru",
            "notes": request.service_booked or contact_info.get("notes", ""),
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
        
        # Log booking details before API call
        print(f"📋 Final booking details:")
        print(f"   Provider: {provider_resource.get('display_name', 'N/A')} ({provider_resource.get('remote_id', 'N/A')})")
        print(f"   Operatory: {operatory_resource.get('display_name', 'N/A')} ({operatory_resource.get('name', 'N/A')})")
        print(f"   Scheduler: HO7 (default)")
        print(f"   Date/Time: {appointment_data['wall_start_time']} - {appointment_data['wall_end_time']}")
        print(f"   Duration: {service_duration} minutes ({slots_needed} slots)")
        
        # 4. Book appointment in Kolla
        url = f"{KOLLA_BASE_URL}/appointments"
        response = requests.post(url, headers=KOLLA_HEADERS, data=json.dumps(appointment_data))
        if response.status_code in (200, 201):
            appointment_id = response.json().get('name', f"APT-{uuid.uuid4().hex[:8].upper()}")
            print(f"   ✅ New patient appointment successfully booked through Kolla API!")
            print(f"   📋 Appointment ID: {appointment_id}")
            print(f"   👤 Contact ID: {contact_id}")
            
            # Log successful booking interaction
            patient_logger.log_interaction(
                interaction_type="booking",
                patient_name=request.name,
                contact_number=contact_number,
                success=True,
                appointment_id=appointment_id,
                service_type=request.service_booked,
                doctor=request.doctor_for_appointment,
                details={
                    "date": request.date,
                    "time": request.time,
                    "day": request.day,
                    "appointment_date": request.date,
                    "appointment_wall_start_time": appointment_data.get('wall_start_time'),
                    "appointment_wall_end_time": appointment_data.get('wall_end_time'),
                    "booking_timestamp": datetime.now().isoformat(),
                    "is_new_patient": request.is_new_patient,
                    "is_new_contact": is_new_contact,
                    "contact_id": contact_id
                }
            )
            
            # Create appropriate success message based on whether contact was new or existing
            if is_new_contact:
                success_message = f"New patient appointment successfully booked for {request.name}"
            else:
                success_message = f"Appointment successfully booked for existing patient {request.name}"
            
            # Add note about duration adjustment if applicable
            if availability_check["adjusted_end_time"]:
                adjusted_minutes = availability_check["conflict_details"]["adjusted_minutes"]
                actual_duration = int((end_datetime - start_datetime).total_seconds() / 60)
                success_message += f" (Duration adjusted by -{adjusted_minutes:.0f} minutes due to scheduling conflict)"
            else:
                actual_duration = service_duration
            
            return {
                "success": True,
                "appointment_id": appointment_id,
                "contact_id": contact_id,
                "message": success_message,
                "status": "confirmed",
                "appointment_details": {
                    "name": request.name,
                    "date": request.date,
                    "time": request.time,
                    "end_time": end_datetime.strftime("%H:%M"),
                    "service": request.service_booked,
                    "doctor": request.doctor_for_appointment,
                    "duration_minutes": actual_duration,
                    "original_duration_minutes": service_duration,
                    "duration_adjusted": availability_check["adjusted_end_time"] is not None,
                    "contact_id": contact_id,
                    "is_new_patient": request.is_new_patient,
                    "is_new_contact": is_new_contact
                }
            }
        else:
            print(f"   ❌ Failed to book appointment through Kolla API")
            
            # Log failed booking interaction
            patient_logger.log_interaction(
                interaction_type="booking",
                patient_name=request.name,
                contact_number=contact_number,
                success=False,
                service_type=request.service_booked,
                doctor=request.doctor_for_appointment,
                error_message=f"Kolla API error: {response.text}",
                details={
                    "date": request.date,
                    "time": request.time,
                    "day": request.day,
                    "appointment_date": request.date,
                    "appointment_wall_start_time": appointment_data.get('wall_start_time'),
                    "appointment_wall_end_time": appointment_data.get('wall_end_time'),
                    "booking_timestamp": datetime.now().isoformat(),
                    "is_new_patient": request.is_new_patient,
                    "is_new_contact": is_new_contact,
                    "status_code": response.status_code
                }
            )
            
            return {
                "success": False,
                "message": f"Failed to book appointment for {request.name}. Please try again or contact the clinic directly.",
                "status": "failed",
                "error": response.text
            }
    except Exception as e:
        print(f"   ❌ Error booking appointment: {e}")
        
        # Determine if is_new_contact variable exists in scope for error logging
        try:
            is_new_contact_for_error = is_new_contact
        except NameError:
            is_new_contact_for_error = None
        
        # Log failed booking interaction due to exception
        patient_logger.log_interaction(
            interaction_type="booking",
            patient_name=request.name,
            contact_number=contact_number,
            success=False,
            service_type=request.service_booked,
            doctor=request.doctor_for_appointment,
            error_message=str(e),
            details={
                "appointment_date": request.date,
                "booking_timestamp": datetime.now().isoformat(),
                "is_new_patient": request.is_new_patient,
                "is_new_contact": is_new_contact_for_error,
                "error_type": "exception"
            }
        )
        
        return {
            "success": False,
            "message": f"An error occurred while booking the appointment. Please contact the clinic directly.",
            "status": "error",
            "error": str(e)
        }

def get_operatory_for_provider(provider_remote_id: str) -> Optional[Dict[str, str]]:
    """Get the operatory resource information for a specific provider"""
    operatory_name = PROVIDER_OPERATORY_MAPPING.get(provider_remote_id)
    if not operatory_name:
        print(f"⚠️ No operatory mapping found for provider {provider_remote_id}")
        return None
    
    operatory_remote_id = OPERATORY_REMOTE_ID_MAPPING.get(operatory_name)
    if not operatory_remote_id:
        print(f"⚠️ No remote_id mapping found for operatory {operatory_name}")
        return None
    
    return {
        "name": operatory_name,
        "remote_id": operatory_remote_id,
        "type": "operatory"
    }
