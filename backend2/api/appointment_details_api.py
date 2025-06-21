import requests
from fastapi import APIRouter, HTTPException

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

router = APIRouter(prefix="/api", tags=["appointment-details"])

# Endpoint for fetching appointment details
# To be implemented: logic for fetching appointment details

def get_appointment_details(appointment_id: str):
    """Fetch appointment details from Kolla API."""
    try:
        url = f"{KOLLA_BASE_URL}/appointments/{appointment_id}"
        response = requests.get(url, headers=KOLLA_HEADERS)
        if response.status_code == 200:
            return {
                "success": True,
                "appointment": response.json()
            }
        else:
            return {
                "success": False,
                "message": f"Failed to fetch appointment details: {response.text}",
                "status": "failed"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "status": "error"
        }
