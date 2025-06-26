import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .models import RescheduleRequest

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

router = APIRouter(prefix="/api", tags=["reschedule"])

class FlexibleRescheduleRequest(BaseModel):
    """Flexible request model that accepts various agent formats"""
    appointment_id: str
    # Time fields - agent can send any of these
    new_date: Optional[str] = None
    new_time: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    wall_start_time: Optional[str] = None
    wall_end_time: Optional[str] = None
    
    # Optional fields that agent might send
    contact_id: Optional[str] = None
    contact: Optional[Dict[str, Any]] = None
    providers: Optional[list] = None
    scheduler: Optional[Dict[str, Any]] = None
    appointment_type_id: Optional[str] = None
    operatory: Optional[str] = None
    short_description: Optional[str] = None
    notes: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    
    # Legacy support
    name: Optional[str] = None
    dob: Optional[str] = None
    reason: Optional[str] = None
    new_slot: Optional[str] = None

@router.post("/reschedule_patient_appointment")
async def reschedule_patient_appointment(request: FlexibleRescheduleRequest):
    """
    Reschedule an existing appointment using Kolla API.
    Accepts flexible agent format and maps to Kolla API requirements.
    Agent hits: POST /api/reschedule_patient_appointment
    """
    try:
        # Validate appointment_id
        if not request.appointment_id:
            raise HTTPException(status_code=400, detail="appointment_id is required")
        
        # Print DOB if provided (as requested)
        if request.dob:
            print(f"Rescheduling appointment for patient DOB: {request.dob}")
        
        # Build the patch data from agent input
        patch_data = build_patch_data(request)
        
        if not patch_data:
            raise HTTPException(status_code=400, detail="No valid reschedule data provided")
        
        # Call Kolla API to reschedule
        url = f"{KOLLA_BASE_URL}/appointments/{request.appointment_id}"
        response = requests.patch(url, headers=KOLLA_HEADERS, data=json.dumps(patch_data))
        
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"Appointment {request.appointment_id} rescheduled successfully",
                "appointment_id": request.appointment_id,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "updated_fields": patch_data,
                "status": "rescheduled"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to reschedule appointment: {response.text}",
                "status_code": response.status_code,
                "appointment_id": request.appointment_id,
                "status": "failed"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rescheduling appointment: {str(e)}")

def build_patch_data(request: FlexibleRescheduleRequest) -> Dict[str, Any]:
    """
    Build patch data for Kolla API from flexible agent request.
    Maps agent fields to Kolla API expected format.
    """
    patch_data = {}
    
    # Handle time fields - priority order for determining new time
    new_start_time = None
    new_end_time = None
    
    # 1. Check for direct ISO format times
    if request.start_time:
        new_start_time = request.start_time
    elif request.wall_start_time:
        new_start_time = parse_wall_time_to_iso(request.wall_start_time)
    elif request.new_date and request.new_time:
        # Combine date and time
        new_start_time = combine_date_time(request.new_date, request.new_time)
    elif request.new_slot:
        # Legacy support
        new_start_time = request.new_slot
    
    if request.end_time:
        new_end_time = request.end_time
    elif request.wall_end_time:
        new_end_time = parse_wall_time_to_iso(request.wall_end_time)
    elif new_start_time:
        # Calculate end time (default 30 minutes if not provided)
        new_end_time = calculate_end_time(new_start_time)
    
    # Add time fields to patch data
    if new_start_time:
        patch_data["start_time"] = new_start_time
    if new_end_time:
        patch_data["end_time"] = new_end_time
    
    # Map other fields that might come from agent
    field_mappings = {
        "contact_id": "contact_id",
        "contact": "contact",
        "providers": "providers", 
        "scheduler": "scheduler",
        "appointment_type_id": "appointment_type_id",
        "operatory": "operatory",
        "short_description": "short_description",
        "notes": "notes",
        "additional_data": "additional_data"
    }
    
    for agent_field, kolla_field in field_mappings.items():
        value = getattr(request, agent_field, None)
        if value is not None:
            patch_data[kolla_field] = value
    
    # Handle legacy reason field
    if request.reason and not patch_data.get("notes"):
        patch_data["notes"] = f"Rescheduled: {request.reason}"
    
    return patch_data

def parse_wall_time_to_iso(wall_time: str) -> Optional[str]:
    """
    Parse wall time format to ISO format.
    Handles various wall time formats.
    """
    try:
        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(wall_time, fmt)
                return dt.isoformat() + "Z"
            except ValueError:
                continue
        
        # If no format matches, return as is (might already be ISO)
        return wall_time
        
    except Exception:
        return None

def combine_date_time(date_str: str, time_str: str) -> Optional[str]:
    """
    Combine separate date and time strings into ISO format.
    """
    try:
        # Parse date
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
        date_obj = None
        
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
        
        if not date_obj:
            return None
        
        # Parse time
        time_formats = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]
        time_obj = None
        
        for fmt in time_formats:
            try:
                time_obj = datetime.strptime(time_str, fmt).time()
                break
            except ValueError:
                continue
        
        if not time_obj:
            return None
        
        # Combine and return ISO format
        dt = datetime.combine(date_obj, time_obj)
        return dt.isoformat() + "Z"
        
    except Exception:
        return None

def calculate_end_time(start_time: str, duration_minutes: int = 30) -> Optional[str]:
    """
    Calculate end time based on start time and duration.
    """
    try:
        # Parse start time
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        
        # Add duration
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        return end_dt.isoformat().replace("+00:00", "Z")
        
    except Exception:
        return None

# Legacy endpoint for backward compatibility
@router.post("/reschedule_appointment")
async def reschedule_appointment_legacy(request: RescheduleRequest):
    """Legacy reschedule endpoint for backward compatibility"""
    # Convert old format to new format
    flexible_request = FlexibleRescheduleRequest(
        appointment_id=getattr(request, 'appointment_id', '') or request.reason,
        name=request.name,
        dob=request.dob,
        reason=request.reason,
        new_slot=request.new_slot
    )
    
    return await reschedule_patient_appointment(flexible_request)
