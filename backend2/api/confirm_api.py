import requests
from fastapi import APIRouter, HTTPException
from .models import RescheduleRequest  # or define a ConfirmRequest if needed

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

router = APIRouter(prefix="/api", tags=["confirm"])

# Endpoint for confirming an appointment
# To be implemented: logic for confirming

def confirm_appointment(appointment_id: str):
    """Confirm an appointment using Kolla API."""
    try:
        url = f"{KOLLA_BASE_URL}/appointments/{appointment_id}:confirm"
        response = requests.post(url, headers=KOLLA_HEADERS)
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"Appointment {appointment_id} confirmed successfully."
            }
        else:
            return {
                "success": False,
                "message": f"Failed to confirm appointment: {response.text}",
                "status": "failed"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "status": "error"
        }
