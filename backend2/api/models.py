"""
Shared Pydantic models for the API
Contains all the data models used across different API endpoints
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel

class ContactInfo(BaseModel):
    number: Optional[str] = None
    email: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    preferred_name: Optional[str] = None
    gender: Optional[str] = None  # e.g., 'GENDER_MALE', 'GENDER_FEMALE', 'GENDER_OTHER'
    birth_date: Optional[str] = None  # YYYY-MM-DD
    notes: Optional[str] = None
    addresses: Optional[List[Dict[str, Any]]] = None  # List of address dicts
    phone_numbers: Optional[List[Dict[str, Any]]] = None  # List of phone dicts
    email_addresses: Optional[List[Dict[str, Any]]] = None  # List of email dicts
    state: Optional[str] = None  # e.g., 'ACTIVE', 'ARCHIVED'
    opt_ins: Optional[Dict[str, Optional[bool]]] = None  # e.g., {'sms': True, 'email': False}
    preferred_provider: Optional[Dict[str, Any]] = None
    first_visit: Optional[str] = None  # YYYY-MM-DD
    guarantor: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

class BookAppointmentRequest(BaseModel):
    name: str
    contact: Union[str, Dict[str, Any], ContactInfo]  # Accept string, dict, or ContactInfo
    day: str
    date: str  # Added date field
    dob: Optional[str] = None  # Added patient date of birth
    time: str
    is_new_patient: bool
    service_booked: str
    doctor_for_appointment: str
    patient_details: Optional[Union[str, Dict[str, Any]]] = None  # Accept both string and dict
    # Optionally allow direct passing of expanded contact info
    contact_info: Optional[ContactInfo] = None

class CheckSlotsRequest(BaseModel):
    day: str

class CheckServiceSlotsRequest(BaseModel):
    service_type: str
    date: Optional[str] = None  # Specific date (YYYY-MM-DD), if not provided will check next 7 days

class RescheduleRequest(BaseModel):
    name: str
    dob: str
    reason: str
    new_slot: str

class CallbackRequest(BaseModel):
    name: str
    contact_number: str
    preferred_callback_time: str

class SendFormRequest(BaseModel):
    contact_number: str

class FAQRequest(BaseModel):
    query: str

class ConversationSummaryRequest(BaseModel):
    summary: Optional[str] = None  # Accepts a summary string
    patient_name: Optional[str] = None
    primary_intent: Optional[str] = None
    appointment_details: Optional[Dict[str, Any]] = None
    outcome: Optional[str] = None
    call_duration: Optional[int] = None
    additional_notes: Optional[str] = None
