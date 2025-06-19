"""
Shared Pydantic models for the API
Contains all the data models used across different API endpoints
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel

class ContactInfo(BaseModel):
    number: Optional[str] = None
    email: Optional[str] = None

class BookAppointmentRequest(BaseModel):
    name: str
    contact: Union[str, Dict[str, Any]]  # Accept both string and dict
    day: str
    date: str  # Added date field
    dob: Optional[str] = None  # Added patient date of birth
    time: str
    is_new_patient: bool
    service_booked: str
    doctor_for_appointment: str
    patient_details: Optional[Union[str, Dict[str, Any]]] = None  # Accept both string and dict

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
