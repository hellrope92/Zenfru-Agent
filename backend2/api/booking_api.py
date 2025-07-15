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

load_dotenv()

from .models import BookAppointmentRequest, RescheduleRequest, ContactInfo
from services.getkolla_service import GetKollaService
from services.patient_interaction_logger import patient_logger

router = APIRouter(prefix="/api", tags=["booking"])

DOCTOR_PROVIDER_MAPPING = {
    "Dr. Yuzvyak": "100",
    "Dr. Hanna": "001",
    "Dr. Parmar": "101",
    "Dr. Lee": "102",
    "Akshay Parmar": "101",
    "Daniel Lee": "102",
    "Andriy Yuzvyak": "100",
    "Nancy Hanna": "001",
}

KOLLA_DISPLAY_NAME_MAPPING = {
    "Dr. Nancy  Hanna": "001",
    "Andriy Yuzvyak": "100",
    "Akshay Parmar": "101",
    "Daniel Lee": "102"
}

PROVIDER_OPERATORY_MAPPING = {
    "100": "resources/operatory_8",
    "001": "resources/operatory_7",
    "101": "resources/operatory_11",
    "102": "resources/operatory_10",
    "H20": "resources/operatory_12",
    "6": "resources/operatory_13",
}

OPERATORY_REMOTE_ID_MAPPING = {
    "resources/operatory_7": "7",
    "resources/operatory_8": "8",
    "resources/operatory_10": "10",
    "resources/operatory_11": "11",
    "resources/operatory_12": "12",
    "resources/operatory_13": "13",
}

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

def load_schedule():
    """Load static schedule from schedule.json"""
    schedule_file = Path(__file__).parent.parent.parent / "schedule.json"
    try:
        with open(schedule_file, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def get_provider_for_appointment_date(appointment_date: str) -> Optional[str]:
    """Get the provider remote_id for a specific appointment date"""
    try:
        date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
        day_name = date_obj.strftime("%A")
        
        schedule = load_schedule()
        day_schedule = schedule.get(day_name, {})
        
        doctor_name = day_schedule.get("doctor", "")
        if not doctor_name:
            return None
            
        provider_id = DOCTOR_PROVIDER_MAPPING.get(doctor_name, "")
        if not provider_id:
            return None
            
        return provider_id
        
    except Exception:
        return None

def get_hygienist_provider_for_appointment_date(appointment_date: str, hygienist_name: str = None) -> Optional[str]:
    """Get the hygienist provider remote_id for a specific appointment date"""
    try:
        date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
        day_name = date_obj.strftime("%A")
        
        schedule = load_schedule()
        day_schedule = schedule.get(day_name, {})
        
        hygienists = day_schedule.get("hygienists", [])
        if not hygienists:
            return None
        
        if hygienist_name:
            for hygienist in hygienists:
                if hygienist.get("name", "").lower() == hygienist_name.lower():
                    return hygienist.get("provider_id", "")
            return None
        else:
            first_hygienist = hygienists[0]
            return first_hygienist.get("provider_id", "")
            
    except Exception:
        return None

def parse_contact_info(contact_data: Union[str, Dict[str, Any]]) -> Dict[str, str]:
    """Parse contact information from various formats"""
    if isinstance(contact_data, str):
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
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        if "AM" in time_str or "PM" in time_str:
            time_obj = datetime.strptime(time_str, "%I:%M %p")
        else:
            time_obj = datetime.strptime(time_str, "%H:%M")
        
        combined_datetime = date_obj.replace(
            hour=time_obj.hour,
            minute=time_obj.minute,
            second=0,
            microsecond=0
        )
        
        return combined_datetime
    except Exception:
        return datetime.now()

def create_kolla_contact(contact_info: dict) -> Optional[str]:
    """Create a new contact in Kolla, return contact_id if successful."""
    url = f"{KOLLA_BASE_URL}/contacts"
    payload = contact_info.copy()
    
    payload.pop('name', None)
    
    fields_to_remove = ['guarantor', 'preferred_provider', 'first_visit']
    for field in fields_to_remove:
        payload.pop(field, None)
    
    if 'state' not in payload:
        payload['state'] = 'ACTIVE'
    if 'type' not in payload:
        payload['type'] = 'PATIENT'
    
    try:
        response = requests.post(url, headers=KOLLA_HEADERS, data=json.dumps(payload), timeout=30)
        
        if response.status_code in (200, 201):
            return response.json().get('name')
        else:
            return None
            
    except Exception:
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

async def check_time_slot_availability(start_datetime: datetime, end_datetime: datetime, operatory_name: str = None) -> bool:
    """Check if the requested time slot is available by querying existing appointments."""
    try:
        url = f"{KOLLA_BASE_URL}/appointments"
        response = requests.get(url, headers=KOLLA_HEADERS, timeout=10)
        
        if response.status_code != 200:
            return True
            
        appointments_data = response.json()
        existing_appointments = appointments_data.get("appointments", [])
        
        for appointment in existing_appointments:
            if appointment.get("cancelled") or appointment.get("completed"):
                continue
                
            appt_wall_start = appointment.get("wall_start_time", "")
            appt_wall_end = appointment.get("wall_end_time", "")
            appt_operatory = None
            
            if operatory_name:
                resources = appointment.get("resources", [])
                for resource in resources:
                    if resource.get("type") == "operatory":
                        appt_operatory = resource.get("name")
                        break
                
                if appt_operatory and appt_operatory != operatory_name:
                    continue
            
            if appt_wall_start and appt_wall_end:
                try:
                    existing_start = datetime.strptime(appt_wall_start, "%Y-%m-%d %H:%M:%S")
                    existing_end = datetime.strptime(appt_wall_end, "%Y-%m-%d %H:%M:%S")
                    
                    if start_datetime < existing_end and end_datetime > existing_start:
                        return False
                        
                except ValueError:
                    continue
        
        return True
        
    except Exception:
        return True

def get_operatory_for_provider(provider_remote_id: str) -> Optional[Dict[str, str]]:
    """Get the operatory resource information for a specific provider"""
    operatory_name = PROVIDER_OPERATORY_MAPPING.get(provider_remote_id)
    if not operatory_name:
        return None
    
    operatory_remote_id = OPERATORY_REMOTE_ID_MAPPING.get(operatory_name)
    if not operatory_remote_id:
        return None
    
    return {
        "name": operatory_name,
        "remote_id": operatory_remote_id,
        "type": "operatory"
    }

def find_provider_resource(resources, request, auto_provider_id=None):
    """Find provider resource using various matching strategies"""
    provider_resource = None
    
    if auto_provider_id:
        for r in resources:
            if r.get('type') == 'PROVIDER' and r.get('remote_id') == auto_provider_id:
                provider_resource = r
                break
    
    if not provider_resource:
        provider_display_name = getattr(request, 'doctor_for_appointment', None)
        if provider_display_name:
            provider_resource = find_resource(resources, "PROVIDER", display_name=provider_display_name)
            
            if not provider_resource and provider_display_name in DOCTOR_PROVIDER_MAPPING:
                mapped_provider_id = DOCTOR_PROVIDER_MAPPING[provider_display_name]
                for r in resources:
                    if r.get('type') == 'PROVIDER' and r.get('remote_id') == mapped_provider_id:
                        provider_resource = r
                        break
            
            if not provider_resource:
                for kolla_name, remote_id in KOLLA_DISPLAY_NAME_MAPPING.items():
                    if provider_display_name.lower() in kolla_name.lower() or kolla_name.lower() in provider_display_name.lower():
                        for r in resources:
                            if r.get('type') == 'PROVIDER' and r.get('remote_id') == remote_id:
                                provider_resource = r
                                break
                        if provider_resource:
                            break
            
            if not provider_resource:
                for r in resources:
                    if r.get('type') == 'PROVIDER':
                        display_name = r.get('display_name', '').lower()
                        request_name = provider_display_name.lower()
                        if any(name in request_name and name in display_name for name in ['hanna', 'parmar', 'yuzvyak', 'lee']):
                            provider_resource = r
                            break
    
    if not provider_resource:
        provider_resource = find_resource(resources, "PROVIDER")
    
    return provider_resource

def find_operatory_resource(resources, provider_resource, request, contact_info):
    """Find operatory resource based on provider or request"""
    operatory_resource = None
    
    if provider_resource:
        provider_remote_id = provider_resource.get('remote_id', '')
        operatory_info = get_operatory_for_provider(provider_remote_id)
        
        if operatory_info:
            operatory_name = operatory_info['name']
            for r in resources:
                if r.get('type') == 'OPERATORY' and r.get('name') == operatory_name:
                    operatory_resource = r
                    break
    
    if not operatory_resource:
        operatory_val = getattr(request, 'operatory', None) or contact_info.get('operatory', None)
        if operatory_val:
            operatory_resource = find_resource(resources, "OPERATORY", display_name=operatory_val)
            if not operatory_resource:
                for r in resources:
                    if r.get('type') == 'OPERATORY' and (r.get('name') == operatory_val or r.get('remote_id') == operatory_val):
                        operatory_resource = r
                        break
    
    if not operatory_resource:
        for r in resources:
            if r.get('type') == 'OPERATORY' and r.get('name') == 'resources/operatory_1':
                operatory_resource = r
                break
    
    if not operatory_resource:
        operatory_resource = find_resource(resources, "OPERATORY")
    
    return operatory_resource

async def book_patient_appointment(request: BookAppointmentRequest, getkolla_service: GetKollaService):
    """Book a new patient appointment using Kolla API, always creating a new contact."""
    
    contact_number = None
    if isinstance(request.contact, str):
        contact_number = request.contact
    elif isinstance(request.contact, dict):
        contact_number = request.contact.get('number') or request.contact.get('phone_number')
    elif hasattr(request.contact, 'number'):
        contact_number = request.contact.number
    
    try:
        if hasattr(request, 'contact_info') and request.contact_info:
            contact_info = request.contact_info.model_dump(exclude_none=True)
        elif isinstance(request.contact, dict):
            contact_info = request.contact
        else:
            contact_info = {'number': request.contact} if isinstance(request.contact, str) else {}

        if 'number' in contact_info and 'phone_numbers' not in contact_info:
            contact_info['phone_numbers'] = [{"number": contact_info['number'], "type": "MOBILE"}]
        if 'email' in contact_info and 'email_addresses' not in contact_info:
            contact_info['email_addresses'] = [{"address": contact_info['email'], "type": "HOME"}]

        if 'given_name' not in contact_info or 'family_name' not in contact_info:
            name_parts = request.name.strip().split(' ', 1)
            if 'given_name' not in contact_info:
                contact_info['given_name'] = name_parts[0] if name_parts else request.name
            if 'family_name' not in contact_info and len(name_parts) > 1:
                contact_info['family_name'] = name_parts[1]
            elif 'family_name' not in contact_info:
                contact_info['family_name'] = ""

        if request.dob and 'birth_date' not in contact_info:
            contact_info['birth_date'] = request.dob

        if 'state' not in contact_info:
            contact_info['state'] = 'ACTIVE'
        if 'type' not in contact_info:
            contact_info['type'] = 'PATIENT'

        contact_id = create_kolla_contact(contact_info)
        if not contact_id:
            return {
                "success": False,
                "message": "Failed to create new patient contact in Kolla.",
                "status": "error",
                "error": "contact_creation_failed"
            }

        try:
            start_datetime = convert_time_to_datetime(request.date, request.time)
            
            base_service_duration = getkolla_service._get_service_duration(request.service_booked)
            slots_needed = getattr(request, 'slots_needed', 1)
            
            if slots_needed > 1:
                service_duration = base_service_duration * slots_needed
            else:
                service_duration = base_service_duration
                
            end_datetime = start_datetime + timedelta(minutes=service_duration)
        except Exception as e:
            return {
                "success": False,
                "message": "Invalid date or time format provided.",
                "status": "error",
                "error": f"date_time_conversion_failed: {str(e)}"
            }

        try:
            resources = get_kolla_resources()
        except Exception as e:
            return {
                "success": False,
                "message": "Failed to fetch clinic resources.",
                "status": "error",
                "error": f"resource_fetch_failed: {str(e)}"
            }

        is_cleaning_appointment = getattr(request, 'iscleaning', False)
        auto_provider_id = None
        
        if is_cleaning_appointment:
            hygienist_name = getattr(request, 'doctor_for_appointment', None)
            auto_provider_id = get_hygienist_provider_for_appointment_date(request.date, hygienist_name)
        else:
            auto_provider_id = get_provider_for_appointment_date(request.date)
        
        provider_resource = find_provider_resource(resources, request, auto_provider_id)
        operatory_resource = find_operatory_resource(resources, provider_resource, request, contact_info)
        
        if not operatory_resource:
            return {
                "success": False,
                "message": "No operatory resource found in Kolla.",
                "status": "error",
                "error": "operatory_not_found"
            }

        if not await check_time_slot_availability(start_datetime, end_datetime, operatory_resource.get("name")):
            return {
                "success": False,
                "message": f"The requested time slot from {request.time} on {request.date} is already booked. Please choose a different time.",
                "status": "time_slot_unavailable",
                "error": "time_slot_conflict"
            }

        providers = []
        if provider_resource:
            providers.append({
                "name": provider_resource.get("name"),
                "remote_id": provider_resource.get("remote_id", ""),
                "type": "PROVIDER"
            })
        
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
            "resources": resources_list,
            "appointment_type_id": "appointmenttypes/1",
            "operatory": operatory_resource.get("name"),
            "scheduler": {
                "name": "",
                "remote_id": "HO7",
                "type": "",
                "display_name": ""
            },
            "short_description": request.service_booked or "New Patient Appointment through Zenfru",
            "notes": request.service_booked or contact_info.get("notes", ""),
            "additional_data": contact_info.get("additional_data", {})
        }
        
        given_name = contact_info.get("given_name", "").strip()
        family_name = contact_info.get("family_name", "").strip()
        if given_name and family_name:
            appointment_data["contact"]["name"] = f"{given_name} {family_name}"
        elif given_name:
            appointment_data["contact"]["name"] = given_name
        elif family_name:
            appointment_data["contact"]["name"] = family_name
        
        url = f"{KOLLA_BASE_URL}/appointments"
        response = requests.post(url, headers=KOLLA_HEADERS, data=json.dumps(appointment_data))
        
        if response.status_code in (200, 201):
            appointment_id = response.json().get('name', f"APT-{uuid.uuid4().hex[:8].upper()}")
            
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
                    "is_new_patient": True,
                    "day": request.day,
                    "contact_id": contact_id
                }
            )
            
            return {
                "success": True,
                "appointment_id": appointment_id,
                "contact_id": contact_id,
                "message": f"New patient appointment successfully booked for {request.name}",
                "status": "confirmed",
                "appointment_details": {
                    "name": request.name,
                    "date": request.date,
                    "time": request.time,
                    "service": request.service_booked,
                    "doctor": request.doctor_for_appointment,
                    "duration_minutes": service_duration,
                    "contact_id": contact_id,
                    "is_new_patient": True
                }
            }
        else:
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
                    "is_new_patient": True,
                    "day": request.day,
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
        patient_logger.log_interaction(
            interaction_type="booking",
            patient_name=request.name,
            contact_number=contact_number,
            success=False,
            service_type=request.service_booked,
            doctor=request.doctor_for_appointment,
            error_message=str(e),
            details={
                "date": request.date,
                "time": request.time,
                "is_new_patient": True,
                "day": request.day,
                "error_type": "exception"
            }
        )
        
        return {
            "success": False,
            "message": f"An error occurred while booking the appointment. Please contact the clinic directly.",
            "status": "error",
            "error": str(e)
        }