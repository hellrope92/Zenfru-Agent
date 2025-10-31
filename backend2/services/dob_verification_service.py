"""
DOB (Date of Birth) Verification Service
Verifies patient date of birth against Kolla API for personal information access
"""

import os
import requests
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class DOBVerificationService:
    """Service for verifying patient DOB against Kolla API"""
    
    def __init__(self):
        # Kolla API configuration
        self.base_url = os.getenv("KOLLA_BASE_URL", "https://unify.kolla.dev/dental/v1")
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {os.getenv('KOLLA_BEARER_TOKEN')}",
            "connector-id": os.getenv("KOLLA_CONNECTOR_ID", "eaglesoft"),
            "consumer-id": os.getenv("KOLLA_CONSUMER_ID", "dajc")
        }
    
    def normalize_phone_number(self, phone_number: str) -> str:
        """Normalize phone number by removing spaces, dashes, parentheses"""
        return phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    def normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize date string to YYYY-MM-DD format
        Handles various date formats including:
        - YYYY-MM-DD
        - MM/DD/YYYY
        - DD/MM/YYYY
        - MM-DD-YYYY
        - DD-MM-YYYY
        """
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # If already in YYYY-MM-DD format
        if len(date_str) == 10 and date_str.count('-') == 2:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                return date_str
            except ValueError:
                pass
        
        # Try various date formats
        date_formats = [
            "%Y-%m-%d",      # 2000-01-25
            "%m/%d/%Y",      # 01/25/2000
            "%d/%m/%Y",      # 25/01/2000
            "%m-%d-%Y",      # 01-25-2000
            "%d-%m-%Y",      # 25-01-2000
            "%Y/%m/%d",      # 2000/01/25
            "%Y.%m.%d",      # 2000.01.25
            "%m.%d.%Y",      # 01.25.2000
            "%d.%m.%Y",      # 25.01.2000
        ]
        
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, date_format)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date format: {date_str}")
        return None
    
    async def get_contact_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get contact information from Kolla API using phone number"""
        try:
            normalized_phone = self.normalize_phone_number(phone_number)
            
            contacts_url = f"{self.base_url}/contacts"
            filter_query = f"type='PATIENT' AND state='ACTIVE' AND phone='{normalized_phone}'"
            params = {"filter": filter_query}
            
            logger.info(f"📞 Fetching contact for phone: {normalized_phone}")
            
            response = requests.get(contacts_url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ Kolla API error: {response.status_code} - {response.text}")
                return None
            
            contacts_data = response.json()
            contacts = contacts_data.get("contacts", [])
            
            if contacts:
                contact = contacts[0]  # Return first matching contact
                logger.info(f"✅ Found contact: {contact.get('given_name', '')} {contact.get('family_name', '')}")
                return contact
            else:
                logger.warning(f"⚠️ No contact found for phone: {normalized_phone}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching contact by phone: {e}")
            return None
    
    async def verify_dob(self, phone_number: str, provided_dob: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Verify patient's DOB against Kolla API
        
        Args:
            phone_number: Patient's phone number
            provided_dob: DOB provided by the user (various formats accepted)
        
        Returns:
            Tuple of (is_verified, message, contact_data)
            - is_verified: True if DOB matches, False otherwise
            - message: Description of verification result
            - contact_data: Full contact data if verification successful, None otherwise
        """
        try:
            # Normalize the provided DOB
            normalized_provided_dob = self.normalize_date(provided_dob)
            if not normalized_provided_dob:
                return False, "Invalid date format provided", None
            
            # Get contact information from Kolla API
            contact_data = await self.get_contact_by_phone(phone_number)
            if not contact_data:
                return False, "No patient found with the provided phone number", None
            
            # Extract birth_date from contact data
            contact_birth_date = contact_data.get("birth_date")
            if not contact_birth_date:
                logger.warning(f"⚠️ No birth_date found in contact data for phone: {phone_number}")
                return False, "Date of birth not available in patient records", None
            
            # Normalize the contact's birth date
            normalized_contact_dob = self.normalize_date(contact_birth_date)
            if not normalized_contact_dob:
                logger.error(f"❌ Invalid birth_date format in contact data: {contact_birth_date}")
                return False, "Invalid date format in patient records", None
            
            # Compare the dates
            if normalized_provided_dob == normalized_contact_dob:
                logger.info(f"✅ DOB verification successful for phone: {phone_number}")
                return True, "Date of birth verified successfully", contact_data
            else:
                logger.warning(f"❌ DOB mismatch for phone: {phone_number}. Provided: {normalized_provided_dob}, Expected: {normalized_contact_dob}")
                return False, "Date of birth does not match our records", None
                
        except Exception as e:
            logger.error(f"❌ Error verifying DOB: {e}")
            return False, f"Error verifying date of birth: {str(e)}", None
    
    async def verify_dob_for_contact(self, contact_data: Dict[str, Any], provided_dob: str) -> Tuple[bool, str]:
        """
        Verify DOB against already retrieved contact data
        
        Args:
            contact_data: Contact information from Kolla API
            provided_dob: DOB provided by the user
        
        Returns:
            Tuple of (is_verified, message)
        """
        try:
            # Normalize the provided DOB
            normalized_provided_dob = self.normalize_date(provided_dob)
            if not normalized_provided_dob:
                return False, "Invalid date format provided"
            
            # Extract birth_date from contact data
            contact_birth_date = contact_data.get("birth_date")
            if not contact_birth_date:
                return False, "Date of birth not available in patient records"
            
            # Normalize the contact's birth date
            normalized_contact_dob = self.normalize_date(contact_birth_date)
            if not normalized_contact_dob:
                return False, "Invalid date format in patient records"
            
            # Compare the dates
            if normalized_provided_dob == normalized_contact_dob:
                return True, "Date of birth verified successfully"
            else:
                return False, "Date of birth does not match our records"
                
        except Exception as e:
            logger.error(f"❌ Error verifying DOB for contact: {e}")
            return False, f"Error verifying date of birth: {str(e)}"


# Global instance
dob_verification_service = DOBVerificationService()