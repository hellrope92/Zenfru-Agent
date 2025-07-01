"""
Modular FastAPI backend for BrightSmile Dental Clinic AI Assistant
Uses actual JSON files with simplified logic and console logging
Updated to use GetKolla service for actual appointment booking
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import uvicorn
import os
from pathlib import Path

# Import services
from services.getkolla_service import GetKollaService
from services.availability_service import AvailabilityService

# Import API routers
from api import (
    schedule_api, 
    booking_api, 
    patient_services_api, 
    debug_api,
    appointment_details_api,
    availability_api,
    get_appointment_api,
    get_contact_api,
    new_patient_form_api,
    callback_api,
    conversation_log_api,
    reschedule_api,
    confirm_api,
    get_current
)

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

# ========== RUNTIME STORAGE ==========

# Runtime storage for testing (not persistent)
APPOINTMENTS = []
CALLBACK_REQUESTS = []
CONVERSATION_LOGS = []

# ========== DEPENDENCY PROVIDERS ==========

def get_getkolla_service() -> GetKollaService:
    """Dependency provider for GetKolla service"""
    return getkolla_service

def get_schedule() -> Dict:
    """Dependency provider for schedule data"""
    return SCHEDULE

def get_bookings() -> List:
    """Dependency provider for bookings data"""
    return BOOKINGS

def get_knowledge_base() -> Dict:
    """Dependency provider for knowledge base data"""
    return KNOWLEDGE_BASE

def get_callback_requests() -> List:
    """Dependency provider for callback requests storage"""
    return CALLBACK_REQUESTS

def get_conversation_logs() -> List:
    """Dependency provider for conversation logs storage"""
    return CONVERSATION_LOGS

# ========== FASTAPI APP ==========

app = FastAPI(
    title="BrightSmile Dental AI Assistant - Modular Backend",
    description="Modular backend using actual JSON files with console logging",
    version="2.0.0"
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

# ========== ENHANCED API ENDPOINTS WITH DEPENDENCY INJECTION ==========

# Create wrapper functions for dependency injection
def create_schedule_endpoints():
    """Create schedule endpoints with proper dependency injection"""
    
    @app.get("/api/availability", tags=["schedule"])
    async def get_availability(
        date: str,
        getkolla_service: GetKollaService = Depends(get_getkolla_service)
    ):
        """Simple availability API - takes a date, returns 3 days of availability"""
        return await schedule_api.get_availability(date, getkolla_service)

def create_booking_endpoints():
    """Create booking endpoints with proper dependency injection"""
    
    @app.post("/api/book_patient_appointment", tags=["booking"])
    async def book_patient_appointment(
        request: booking_api.BookAppointmentRequest,
        getkolla_service: GetKollaService = Depends(get_getkolla_service)
    ):
        """Book a new patient appointment using GetKolla API"""
        return await booking_api.book_patient_appointment(request, getkolla_service)
    
    @app.post("/api/reschedule_patient_appointment", tags=["booking"])
    async def reschedule_patient_appointment(request: booking_api.RescheduleRequest):
        """Reschedule an existing patient appointment (print only)"""
        return await booking_api.reschedule_patient_appointment(request)

def create_patient_services_endpoints():
    """Create patient services endpoints with proper dependency injection"""
    
    @app.post("/api/send_new_patient_form", tags=["patient-services"])
    async def send_new_patient_form(
        request: patient_services_api.SendFormRequest,
        knowledge_base: Dict = Depends(get_knowledge_base)
    ):
        """Send new patient forms to the provided phone number"""
        return await patient_services_api.send_new_patient_form(request, knowledge_base)
    
    @app.post("/api/log_callback_request", tags=["patient-services"])
    async def log_callback_request(
        request: patient_services_api.CallbackRequest,
        callback_requests: List = Depends(get_callback_requests)
    ):
        """Log a callback request for staff follow-up"""
        return await patient_services_api.log_callback_request(request, callback_requests)
    
    @app.post("/api/answer_faq_query", tags=["patient-services"])
    async def answer_faq_query(
        request: patient_services_api.FAQRequest,
        knowledge_base: Dict = Depends(get_knowledge_base)
    ):
        """Answer frequently asked questions using knowledge base"""
        return await patient_services_api.answer_faq_query(request, knowledge_base)
    
    @app.post("/api/log_conversation_summary", tags=["patient-services"])
    async def log_conversation_summary(
        request: patient_services_api.ConversationSummaryRequest,
        conversation_logs: List = Depends(get_conversation_logs)
    ):
        """Log a comprehensive summary of the conversation"""
        return await patient_services_api.log_conversation_summary(request, conversation_logs)

def create_debug_endpoints():
    """Create debug endpoints with proper dependency injection"""
    
    @app.get("/api/health", tags=["debug"])
    async def health_check(
        getkolla_service: GetKollaService = Depends(get_getkolla_service),
        schedule: Dict = Depends(get_schedule),
        bookings: List = Depends(get_bookings),
        knowledge_base: Dict = Depends(get_knowledge_base)
    ):
        """Health check endpoint"""
        return await debug_api.health_check(getkolla_service, schedule, bookings, knowledge_base)
    
    @app.get("/api/getkolla/test", tags=["debug"])
    async def test_getkolla_api(getkolla_service: GetKollaService = Depends(get_getkolla_service)):
        """Test GetKolla API connectivity and data fetch"""
        return await debug_api.test_getkolla_api(getkolla_service)
    
    @app.get("/api/debug/schedule", tags=["debug"])
    async def get_debug_schedule(
        schedule: Dict = Depends(get_schedule),
        bookings: List = Depends(get_bookings)
    ):
        """Debug endpoint to view the clinic schedule and bookings"""
        return await debug_api.get_debug_schedule(schedule, bookings)
    
    @app.get("/api/debug/callbacks", tags=["debug"])
    async def get_debug_callbacks(callback_requests: List = Depends(get_callback_requests)):
        """Debug endpoint to view all callback requests"""
        return await debug_api.get_debug_callbacks(callback_requests)
    
    @app.get("/api/debug/conversations", tags=["debug"])
    async def get_debug_conversations(conversation_logs: List = Depends(get_conversation_logs)):
        """Debug endpoint to view all conversation logs"""
        return await debug_api.get_debug_conversations(conversation_logs)
    
    @app.get("/api/debug/knowledge_base", tags=["debug"])
    async def get_debug_knowledge_base(knowledge_base: Dict = Depends(get_knowledge_base)):
        """Debug endpoint to view the knowledge base"""
        return await debug_api.get_debug_knowledge_base(knowledge_base)
    
    @app.get("/healthz", tags=["debug"])
    async def render_health_check():
        """Health check endpoint for Render deployment"""
        return {"status": "ok"}

# Initialize all endpoints
create_schedule_endpoints()
create_booking_endpoints()
create_patient_services_endpoints()
create_debug_endpoints()

# Include all new router-based APIs
app.include_router(appointment_details_api.router)
app.include_router(availability_api.router)
app.include_router(get_appointment_api.router)
app.include_router(get_contact_api.router)
app.include_router(new_patient_form_api.router)
app.include_router(callback_api.router)
app.include_router(conversation_log_api.router)
app.include_router(reschedule_api.router)
app.include_router(confirm_api.router)
app.include_router(get_current.router, prefix="/api", tags=["datetime"])  # Add this line
# ========== MAIN ==========

if __name__ == "__main__":    
    print("🦷 Starting BrightSmile Dental AI Assistant - Modular Backend")
    print("📋 Available endpoints organized by modules:")
    print()
    print("📅 Schedule & Availability Module:")
    print("   - GET  /api/availability?date=YYYY-MM-DD (returns 3 days)")
    print("   - GET  /api/availability/refresh")
    print()
    print("📝 Booking & Reschedule Module:")
    print("   - POST /api/book_patient_appointment")
    print("   - POST /api/reschedule_patient_appointment (flexible agent format)")
    print("   - POST /api/reschedule_appointment (legacy)")
    print()
    print("📋 Core Patient APIs (with local caching):")
    print("   - POST /api/get_appointment (name, dob) - 24hr cache")
    print("   - GET  /api/get_appointment/{name}/{dob}")
    print("   - POST /api/get_contact (name, dob) - 24hr cache")
    print("   - GET  /api/get_contact/{name}/{dob}")
    print()
    print("👥 Patient Services Module:")
    print("   - POST /api/send_new_patient_form")
    print("   - POST /api/log_callback_request")
    print("   - GET  /api/callback_requests")
    print("   - PUT  /api/callback_requests/{id}/status")
    print("   - POST /api/log_conversation_summary")
    print("   - GET  /api/conversation_logs")
    print("   - GET  /api/conversation_logs/analytics")
    print()
    print("🔧 Debug Module:")
    print("   - GET  /api/health")
    print("   - GET  /api/getkolla/test")
    print("   - GET  /api/debug/* (for testing)")
    print()
    print(f"📊 Data Status:")
    print(f"   Schedule: {len(SCHEDULE)} days loaded")
    print(f"   Existing Bookings: {len(BOOKINGS)} appointments")
    print(f"   Knowledge Base: {len(KNOWLEDGE_BASE)} sections")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
