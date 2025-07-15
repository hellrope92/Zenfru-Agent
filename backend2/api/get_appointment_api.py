"""
Get Appointment API endpoint
Retrieves existing appointment information for a patient using Kolla API filters
Parameters: phone (required)
Used for rescheduling and confirming appointments
Uses direct Kolla API filtering for efficient appointment lookup

Note: Matching is performed by patient phone number for accurate identification.
"""

import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from api.models import GetAppointmentRequest

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/api", tags=["appointments"])

# Kolla API configuration
KOLLA_BASE_URL = os.getenv("KOLLA_BASE_URL", "https://unify.kolla.dev/dental/v1")
KOLLA_HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {os.getenv('KOLLA_BEARER_TOKEN')}",
    "connector-id": os.getenv("KOLLA_CONNECTOR_ID", "eaglesoft"),
    "consumer-id": os.getenv("KOLLA_CONSUMER_ID", "dajc")
}

@router.post("/get_appointment")
async def get_appointment(request: GetAppointmentRequest):
    """
    Retrieves existing appointment information for a patient using Kolla API filters
    Parameters: phone (required)
    Used for rescheduling and confirming appointments
    Note: Matching is performed by phone number for accurate patient identification.
    """
    try:
        # Print phone number as requested
        print(f"🔍 Fetching appointments for patient phone: {request.phone}")
        
        # Normalize phone number (remove spaces, dashes, etc.)
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            
        # Use Kolla API to get appointments for this phone number
        appointments = await fetch_appointments_by_phone_filter(normalized_phone)
        
        if appointments:
            # Get the latest appointment (first one since they're sorted by start_time desc)
            latest_appointment = appointments[0] if appointments else None
            
            return {
                "success": True,
                "patient_phone": request.phone,
                "appointment": latest_appointment,
                "total_appointments": len(appointments),
                "source": "kolla_api_filter"
            }
        else:
            return {
                "success": False,
                "message": "No appointments found for the specified patient",
                "patient_phone": request.phone,
                "appointment": None
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving appointments: {str(e)}")

async def fetch_appointments_by_phone_filter(patient_phone: str) -> List[Dict[str, Any]]:
    """
    Fetch appointments from Kolla API using filters
    Step 1: Find contact by phone using contacts filter
    Step 2: Get appointments for that contact using appointments filter
    """
    try:
        # Step 1: Find contact by phone number
        contact_info = await get_contact_by_phone_filter(patient_phone)
        
        if not contact_info:
            print(f"⚠️ No contact found for phone: {patient_phone}")
            return []
        
        # Step 2: Get contact_id for appointments filter
        contact_id = contact_info.get("name")  # This is usually like "contacts/123"
        
        if not contact_id:
            print(f"⚠️ No contact ID found for phone: {patient_phone}")
            return []
        
        print(f"📋 Found contact: {contact_info.get('given_name', '')} {contact_info.get('family_name', '')} ({contact_id})")
        
        # Step 3: Get appointments for this contact using appointments filter
        appointments = await get_appointments_by_contact_filter(contact_id)
        
        if appointments:
            print(f"✅ Found {len(appointments)} appointments for patient")
            return appointments
        else:
            print(f"⚠️ No appointments found for contact: {contact_id}")
            return []
        
    except Exception as e:
        print(f"❌ Error fetching appointments by phone filter: {e}")
        return []

async def get_contact_by_phone_filter(patient_phone: str) -> Optional[Dict[str, Any]]:
    """Get contact information using Kolla contacts filter"""
    try:
        contacts_url = f"{KOLLA_BASE_URL}/contacts"
        
        # Build filter for phone number search
        # Phone number is already normalized (e.g., "5551234567")
        filter_query = f"type='PATIENT' AND state='ACTIVE' AND phone='{patient_phone}'"
        params = {"filter": filter_query}
        
        print(f"📞 Calling Kolla Contacts API: {contacts_url}")
        print(f"   Filter: {filter_query}")
        print(f"   Normalized phone: {patient_phone}")
        
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, params=params, timeout=10)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return None
            
        contacts_data = response.json()
        contacts = contacts_data.get("contacts", [])
        
        if contacts:
            # Return the first matching contact
            contact = contacts[0]
            print(f"   ✅ Found contact: {contact.get('given_name', '')} {contact.get('family_name', '')}")
            return contact
        
        return None
        
    except Exception as e:
        print(f"   ❌ Error getting contact by phone filter: {e}")
        return None

async def get_appointments_by_contact_filter(contact_id: str) -> List[Dict[str, Any]]:
    """Get appointments for a specific contact using Kolla appointments filter"""
    try:
        appointments_url = f"{KOLLA_BASE_URL}/appointments"
        
        # Build filter for contact_id and future appointments
        # Get appointments from past 30 days to future 60 days
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
        future_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%dT23:59:59Z")
        
        filter_query = f"contact_id='{contact_id}' AND start_time > '{past_date}' AND start_time < '{future_date}'"
        params = {"filter": filter_query}
        
        print(f"📞 Calling Kolla Appointments API: {appointments_url}")
        print(f"   Filter: {filter_query}")
        
        response = requests.get(appointments_url, headers=KOLLA_HEADERS, params=params, timeout=10)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return []
            
        appointments_data = response.json()
        appointments = appointments_data.get("appointments", [])
        
        print(f"   ✅ Retrieved {len(appointments)} appointments")
        
        # Sort appointments by start_time to get the latest ones first
        appointments.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        
        # Enrich appointment data
        enriched_appointments = []
        for appointment in appointments:
            enriched_appointment = {
                **appointment,
                "appointment_date": appointment.get("start_time", "").split("T")[0] if appointment.get("start_time") else None,
                "appointment_time": appointment.get("start_time", "").split("T")[1] if appointment.get("start_time") else None,
                "wall_date": appointment.get("wall_start_time", "").split(" ")[0] if appointment.get("wall_start_time") else None,
                "wall_time": appointment.get("wall_start_time", "").split(" ")[1] if appointment.get("wall_start_time") else None,
                "status": "confirmed" if appointment.get("confirmed") else "unconfirmed",
                "cancelled": appointment.get("cancelled", False),
                "completed": appointment.get("completed", False),
                "duration_minutes": calculate_duration(appointment.get("start_time"), appointment.get("end_time")),
                "provider": appointment.get("providers", [{}])[0].get("display_name", "") if appointment.get("providers") else "",
                "operatory": appointment.get("resources", [{}])[0].get("display_name", "") if appointment.get("resources") else "",
                "notes": appointment.get("notes", ""),
                "short_description": appointment.get("short_description", "")
            }
            
            enriched_appointments.append(enriched_appointment)
        
        return enriched_appointments
        
    except Exception as e:
        print(f"   ❌ Error getting appointments by contact filter: {e}")
        return []

def calculate_duration(start_time: str, end_time: str) -> Optional[int]:
    """Calculate appointment duration in minutes"""
    try:
        if start_time and end_time:
            start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            return int((end - start).total_seconds() / 60)
    except:
        pass
    return None

@router.get("/get_appointment_by_phone/{patient_phone}")
async def get_appointment_by_phone_only(patient_phone: str):
    """
    GET endpoint for retrieving appointments by phone number only
    URL format: /api/get_appointment_by_phone/{patient_phone}
    """
    request = GetAppointmentRequest(phone=patient_phone)
    return await get_appointment(request)

@router.post("/get_appointment/refresh")
async def refresh_appointments_cache(request: GetAppointmentRequest):
    """Force refresh appointment data from Kolla API"""
    try:
        # Normalize phone number
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Force fetch from API
        appointments = await fetch_appointments_by_phone_filter(normalized_phone)
        
        return {
            "success": True,
            "message": "Appointments data refreshed from Kolla API",
            "patient_phone": request.phone,
            "appointments_found": len(appointments),
            "appointments": appointments
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing appointments data: {str(e)}")

@router.get("/appointments/search")
async def search_appointments(
    phone: Optional[str] = None,
    contact_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Search appointments with flexible parameters using Kolla API filters
    """
    try:
        if phone:
            # Use phone-based search
            normalized_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            appointments = await fetch_appointments_by_phone_filter(normalized_phone)
            
            return {
                "success": True,
                "search_type": "phone",
                "search_value": phone,
                "appointments": appointments,
                "total_appointments": len(appointments)
            }
        
        if contact_id:
            # Use contact_id-based search
            appointments = await get_appointments_by_contact_filter(contact_id)
            
            return {
                "success": True,
                "search_type": "contact_id",
                "search_value": contact_id,
                "appointments": appointments,
                "total_appointments": len(appointments)
            }
        
        if start_date and end_date:
            # Use date range search
            appointments = await get_appointments_by_date_range(start_date, end_date)
            
            return {
                "success": True,
                "search_type": "date_range",
                "search_value": f"{start_date} to {end_date}",
                "appointments": appointments,
                "total_appointments": len(appointments)
            }
        
        return {
            "success": False,
            "message": "Please provide either phone, contact_id, or date range (start_date + end_date) parameters",
            "available_parameters": ["phone", "contact_id", "start_date + end_date"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching appointments: {str(e)}")

async def get_appointments_by_date_range(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Get appointments for a date range using Kolla appointments filter"""
    try:
        appointments_url = f"{KOLLA_BASE_URL}/appointments"
        
        # Build filter for date range
        start_filter = f"{start_date}T00:00:00Z"
        end_filter = f"{end_date}T23:59:59Z"
        filter_query = f"start_time > '{start_filter}' AND start_time < '{end_filter}'"
        
        params = {"filter": filter_query}
        
        print(f"📞 Calling Kolla Appointments API: {appointments_url}")
        print(f"   Filter: {filter_query}")
        
        response = requests.get(appointments_url, headers=KOLLA_HEADERS, params=params, timeout=10)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return []
            
        appointments_data = response.json()
        appointments = appointments_data.get("appointments", [])
        
        print(f"   ✅ Retrieved {len(appointments)} appointments for date range")
        
        return appointments
        
    except Exception as e:
        print(f"   ❌ Error getting appointments by date range: {e}")
        return []
