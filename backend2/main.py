"""
Simple FastAPI backend for BrightSmile Dental Clinic AI Assistant
Uses actual JSON files with simplified logic and console logging
Updated to use GetKolla service for actual appointment booking
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from pathlib import Path
from services.getkolla_service import GetKollaService
from services.availability_service import AvailabilityService

# ========== PYDANTIC MODELS ==========

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

# ========== DATA LOADING ==========

def load_json_file(filename: str) -> Dict[str, Any]:
    """Load JSON file from parent directory"""
    file_path = Path(__file__).parent.parent / filename
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {filename} not found at {file_path}")
        return {}
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON in {filename}")
        return {}

# Load data files
SCHEDULE = load_json_file("schedule.json")
BOOKINGS = load_json_file("bookings.json")
KNOWLEDGE_BASE = load_json_file("knowledge_base.json")

print(f"📁 Loaded data:")
print(f"   Schedule: {len(SCHEDULE)} days configured")
print(f"   Bookings: {len(BOOKINGS)} existing appointments")
print(f"   Knowledge Base: {len(KNOWLEDGE_BASE)} sections loaded")

# ========== HELPER FUNCTIONS ==========

def get_next_n_days(n: int = 5) -> List[str]:
    """Get the next N days starting from tomorrow"""
    today = datetime.now()
    days = []
    for i in range(1, n + 1):  # Start from tomorrow
        future_date = today + timedelta(days=i)
        day_name = future_date.strftime("%A")
        days.append(day_name)
    return days

def get_available_slots_for_day(day: str) -> List[Dict[str, str]]:
    """Get available time slots for a specific day"""
    if day not in SCHEDULE:
        return []
    
    day_info = SCHEDULE[day]
    
    # Check if clinic is closed
    if day_info.get("status") == "Closed":
        return []
    
    # Generate time slots based on open/close times
    open_time = day_info.get("open", "9:00 AM")
    close_time = day_info.get("close", "5:00 PM")
    doctor = day_info.get("doctor", "Available Doctor")
    
    # Simple slot generation (every hour)
    slots = []
    if "9:00 AM" in open_time:
        base_slots = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"]
        
        # Filter based on close time
        if "4:00 PM" in close_time:
            base_slots = [slot for slot in base_slots if slot not in ["5:00 PM"]]
        elif "5:00 PM" in close_time:
            base_slots = [slot for slot in base_slots if slot not in []]
        elif "6:00 PM" in close_time:
            base_slots.append("5:00 PM")
        
        for slot in base_slots:
            # Check if slot is already booked
            is_booked = any(
                booking.get("day") == day and booking.get("time") == slot 
                for booking in BOOKINGS
            )
            
            if not is_booked:
                slots.append({
                    "time": slot,
                    "doctor": doctor,
                    "duration_minutes": 30
                })
    
    return slots

def search_knowledge_base(query: str) -> tuple[str, str]:
    """Search knowledge base for relevant information"""
    query_lower = query.lower()
    clinic_info = KNOWLEDGE_BASE.get("clinic_info", {})
    
    # Address/Location queries
    if any(word in query_lower for word in ["address", "location", "where", "find"]):
        return clinic_info.get("address", "Address not available"), "clinic_address"
    
    # Parking queries
    if any(word in query_lower for word in ["parking", "park"]):
        return clinic_info.get("parking_info", "Parking information not available"), "parking_info"
    
    # Hours queries
    if any(word in query_lower for word in ["hours", "open", "closed", "time"]):
        hours = clinic_info.get("office_hours_detailed", {})
        hours_text = "\n".join([f"{day}: {time}" for day, time in hours.items()])
        return f"Our office hours are:\n{hours_text}", "office_hours"
    
    # Services queries
    if any(word in query_lower for word in ["service", "treatment", "procedure", "do you do"]):
        services = clinic_info.get("services_offered_summary", [])
        services_text = ", ".join(services)
        return f"We offer the following services: {services_text}", "services"
    
    # Pricing queries
    if any(word in query_lower for word in ["cost", "price", "fee", "how much"]):
        pricing = clinic_info.get("service_pricing", {})
        pricing_text = "\n".join([f"{service}: {price}" for service, price in pricing.items()])
        return f"Here are some of our prices:\n{pricing_text}", "pricing"
    
    # Doctor queries
    if any(word in query_lower for word in ["doctor", "dentist", "who", "staff"]):
        doctors = clinic_info.get("dentist_team", [])
        doctor_info = []
        for doc in doctors:
            doctor_info.append(f"{doc['name']} - {doc['working_days_hours']}")
        return "\n".join(doctor_info), "doctor_info"
    
    # Default response
    return "I don't have specific information about that. Please call our office for more details.", "general"

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

# ========== RUNTIME STORAGE ==========

# Runtime storage for testing (not persistent)
APPOINTMENTS = []
CALLBACK_REQUESTS = []
CONVERSATION_LOGS = []

# ========== FASTAPI APP ==========

app = FastAPI(
    title="BrightSmile Dental AI Assistant - Simple Backend",
    description="Simple backend using actual JSON files with console logging",
    version="1.0.0"
)

# Initialize GetKolla service
getkolla_service = GetKollaService()

# Initialize Availability service (assuming this exists)
try:
    from services.availability_service import SimpleAvailabilityService
    simple_availability_service = SimpleAvailabilityService()
except ImportError:
    print("⚠️ SimpleAvailabilityService not found, using fallback")
    simple_availability_service = None

# ========== TOOL ENDPOINTS ==========

@app.get("/api/get_current_day")
async def get_current_day():
    """Get the current day of the week"""
    current_day = datetime.now().strftime("%A")
    current_date = datetime.now().strftime("%Y-%m-%d")
    print(f"🗓️ GET_CURRENT_DAY: {current_day}")
    
    return {
        "day": current_day,
        "date": current_date,
    }

@app.post("/api/check_available_slots")
async def check_available_slots(request: CheckSlotsRequest):
    """Check available appointment slots for next 7 days using GetKolla API"""
    current_day = datetime.now().strftime("%A")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"🔍 CHECK_AVAILABLE_SLOTS:")
    print(f"   Current Day: {current_day} ({current_date})")
    print(f"   Checking next 7 days with GetKolla API integration...")
    
    try:
        # Get available slots from GetKolla service
        available_slots_by_day = getkolla_service.get_available_slots_next_7_days()
        
        # Transform the data to match the expected format
        all_available_slots = []
        days_checked = []
        
        for day_info, slots in available_slots_by_day.items():
            day_name = day_info.split(' (')[0]  # Extract day name from "Monday (2025-06-18)"
            days_checked.append(day_name)
            
            for slot_time in slots:
                all_available_slots.append({
                    "day": day_name,
                    "time": slot_time,
                    "available": True,
                    "doctor": getkolla_service.schedule.get(day_name.split()[0], {}).get("doctor", "Available Doctor")
                })
        
        print(f"   ✅ Total available slots found: {len(all_available_slots)}")
        print(f"   📅 Days with availability: {len(available_slots_by_day)}")
        
        return {
            "available_slots": all_available_slots,
            "days_checked": days_checked,
            "current_day": current_day,
            "slots_by_day": available_slots_by_day,
            "total_slots": len(all_available_slots)
        }
        
    except Exception as e:
        print(f"   ❌ Error fetching available slots: {e}")
        # Fallback to original logic if GetKolla service fails
        next_days = get_next_n_days(5)
        all_available_slots = []
        
        for day in next_days:
            day_slots = get_available_slots_for_day(day)
            if day_slots:
                for slot in day_slots:
                    slot["day"] = day
                    all_available_slots.append(slot)
        
        return {
            "available_slots": all_available_slots,
            "days_checked": next_days,
            "current_day": current_day,
            "error": "GetKolla API unavailable, using fallback logic"
        }

@app.post("/api/book_patient_appointment")
async def book_patient_appointment(request: BookAppointmentRequest):
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

@app.post("/api/reschedule_patient_appointment")
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

@app.post("/api/send_new_patient_form")
async def send_new_patient_form(request: SendFormRequest):
    """Send new patient forms to the provided phone number"""
    
    form_url = KNOWLEDGE_BASE.get("intake_form_url", "https://forms.brightsmile-dental.com/new-patient")
    
    print(f"📱 SEND_NEW_PATIENT_FORM:")
    print(f"   Phone: {request.contact_number}")
    print(f"   Form URL: {form_url}")
    print(f"   ✅ [SIMULATION] SMS would be sent!")
    
    return {
        "success": True,
        "message": f"[SIMULATION] New patient forms would be sent to {request.contact_number}",
        "form_url": form_url
    }

@app.post("/api/log_callback_request")
async def log_callback_request(request: CallbackRequest):
    """Log a callback request for staff follow-up"""
    
    print(f"📞 LOG_CALLBACK_REQUEST:")
    print(f"   Name: {request.name}")
    print(f"   Phone: {request.contact_number}")
    print(f"   Preferred Time: {request.preferred_callback_time}")
    
    # Generate callback ID
    callback_id = f"CB-{uuid.uuid4().hex[:8].upper()}"
    
    # Store in runtime storage
    callback_record = {
        "callback_id": callback_id,
        "name": request.name,
        "contact_number": request.contact_number,
        "preferred_callback_time": request.preferred_callback_time,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    CALLBACK_REQUESTS.append(callback_record)
    
    print(f"   ✅ Callback request logged successfully!")
    print(f"   📋 Callback ID: {callback_id}")
    
    return {
        "success": True,
        "callback_id": callback_id,
        "message": f"Callback request logged for {request.name}"
    }

@app.post("/api/answer_faq_query")
async def answer_faq_query(request: FAQRequest):
    """Answer frequently asked questions using knowledge base"""
    
    print(f"❓ ANSWER_FAQ_QUERY:")
    print(f"   Query: {request.query}")
    
    # Search knowledge base
    answer, source = search_knowledge_base(request.query)
    
    print(f"   💡 Answer: {answer}")
    print(f"   📚 Source: {source}")
    
    return {
        "success": True,
        "query": request.query,
        "answer": answer,
        "source": source
    }

@app.post("/api/log_conversation_summary")
async def log_conversation_summary(request: ConversationSummaryRequest):
    """Log a comprehensive summary of the conversation"""
    
    print(f"📝 LOG_CONVERSATION_SUMMARY:")
    if request.summary:
        print(f"   Summary: {request.summary}")
    print(f"   Patient: {request.patient_name or 'Unknown'}")
    print(f"   Primary Intent: {request.primary_intent}")
    print(f"   Outcome: {request.outcome}")
    if request.appointment_details:
        print(f"   Appointment Details: {request.appointment_details}")
    if request.call_duration:
        print(f"   Call Duration: {request.call_duration} seconds")
    if request.additional_notes:
        print(f"   Notes: {request.additional_notes}")
    
    # Generate summary ID
    summary_id = f"CONV-{uuid.uuid4().hex[:8].upper()}"
    
    # Store in runtime storage
    conversation_record = {
        "summary_id": summary_id,
        "summary": request.summary,
        "patient_name": request.patient_name,
        "primary_intent": request.primary_intent,
        "appointment_details": request.appointment_details,
        "outcome": request.outcome,
        "call_duration": request.call_duration,
        "additional_notes": request.additional_notes,
        "logged_at": datetime.now().isoformat()
    }
    
    CONVERSATION_LOGS.append(conversation_record)
    
    print(f"   ✅ Conversation summary logged successfully!")
    print(f"   📋 Summary ID: {summary_id}")
    
    return {
        "success": True,
        "summary_id": summary_id,
        "message": "Conversation summary logged successfully"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    # Test GetKolla API connectivity
    kolla_status = getkolla_service.health_check()
    
    return {
        "status": "healthy",
        "service": "BrightSmile Dental AI Assistant",
        "timestamp": datetime.now().isoformat(),
        "data_loaded": {
            "schedule": len(SCHEDULE) > 0,
            "bookings": len(BOOKINGS) > 0,
            "knowledge_base": len(KNOWLEDGE_BASE) > 0
        },
        "getkolla_api": {
            "status": "connected" if kolla_status else "disconnected",
            "available": kolla_status
        }
    }

@app.get("/api/getkolla/test")
async def test_getkolla_api():
    """Test GetKolla API connectivity and data fetch"""
    print("🔧 TESTING_GETKOLLA_API:")
    
    try:
        # Test API connectivity
        health_status = getkolla_service.health_check()
        print(f"   Health Check: {'✅ Connected' if health_status else '❌ Failed'}")
        
        # Test fetching appointments
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)
        appointments = getkolla_service.get_booked_appointments(start_date, end_date)
        print(f"   Appointments Found: {len(appointments)}")
        
        # Test available slots calculation
        available_slots = getkolla_service.get_available_slots_next_7_days()
        print(f"   Available Slots: {len(available_slots)} days with slots")
        
        return {
            "getkolla_api": {
                "health_check": health_status,
                "appointments_found": len(appointments),
                "available_slots_days": len(available_slots),
                "sample_appointments": appointments[:2] if appointments else [],
                "available_slots_summary": {day: len(slots) for day, slots in available_slots.items()}
            },
            "status": "success" if health_status else "api_unavailable"
        }
        
    except Exception as e:
        print(f"   ❌ Error testing GetKolla API: {e}")
        return {
            "getkolla_api": {
                "error": str(e),
                "health_check": False
            },
            "status": "error"
        }

@app.get("/api/debug/schedule")
async def get_schedule():
    """Debug endpoint to view the clinic schedule and bookings"""
    return {
        "schedule": SCHEDULE,
        "existing_bookings": BOOKINGS,
        "total_existing_bookings": len(BOOKINGS)
    }

@app.get("/api/debug/callbacks")
async def get_callbacks():
    """Debug endpoint to view all callback requests"""
    return {
        "callbacks": CALLBACK_REQUESTS,
        "total": len(CALLBACK_REQUESTS)
    }

@app.get("/api/debug/conversations")
async def get_conversations():
    """Debug endpoint to view all conversation logs"""
    return {
        "conversations": CONVERSATION_LOGS,
        "total": len(CONVERSATION_LOGS)
    }

@app.get("/api/debug/knowledge_base")
async def get_knowledge_base():
    """Debug endpoint to view the knowledge base"""
    return {
        "knowledge_base": KNOWLEDGE_BASE,
        "clinic_name": KNOWLEDGE_BASE.get("clinic_info", {}).get("name", "Unknown"),
        "services_count": len(KNOWLEDGE_BASE.get("clinic_info", {}).get("services_offered_summary", [])),
        "doctors_count": len(KNOWLEDGE_BASE.get("clinic_info", {}).get("dentist_team", []))
    }

@app.get("/api/get_schedule")
async def get_schedule(days: int = 7):
    """Get available appointment schedule for the next N days using GetKolla API"""
    print(f"📅 GET_SCHEDULE: Fetching schedule for next {days} days")
    
    try:
        if days == 7:
            # Use the optimized method for 7 days
            available_slots_by_day = getkolla_service.get_available_slots_next_7_days()
            
            # Transform to a more structured format
            schedule_data = {}
            total_available_slots = 0
            
            for day_info, slots in available_slots_by_day.items():
                # Extract day name and date from "Monday (2025-06-18)" format
                parts = day_info.split(' (')
                day_name = parts[0]
                date_str = parts[1].rstrip(')')
                
                # Get doctor info from schedule
                day_schedule = getkolla_service.schedule.get(day_name, {})
                doctor = day_schedule.get("doctor", "Available Doctor")
                open_time = day_schedule.get("open", "9:00 AM")
                close_time = day_schedule.get("close", "5:00 PM")
                
                schedule_data[date_str] = {
                    "day": day_name,
                    "date": date_str,
                    "status": "Open" if slots else "No availability",
                    "open_time": open_time,
                    "close_time": close_time,
                    "doctor": doctor,
                    "available_slots": slots,
                    "total_slots": len(slots)
                }
                total_available_slots += len(slots)
        else:
            # For custom number of days, calculate individually
            schedule_data = {}
            total_available_slots = 0
            today = datetime.now()
            
            for i in range(days):
                target_date = today + timedelta(days=i)
                date_str = target_date.strftime("%Y-%m-%d")
                day_name = target_date.strftime("%A")
                
                # Get available slots for this specific date
                slots = getkolla_service.get_available_slots_for_date(target_date)
                
                # Get doctor info from schedule
                day_schedule = getkolla_service.schedule.get(day_name, {})
                doctor = day_schedule.get("doctor", "Available Doctor")
                open_time = day_schedule.get("open", "9:00 AM")
                close_time = day_schedule.get("close", "5:00 PM")
                status = day_schedule.get("status", "Open")
                
                if status == "Closed":
                    schedule_data[date_str] = {
                        "day": day_name,
                        "date": date_str,
                        "status": "Closed",
                        "open_time": None,
                        "close_time": None,
                        "doctor": None,
                        "available_slots": [],
                        "total_slots": 0
                    }
                else:
                    schedule_data[date_str] = {
                        "day": day_name,
                        "date": date_str,
                        "status": "Open" if slots else "No availability",
                        "open_time": open_time,
                        "close_time": close_time,
                        "doctor": doctor,
                        "available_slots": slots,
                        "total_slots": len(slots)
                    }
                    total_available_slots += len(slots)
        
        print(f"   ✅ Schedule generated successfully")
        print(f"   📊 Total available slots: {total_available_slots}")
        print(f"   📅 Days with availability: {len([d for d in schedule_data.values() if d['total_slots'] > 0])}")
        
        return {
            "success": True,
            "days_requested": days,
            "schedule": schedule_data,
            "summary": {
                "total_available_slots": total_available_slots,
                "days_with_availability": len([d for d in schedule_data.values() if d['total_slots'] > 0]),
                "days_closed": len([d for d in schedule_data.values() if d['status'] == 'Closed']),
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        print(f"   ❌ Error generating schedule: {e}")
        return {
            "success": False,
            "error": str(e),
            "schedule": {},
            "summary": {
                "total_available_slots": 0,
                "days_with_availability": 0,
                "days_closed": 0,
                "generated_at": datetime.now().isoformat()
            }
        }