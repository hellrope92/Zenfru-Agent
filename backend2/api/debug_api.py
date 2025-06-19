"""
Debug and testing API endpoints
Handles health checks, debug information, and testing utilities
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException

# Import dependencies (will be injected from main.py)
from services.getkolla_service import GetKollaService

router = APIRouter(prefix="/api", tags=["debug"])

async def health_check(getkolla_service: GetKollaService, schedule: Dict, bookings: List, knowledge_base: Dict):
    """Health check endpoint"""
    # Test GetKolla API connectivity
    kolla_status = getkolla_service.health_check()
    
    return {
        "status": "healthy",
        "service": "BrightSmile Dental AI Assistant",
        "timestamp": datetime.now().isoformat(),
        "data_loaded": {
            "schedule": len(schedule) > 0,
            "bookings": len(bookings) > 0,
            "knowledge_base": len(knowledge_base) > 0
        },
        "getkolla_api": {
            "status": "connected" if kolla_status else "disconnected",
            "available": kolla_status
        }
    }

async def test_getkolla_api(getkolla_service: GetKollaService):
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

async def get_debug_schedule(schedule: Dict, bookings: List):
    """Debug endpoint to view the clinic schedule and bookings"""
    return {
        "schedule": schedule,
        "existing_bookings": bookings,
        "total_existing_bookings": len(bookings)
    }

async def get_debug_callbacks(callback_requests: List):
    """Debug endpoint to view all callback requests"""
    return {
        "callbacks": callback_requests,
        "total": len(callback_requests)
    }

async def get_debug_conversations(conversation_logs: List):
    """Debug endpoint to view all conversation logs"""
    return {
        "conversations": conversation_logs,
        "total": len(conversation_logs)
    }

async def get_debug_knowledge_base(knowledge_base: Dict):
    """Debug endpoint to view the knowledge base"""
    return {
        "knowledge_base": knowledge_base,
        "clinic_name": knowledge_base.get("clinic_info", {}).get("name", "Unknown"),
        "services_count": len(knowledge_base.get("clinic_info", {}).get("services_offered_summary", [])),
        "doctors_count": len(knowledge_base.get("clinic_info", {}).get("dentist_team", []))
    }
