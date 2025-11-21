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
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from pathlib import Path
import logging
from services.service_status_sheet import update_fastapi_backend

# Import services
from services.getkolla_service import GetKollaService
from services.availability_service import AvailabilityService
from services.patient_interaction_logger import patient_logger
from services.supabase_log_handler import SupabaseLogHandler
from services.auth_service import require_api_key

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
    get_current,
    reporting_api,
    save_transcripts_api,
    transcript_summary_api,
    auth_api,
    otp_api
)


# ========== LOGGING SETUP ==========
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    if os.getenv("RENDER", "false").lower() == "true":
        handler = SupabaseLogHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        logging.basicConfig(level=logging.INFO)

setup_logging()

# ========== DATA LOADING ==========

def load_json_file(filename: str) -> Dict[str, Any]:
    """Load JSON file from parent directory"""
    file_path = Path(__file__).parent.parent / filename
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"❌ Error: {filename} not found at {file_path}")
        return {}
    except json.JSONDecodeError:
        logging.error(f"❌ Error: Invalid JSON in {filename}")
        return {}

# Load data files
SCHEDULE = load_json_file("schedule.json")
BOOKINGS = load_json_file("bookings.json")
KNOWLEDGE_BASE = load_json_file("knowledge_base.json")

logging.info(f"📁 Loaded data:")
logging.info(f"   Schedule: {len(SCHEDULE)} days configured")
logging.info(f"   Bookings: {len(BOOKINGS)} existing appointments")
logging.info(f"   Knowledge Base: {len(KNOWLEDGE_BASE)} sections loaded")

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

# Mount the directory containing the logo as a static directory
app.mount("/static", StaticFiles(directory=Path(__file__).parent), name="static")

# Backend status middleware (updates sheet row for FASTAPI Backend)
@app.middleware("http")
async def backend_status_middleware(request, call_next):
    path = request.url.path
    try:
        response = await call_next(request)
        if response.status_code < 400:
            update_fastapi_backend(True, f"{path} OK")
        else:
            update_fastapi_backend(False, f"{path} HTTP {response.status_code}")
        return response
    except Exception as e:
        update_fastapi_backend(False, f"{path} Exception: {e.__class__.__name__}")
        raise

# Initialize GetKolla service
getkolla_service = GetKollaService()

# Initialize Availability service (assuming this exists)
try:
    from services.availability_service import SimpleAvailabilityService
    simple_availability_service = SimpleAvailabilityService()
except ImportError:
    logging.warning("⚠️ SimpleAvailabilityService not found, using fallback")
    simple_availability_service = None

# ========== ENHANCED API ENDPOINTS WITH DEPENDENCY INJECTION ==========

# Create wrapper functions for dependency injection
def create_schedule_endpoints():
    """Create schedule endpoints with proper dependency injection"""
    
    @app.get("/api/availability", tags=["schedule"])
    async def get_availability(date: str, iscleaning: bool = False, authenticated: bool = Depends(require_api_key)):
        """Enhanced availability API - takes a date and iscleaning flag, returns 3 days of availability"""
        return await schedule_api.get_availability(date, iscleaning)
    
    @app.get("/api/debug/appointments", tags=["debug"])
    async def debug_appointments(date: str, iscleaning: bool = False, authenticated: bool = Depends(require_api_key)):
        """Debug endpoint to show raw appointment data with provider filtering"""
        return await schedule_api.debug_appointments(date, iscleaning)

def create_booking_endpoints():
    """Create booking endpoints with proper dependency injection"""
    
    @app.post("/api/book_patient_appointment", tags=["booking"])
    async def book_patient_appointment(
        request: booking_api.BookAppointmentRequest,
        getkolla_service: GetKollaService = Depends(get_getkolla_service),
        authenticated: bool = Depends(require_api_key)
    ):
        """Book a new patient appointment using GetKolla API"""
        return await booking_api.book_patient_appointment(request, getkolla_service)

def create_patient_services_endpoints():
    """Create patient services endpoints with proper dependency injection"""
    
    @app.post("/api/send_new_patient_form", tags=["patient-services"])
    async def send_new_patient_form(
        request: patient_services_api.SendFormRequest,
        knowledge_base: Dict = Depends(get_knowledge_base),
        authenticated: bool = Depends(require_api_key)
    ):
        """Send new patient forms to the provided phone number"""
        return await patient_services_api.send_new_patient_form(request, knowledge_base)
    
    @app.post("/api/log_callback_request", tags=["patient-services"])
    async def log_callback_request(
        request: patient_services_api.CallbackRequest,
        callback_requests: List = Depends(get_callback_requests),
        authenticated: bool = Depends(require_api_key)
    ):
        """Log a callback request for staff follow-up"""
        return await patient_services_api.log_callback_request(request, callback_requests)
    
    @app.post("/api/answer_faq_query", tags=["patient-services"])
    async def answer_faq_query(
        request: patient_services_api.FAQRequest,
        knowledge_base: Dict = Depends(get_knowledge_base),
        authenticated: bool = Depends(require_api_key)
    ):
        """Answer frequently asked questions using knowledge base"""
        return await patient_services_api.answer_faq_query(request, knowledge_base)
    
    @app.post("/api/log_conversation_summary", tags=["patient-services"])
    async def log_conversation_summary(
        request: patient_services_api.ConversationSummaryRequest,
        conversation_logs: List = Depends(get_conversation_logs),
        authenticated: bool = Depends(require_api_key)
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
        knowledge_base: Dict = Depends(get_knowledge_base),
        authenticated: bool = Depends(require_api_key)
    ):
        """Health check endpoint"""
        return await debug_api.health_check(getkolla_service, schedule, bookings, knowledge_base)
    
    @app.get("/api/getkolla/test", tags=["debug"])
    async def test_getkolla_api(getkolla_service: GetKollaService = Depends(get_getkolla_service), authenticated: bool = Depends(require_api_key)):
        """Test GetKolla API connectivity and data fetch"""
        return await debug_api.test_getkolla_api(getkolla_service)
    
    @app.get("/api/debug/schedule", tags=["debug"])
    async def get_debug_schedule(
        schedule: Dict = Depends(get_schedule),
        bookings: List = Depends(get_bookings),
        authenticated: bool = Depends(require_api_key)
    ):
        """Debug endpoint to view the clinic schedule and bookings"""
        return await debug_api.get_debug_schedule(schedule, bookings)
    
    @app.get("/api/debug/callbacks", tags=["debug"])
    async def get_debug_callbacks(callback_requests: List = Depends(get_callback_requests), authenticated: bool = Depends(require_api_key)):
        """Debug endpoint to view all callback requests"""
        return await debug_api.get_debug_callbacks(callback_requests)
    
    @app.get("/api/debug/conversations", tags=["debug"])
    async def get_debug_conversations(conversation_logs: List = Depends(get_conversation_logs), authenticated: bool = Depends(require_api_key)):
        """Debug endpoint to view all conversation logs"""
        return await debug_api.get_debug_conversations(conversation_logs)
    
    @app.get("/api/debug/knowledge_base", tags=["debug"])
    async def get_debug_knowledge_base(knowledge_base: Dict = Depends(get_knowledge_base), authenticated: bool = Depends(require_api_key)):
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
app.include_router(auth_api.router)

# Mount OTP routes only when explicitly enabled to avoid exposing unused endpoints in production
if os.getenv("ENABLE_OTP", "false").lower() == "true":
    app.include_router(otp_api.router)

app.include_router(appointment_details_api.router)
app.include_router(availability_api.router)
app.include_router(get_appointment_api.router)
app.include_router(get_contact_api.router)
app.include_router(new_patient_form_api.router)
app.include_router(callback_api.router)
app.include_router(conversation_log_api.router)
app.include_router(reschedule_api.router)
app.include_router(confirm_api.router)
app.include_router(get_current.router, prefix="/api", tags=["datetime"])
app.include_router(reporting_api.router)
app.include_router(save_transcripts_api.router)
app.include_router(transcript_summary_api.router)
# ========== MAIN ==========

if __name__ == "__main__":    
    logging.info("🦷 Starting BrightSmile Dental AI Assistant - Modular Backend")
    logging.info("� Authentication: API Key required for all endpoints (except /healthz)")
    logging.info("�📋 Available endpoints organized by modules:")
    logging.info("")
    logging.info("🔐 Authentication Module:")
    logging.info("   - POST /auth/generate-key (generate new API key)")
    logging.info("   - GET  /auth/keys (list API keys)")
    logging.info("   - DELETE /auth/keys (revoke API key)")
    logging.info("   - GET  /auth/test (test authentication)")
    logging.info("")
    logging.info("📱 SMS OTP Module:")
    logging.info("   - POST /api/otp/send (send OTP to phone number)")
    logging.info("   - POST /api/otp/verify (verify OTP code)")
    logging.info("   - POST /api/otp/status (check OTP status)")
    logging.info("   - POST /api/otp/cleanup (cleanup expired OTPs)")
    logging.info("   - GET  /api/otp/config (view OTP configuration)")
    logging.info("")
    logging.info("📅 Schedule & Availability Module:")
    logging.info("   - GET  /api/availability?date=YYYY-MM-DD (returns 3 days)")
    logging.info("   - GET  /api/availability/refresh")
    logging.info("")
    logging.info("📝 Booking & Reschedule Module:")
    logging.info("   - POST /api/book_patient_appointment")
    logging.info("   - POST /api/reschedule_patient_appointment (flexible agent format)")
    logging.info("   - POST /api/reschedule_appointment (legacy)")
    logging.info("")
    logging.info("📋 Core Patient APIs (with local caching and DOB verification):")
    logging.info("   - POST /api/get_appointment (phone, dob) - 24hr cache")
    logging.info("   - GET  /api/get_appointment/{phone}/{dob}")
    logging.info("   - POST /api/get_contact (phone, dob) - 24hr cache")
    logging.info("   - GET  /api/get_contact/{phone}/{dob}")
    logging.info("   - POST /api/get_appointment_details (phone, dob)")
    logging.info("   - POST /api/confirm_by_phone (phone, dob)")
    logging.info("")
    logging.info("👥 Patient Services Module:")
    logging.info("   - POST /api/send_new_patient_form")
    logging.info("   - POST /api/log_callback_request")
    logging.info("   - GET  /api/callback_requests")
    logging.info("   - PUT  /api/callback_requests/{id}/status")
    logging.info("   - POST /api/log_conversation_summary")
    logging.info("   - GET  /api/conversation_logs")
    logging.info("   - GET  /api/conversation_logs/analytics")
    logging.info("")
    logging.info("🔧 Debug Module:")
    logging.info("   - GET  /api/health")
    logging.info("   - GET  /api/getkolla/test")
    logging.info("   - GET  /api/debug/* (for testing)")
    logging.info("")
    logging.info("📈 Reporting & Analytics Module:")
    logging.info("   - POST /api/configure_reporting (setup email/config)")
    logging.info("   - GET  /api/reporting_config (view current config)")
    logging.info("   - POST /api/generate_report (manual report generation)")
    logging.info("   - GET  /api/interaction_statistics?days=7")
    logging.info("   - GET  /api/daily_interactions/{YYYY-MM-DD}")
    logging.info("   - GET  /api/interaction_summary (today's summary)")
    logging.info("   - POST /api/test_email (test email configuration)")
    logging.info("   - GET  /api/log_files (list available log files)")
    logging.info("")
    logging.info(f"📊 Data Status:")
    logging.info(f"   Schedule: {len(SCHEDULE)} days loaded")
    logging.info(f"   Existing Bookings: {len(BOOKINGS)} appointments")
    logging.info(f"   Knowledge Base: {len(KNOWLEDGE_BASE)} sections")
    logging.info("")
    logging.info("📝 Patient Interaction Logging:")
    logging.info(f"   Log Directory: {patient_logger.log_directory}")
    logging.info(f"   Daily Report Time: {patient_logger.config['reporting']['daily_email_time']}")
    logging.info(f"   Email Recipients: {len(patient_logger.config['email']['recipients'])} configured")
    logging.info("   Automatic logging enabled for all patient interactions")
    logging.info("")
    
    port = int(os.environ.get("PORT", 8000))  # default to 8000 locally
    uvicorn.run(app, host="0.0.0.0", port=port)