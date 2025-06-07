"""
Simple FastAPI backend for BrightSmile Dental Clinic AI Assistant
Uses actual JSON files with simplified logic and console logging
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from pathlib import Path

# ========== PYDANTIC MODELS ==========

class BookAppointmentRequest(BaseModel):
    name: str
    contact: str
    day: str
    date: str  # Added date field
    dob: Optional[str] = None  # Added patient date of birth
    time: str
    is_new_patient: bool
    service_booked: str
    doctor_for_appointment: str
    patient_details: Optional[str] = None

class CheckSlotsRequest(BaseModel):
    day: str

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
    """Check available appointment slots for next 5 days"""
    current_day = datetime.now().strftime("%A")
    next_days = get_next_n_days(5)
    
    print(f"🔍 CHECK_AVAILABLE_SLOTS:")
    print(f"   Current Day: {current_day}")
    print(f"   Checking next 5 days: {next_days}")
    
    all_available_slots = []
    
    for day in next_days:
        day_slots = get_available_slots_for_day(day)
        if day_slots:
            print(f"   📅 {day}: {len(day_slots)} slots available")
            for slot in day_slots:
                slot["day"] = day  # Add day to each slot
                all_available_slots.append(slot)
        else:
            print(f"   📅 {day}: No slots available (closed or fully booked)")
    
    print(f"   ✅ Total available slots found: {len(all_available_slots)}")
    
    return {
        "available_slots": all_available_slots,
        "days_checked": next_days,
        "current_day": current_day
    }

@app.post("/api/book_patient_appointment")
async def book_patient_appointment(request: BookAppointmentRequest):
    """Book a new patient appointment (print only)"""
    
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
    print(f"   Patient Details: {request.patient_details} )")
    print(f"   ✅ [SIMULATION] Appointment would be booked!")
    
    # Generate appointment ID for simulation
    appointment_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
    
    return {
        "success": True,
        "appointment_id": appointment_id,
        "message": f"[SIMULATION] Appointment would be booked for {request.name}",
        "appointment_details": {
            "name": request.name,
            "contact": request.contact,
            "day": request.day,
            "date": request.date,
            "dob": request.dob,
            "time": request.time,
            "service": request.service_booked,
            "doctor": request.doctor_for_appointment,
            "patient_details": request.patient_details
        }
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

# ========== UTILITY ENDPOINTS ==========

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "BrightSmile Dental AI Assistant",
        "timestamp": datetime.now().isoformat(),
        "data_loaded": {
            "schedule": len(SCHEDULE) > 0,
            "bookings": len(BOOKINGS) > 0,
            "knowledge_base": len(KNOWLEDGE_BASE) > 0
        }
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

# ========== MAIN ==========

if __name__ == "__main__":
    print("🦷 Starting BrightSmile Dental AI Assistant - Simple Backend")
    print("📋 Available endpoints:")
    print("   - GET  /api/get_current_day")
    print("   - POST /api/check_available_slots (shows next 5 days)")
    print("   - POST /api/book_patient_appointment (print only)")
    print("   - POST /api/reschedule_patient_appointment (print only)")
    print("   - POST /api/send_new_patient_form")
    print("   - POST /api/log_callback_request")
    print("   - POST /api/answer_faq_query (uses knowledge_base.json)")
    print("   - POST /api/log_conversation_summary")
    print("   - GET  /api/health")
    print("   - GET  /api/debug/* (for testing)")
    print()
    print(f"📊 Data Status:")
    print(f"   Schedule: {len(SCHEDULE)} days loaded")
    print(f"   Existing Bookings: {len(BOOKINGS)} appointments")
    print(f"   Knowledge Base: {len(KNOWLEDGE_BASE)} sections")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
