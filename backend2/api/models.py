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
    gender: Optional[str] = None  # e.g., 'MALE', 'FEMALE', 'GENDER_UNSPECIFIED'
    birth_date: Optional[str] = None  # YYYY-MM-DD
    notes: Optional[str] = None
    # Address fields
    street_address: Optional[str] = None
    city: Optional[str] = None
    state_address: Optional[str] = None  # Address state (renamed to avoid conflict with patient state)
    postal_code: Optional[str] = None
    country_code: Optional[str] = None
    addresses: Optional[List[Dict[str, Any]]] = None  # List of address dicts
    phone_numbers: Optional[List[Dict[str, Any]]] = None  # List of phone dicts
    email_addresses: Optional[List[Dict[str, Any]]] = None  # List of email dicts
    state: Optional[str] = None  # e.g., 'ACTIVE', 'ARCHIVED'
    opt_ins: Optional[Dict[str, Optional[bool]]] = None  # e.g., {'sms': True, 'email': False}
    preferred_provider: Optional[Dict[str, Any]] = None
    preferred_hygienist_id: Optional[str] = None  # e.g., 'H20', 'HO4'
    preferred_hygienist_name: Optional[str] = None  # e.g., 'resources/provider_H20'
    first_visit: Optional[str] = None  # YYYY-MM-DD
    guarantor: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

class BookAppointmentRequest(BaseModel):
    name: str
    contact_id: str # existing contact ID to link
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
    # Additional fields used by the booking API
    operatory: Optional[str] = None  # Operatory room for the appointment
    slots_needed: Optional[int] = 1  # Number of time slots needed (1 = 30 min, 2 = 1 hour, etc.)
    iscleaning: Optional[bool] = False  # True for hygienist appointments (cleaning), False for doctor appointments
    # Address fields (can be provided directly in request)
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None  # Address state (e.g., "NJ")
    postal_code: Optional[str] = None
    country_code: Optional[str] = None
    # Personal information fields
    gender: Optional[str] = None  # e.g., 'MALE', 'FEMALE', 'GENDER_UNSPECIFIED'

class CheckSlotsRequest(BaseModel):
    day: str

class CheckServiceSlotsRequest(BaseModel):
    service_type: str
    date: Optional[str] = None  # Specific date (YYYY-MM-DD), if not provided will check next 7 days

class RescheduleRequest(BaseModel):
    appointment_id: str
    start_time: str  # ISO format datetime string
    end_time: str    # ISO format datetime string
    notes: Optional[str] = None
    # Optional legacy fields for backward compatibility
    name: Optional[str] = None
    dob: Optional[str] = None
    reason: Optional[str] = None
    new_slot: Optional[str] = None

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

# New models for the core APIs
class GetAppointmentRequest(BaseModel):
    phone: str
    dob: str  # Required DOB for verification

class AppointmentDetailsRequest(BaseModel):
    phone: str
    dob: str  # Required DOB for verification

class ConfirmByPhoneRequest(BaseModel):
    phone: str
    dob: str  # Required DOB for verification
    name: Optional[str] = None
    confirmed: bool = True
    confirmation_type: Optional[str] = "confirmationTypes/1"
    notes: Optional[str] = None

class GetContactRequest(BaseModel):
    phone: str  # Changed from name to phone for consistent patient identification
    dob: str  # Required DOB for verification
    # Legacy support
    name: Optional[str] = None

class AvailabilityRequest(BaseModel):
    date: str  # YYYY-MM-DD format

class LogCallbackRequest(BaseModel):
    name: str
    contact: str
    reason: str
    preferred_callback_time: Optional[str] = None

class SendNewPatientFormRequest(BaseModel):
    phone_number: str

class AnswerFAQRequest(BaseModel):
    query: str

class LogConversationRequest(BaseModel):
    patient_name: Optional[str] = None
    conversation_summary: str
    call_outcome: str
    timestamp: Optional[str] = None
