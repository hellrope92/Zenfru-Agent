"""
Get Contact API endpoint
Retrieves existing patient contact information using Kolla API filters
Parameters: phone (required), name, dob (optional for legacy support)
Used for booking appointments with existing patients
Uses direct Kolla API filtering for efficient contact lookup
"""

import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from services.auth_service import require_api_key
from dotenv import load_dotenv
import logging

from api.models import GetContactRequest

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/api", tags=["contacts"])
logger = logging.getLogger(__name__)

# Kolla API configuration
KOLLA_BASE_URL = os.getenv("KOLLA_BASE_URL", "https://unify.kolla.dev/dental/v1")
KOLLA_HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {os.getenv('KOLLA_BEARER_TOKEN')}",
    "connector-id": os.getenv("KOLLA_CONNECTOR_ID", "eaglesoft"),
    "consumer-id": os.getenv("KOLLA_CONSUMER_ID", "dajc")
}

@router.post("/get_contact")
async def get_contact(request: GetContactRequest, authenticated: bool = Depends(require_api_key)):
    """
    Retrieves existing patient contact information using Kolla API filters
    Parameters: phone (required), name, dob (optional for legacy support)
    Used for booking appointments with existing patients
    """
    try:
        logger.info(f"Fetching contact for patient phone: {request.phone}")
        
        # Normalize phone number
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Use Kolla API filter to search for contacts by phone number
        contacts = await fetch_contacts_by_phone_filter(normalized_phone)
        if contacts:
            return {
                "success": True,
                "patient_phone": request.phone,
                "contacts": contacts,
                "source": "kolla_api_filter"
            }
        else:
            logger.warning(f"No contact information found for phone: {request.phone}")
            raise HTTPException(status_code=404, detail="No contact found for specified patient")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in get_contact", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error retrieving contact information")

async def fetch_contacts_by_phone_filter(patient_phone: str) -> Optional[list]:
    """Fetch all contact information from Kolla API using phone filter"""
    try:
        contacts_url = f"{KOLLA_BASE_URL}/contacts?filter=phone=%27{patient_phone}%27"
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, timeout=10)
    
        logging.info(f"   Response Status: {response.status_code}")
        if response.status_code != 200:            
            logging.error(f"   ❌ API Error: {response.text}")
            return None
        contacts_data = response.json()
        contacts = contacts_data.get("contacts", [])
    
        logging.info(f"   ✅ Found {len(contacts)} contacts matching phone filter")
        if contacts:
            return contacts
    
        logging.warning(f"   ⚠️ No contact found for phone: {patient_phone}")
        return None
    except Exception as e:    
        logging.error(f"   ❌ Error fetching contact by phone filter: {e}")
        return None

@router.get("/get_contact/{patient_name}/{patient_dob}")
async def get_contact_by_url(patient_name: str, patient_dob: str, authenticated: bool = Depends(require_api_key)):
    """
    Alternative GET endpoint for retrieving contact information (legacy support)
    URL format: /api/get_contact/{patient_name}/{patient_dob}
    Note: This endpoint requires phone number for accurate lookup
    """
    return {
        "success": False,
        "message": "This endpoint is deprecated. Please use POST /api/get_contact with phone parameter.",
        "suggestion": "Use POST /api/get_contact with phone number for accurate patient identification"
    }

@router.post("/get_contact/refresh")
async def refresh_contact_cache(request: GetContactRequest, authenticated: bool = Depends(require_api_key)):
    """Force refresh contact data from Kolla API"""
    try:
        # Since we're not using cache anymore, this just fetches fresh data
        normalized_phone = request.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        contacts = await fetch_contacts_by_phone_filter(normalized_phone)
        return {
            "success": True,
            "message": "Contact data refreshed from Kolla API",
            "patient_phone": request.phone,
            "contact_found": bool(contacts),
            "contacts": contacts
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing contact data: {str(e)}")

@router.get("/contacts/search")
async def search_contacts(name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None, authenticated: bool = Depends(require_api_key)):
    """
    Search contacts with flexible parameters using Kolla API filters
    """
    try:
        if phone:
            # Use phone-based search
            normalized_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            contacts = await fetch_contacts_by_phone_filter(normalized_phone)
            if contacts:
                return {
                    "success": True,
                    "search_type": "phone",
                    "search_value": phone,
                    "contacts": contacts
                }
            else:
                return {
                    "success": False,
                    "message": f"No contact found for phone: {phone}",
                    "search_type": "phone",
                    "contacts": []
                }
        
        if name:
            # Search by name using Kolla filter
            contact_info = await fetch_contact_by_name_filter(name)
            
            if contact_info:
                return {
                    "success": True,
                    "search_type": "name",
                    "search_value": name,
                    "contacts": contact_info  # This could be a list
                }
            else:
                return {
                    "success": False,
                    "message": f"No contact found for name: {name}",
                    "search_type": "name", 
                    "contacts": []
                }
        
        return {
            "success": False,
            "message": "Please provide either phone or name parameter for contact search",
            "available_parameters": ["phone", "name"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching contacts: {str(e)}")

async def fetch_contact_by_name_filter(patient_name: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch contact information from Kolla API using name filter"""
    try:
        contacts_url = f"{KOLLA_BASE_URL}/contacts"
        
        # Build filter for name search
        filter_query = f"type='PATIENT' AND state='ACTIVE' AND name='{patient_name}'"
        
        params = {"filter": filter_query}
        
    
        logging.info(f"📞 Calling Kolla API: {contacts_url}")    
        logging.info(f"   Filter: {filter_query}")
        
        response = requests.get(contacts_url, headers=KOLLA_HEADERS, params=params, timeout=10)
    
        logging.info(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:            
            logging.error(f"   ❌ API Error: {response.text}")
            return None
            
        contacts_data = response.json()
        contacts = contacts_data.get("contacts", [])            
        logging.info(f"   ✅ Found {len(contacts)} contacts matching name filter")
        
        if contacts:
            return contacts
        
        logging.warning(f"   ⚠️ No contact found for name: {patient_name}")
        return None
        
    except Exception as e:    
        logging.error(f"   ❌ Error fetching contact by name filter: {e}")
        return None
