"""
Booking-related API endpoints
Handles appointment booking, rescheduling, and booking management
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, HTTPException

# Import shared models
from .models import BookAppointmentRequest, RescheduleRequest, ContactInfo

# Import dependencies (will be injected from main.py)
from services.getkolla_service import GetKollaService

router = APIRouter(prefix="/api", tags=["booking"])

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

async def book_patient_appointment(request: BookAppointmentRequest, getkolla_service: GetKollaService):
    """Book a new patient appointment using GetKolla API"""
    
    print(f"📅 BOOK_PATIENT_APPOINTMENT:")
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
        # Parse contact information
        contact_info = parse_contact_info(request.contact)
        
        # Convert appointment time to datetime objects
        start_datetime = convert_time_to_datetime(request.date, request.time)
        
        # Calculate end time based on service type (default 30 minutes)
        service_duration = getkolla_service._get_service_duration(request.service_booked)
        end_datetime = start_datetime + timedelta(minutes=service_duration)
        
        # Prepare appointment data for GetKolla API
        appointment_data = {
            "name": request.name,
            "contact": contact_info.get("phone", ""),
            "email": contact_info.get("email", ""),
            "start_time": start_datetime.isoformat(),
            "end_time": end_datetime.isoformat(),
            "service_booked": request.service_booked,
            "is_new_patient": request.is_new_patient,
            "dob": request.dob,
            "patient_details": request.patient_details
        }
        
        # Attempt to book the appointment through GetKolla API
        booking_success = getkolla_service.book_appointment(appointment_data)
        
        if booking_success:
            # Generate appointment ID for success response
            appointment_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
            
            print(f"   ✅ Appointment successfully booked through GetKolla API!")
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
            print(f"   ❌ Failed to book appointment through GetKolla API")
            return {
                "success": False,
                "message": f"Failed to book appointment for {request.name}. Please try again or contact the clinic directly.",
                "status": "failed",
                "error": "booking_failed"
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
    """Reschedule an existing patient appointment (print only)"""
    
    print(f"🔄 RESCHEDULE_PATIENT_APPOINTMENT:")
    print(f"   Name: {request.name}")
    print(f"   DOB: {request.dob}")
    print(f"   Reason: {request.reason}")
    print(f"   New Slot: {request.new_slot}")
    print(f"   ✅ [SIMULATION] Appointment would be rescheduled!")
    
    return {
        "success": True,
        "message": f"[SIMULATION] Appointment would be rescheduled for {request.name}",
        "new_appointment_details": {
            "name": request.name,
            "new_slot": request.new_slot,
            "reason": request.reason,
            "timestamp": datetime.now().isoformat()
        }
    }
