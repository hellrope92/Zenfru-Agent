import json
import requests
from datetime import datetime
from fastapi import APIRouter, HTTPException
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

# Endpoint for rescheduling an appointment
# To be implemented: logic for rescheduling

def reschedule_appointment(request: RescheduleRequest):
    """Reschedule an existing appointment using Kolla API."""
    try:
        # You must know the appointment ID to reschedule
        # Here, we assume new_slot contains the new datetime in ISO format and appointment_id is passed in reason or as a new field
        appointment_id = getattr(request, 'appointment_id', None) or request.reason  # fallback for demo
        if not appointment_id:
            return {"success": False, "message": "Appointment ID required to reschedule."}
        patch_data = {
            "start_time": request.new_slot,  # ISO format expected
            "notes": f"Rescheduled: {request.reason}"
        }
        url = f"{KOLLA_BASE_URL}/appointments/{appointment_id}"
        response = requests.patch(url, headers=KOLLA_HEADERS, data=json.dumps(patch_data))
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"Appointment {appointment_id} rescheduled successfully.",
                "new_slot": request.new_slot
            }
        else:
            return {
                "success": False,
                "message": f"Failed to reschedule appointment: {response.text}",
                "status": "failed"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "status": "error"
        }
