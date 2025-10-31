"""
SMS OTP Service for sending and verifying one-time passwords
Supports multiple SMS providers with configurable settings
"""

import os
import random
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import requests


class OTPService:
    """Service for managing SMS OTP functionality"""
    
    def __init__(self):
        self.otp_storage: Dict[str, Dict] = {}  # In-memory storage for demo
        self.otp_length = 6
        self.otp_expiry_minutes = 5
        self.max_attempts = 3
        
        # SMS Provider configuration
        self.sms_provider = os.getenv('SMS_PROVIDER', 'twilio')  # 'twilio' or 'textlocal'
        
        # Twilio configuration
        self.twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        # TextLocal configuration (alternative)
        self.textlocal_api_key = os.getenv('TEXTLOCAL_API_KEY')
        self.textlocal_sender = os.getenv('TEXTLOCAL_SENDER', 'BrightSmile')
        
        self.logger = logging.getLogger(__name__)
    
    def generate_otp(self) -> str:
        """Generate a random OTP"""
        return ''.join([str(random.randint(0, 9)) for _ in range(self.otp_length)])
    
    def _hash_phone_number(self, phone_number: str) -> str:
        """Hash phone number for security"""
        return hashlib.sha256(phone_number.encode()).hexdigest()
    
    def _normalize_phone_number(self, phone_number: str) -> str:
        """Normalize phone number format"""
        # Remove all non-numeric characters
        normalized = ''.join(filter(str.isdigit, phone_number))
        
        # Add country code if not present (assuming US +1 for demo)
        if len(normalized) == 10:
            normalized = '1' + normalized
        elif len(normalized) == 11 and normalized.startswith('1'):
            pass  # Already has country code
        elif len(normalized) > 11:
            # International number, keep as is
            pass
        
        return '+' + normalized
    
    def send_otp_via_twilio(self, phone_number: str, otp: str) -> bool:
        """Send OTP via Twilio SMS"""
        try:
            # Import Twilio client lazily so missing package doesn't break app import
            try:
                from twilio.rest import Client
            except Exception:
                self.logger.error("Twilio library not available. Install 'twilio' or set SMS_PROVIDER to 'mock' or 'textlocal'.")
                return False

            if not all([self.twilio_account_sid, self.twilio_auth_token, self.twilio_phone_number]):
                self.logger.error("Twilio credentials not configured")
                return False
            
            client = Client(self.twilio_account_sid, self.twilio_auth_token)
            
            message = client.messages.create(
                body=f"Your BrightSmile verification code is: {otp}. This code expires in {self.otp_expiry_minutes} minutes.",
                from_=self.twilio_phone_number,
                to=phone_number
            )
            
            self.logger.info(f"OTP sent via Twilio to {phone_number[-4:].rjust(len(phone_number), '*')}, Message SID: {message.sid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send OTP via Twilio: {str(e)}")
            return False
    
    def send_otp_via_textlocal(self, phone_number: str, otp: str) -> bool:
        """Send OTP via TextLocal SMS"""
        try:
            if not self.textlocal_api_key:
                self.logger.error("TextLocal API key not configured")
                return False
            
            # Remove + from phone number for TextLocal
            phone_clean = phone_number.replace('+', '')
            
            url = "https://api.textlocal.in/send/"
            data = {
                'apikey': self.textlocal_api_key,
                'numbers': phone_clean,
                'message': f"Your BrightSmile verification code is: {otp}. This code expires in {self.otp_expiry_minutes} minutes.",
                'sender': self.textlocal_sender
            }
            
            response = requests.post(url, data=data)
            response_data = response.json()
            
            if response_data.get('status') == 'success':
                self.logger.info(f"OTP sent via TextLocal to {phone_number[-4:].rjust(len(phone_number), '*')}")
                return True
            else:
                self.logger.error(f"TextLocal API error: {response_data}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to send OTP via TextLocal: {str(e)}")
            return False
    
    def send_otp_mock(self, phone_number: str, otp: str) -> bool:
        """Mock SMS sending for testing (logs OTP instead of sending)"""
        self.logger.info(f"MOCK SMS: OTP {otp} would be sent to {phone_number}")
        print(f"📱 MOCK SMS to {phone_number}: Your verification code is {otp}")
        return True
    
    def send_otp(self, phone_number: str) -> Tuple[bool, str, Optional[str]]:
        """
        Send OTP to phone number
        Returns: (success, message, otp_id)
        """
        try:
            # Normalize phone number
            normalized_phone = self._normalize_phone_number(phone_number)
            phone_hash = self._hash_phone_number(normalized_phone)
            
            # Check rate limiting (optional)
            if phone_hash in self.otp_storage:
                last_sent = self.otp_storage[phone_hash].get('last_sent')
                if last_sent and datetime.now() - last_sent < timedelta(minutes=1):
                    return False, "Please wait before requesting another OTP", None
            
            # Generate OTP
            otp = self.generate_otp()
            otp_id = f"otp_{phone_hash}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Send via configured provider
            sent_successfully = False
            
            if self.sms_provider == 'twilio':
                sent_successfully = self.send_otp_via_twilio(normalized_phone, otp)
            elif self.sms_provider == 'textlocal':
                sent_successfully = self.send_otp_via_textlocal(normalized_phone, otp)
            else:
                # Fallback to mock for testing
                sent_successfully = self.send_otp_mock(normalized_phone, otp)
            
            if sent_successfully:
                # Store OTP for verification
                self.otp_storage[phone_hash] = {
                    'otp': otp,
                    'phone_number': normalized_phone,
                    'created_at': datetime.now(),
                    'expires_at': datetime.now() + timedelta(minutes=self.otp_expiry_minutes),
                    'attempts': 0,
                    'verified': False,
                    'last_sent': datetime.now(),
                    'otp_id': otp_id
                }
                
                return True, f"OTP sent successfully to {phone_number}", otp_id
            else:
                return False, "Failed to send OTP", None
                
        except Exception as e:
            self.logger.error(f"Error sending OTP: {str(e)}")
            return False, f"Error sending OTP: {str(e)}", None
    
    def verify_otp(self, phone_number: str, otp: str, otp_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Verify OTP for phone number
        Returns: (success, message)
        """
        try:
            normalized_phone = self._normalize_phone_number(phone_number)
            phone_hash = self._hash_phone_number(normalized_phone)
            
            if phone_hash not in self.otp_storage:
                return False, "No OTP found for this phone number"
            
            otp_data = self.otp_storage[phone_hash]
            
            # Check if already verified
            if otp_data.get('verified'):
                return False, "OTP already verified"
            
            # Check expiry
            if datetime.now() > otp_data['expires_at']:
                self.cleanup_expired_otp(phone_hash)
                return False, "OTP has expired"
            
            # Check max attempts
            if otp_data['attempts'] >= self.max_attempts:
                self.cleanup_expired_otp(phone_hash)
                return False, "Maximum verification attempts exceeded"
            
            # Increment attempts
            otp_data['attempts'] += 1
            
            # Verify OTP
            if otp_data['otp'] == otp:
                otp_data['verified'] = True
                otp_data['verified_at'] = datetime.now()
                self.logger.info(f"OTP verified successfully for {phone_number[-4:].rjust(len(phone_number), '*')}")
                return True, "OTP verified successfully"
            else:
                remaining_attempts = self.max_attempts - otp_data['attempts']
                return False, f"Invalid OTP. {remaining_attempts} attempts remaining"
                
        except Exception as e:
            self.logger.error(f"Error verifying OTP: {str(e)}")
            return False, f"Error verifying OTP: {str(e)}"
    
    def cleanup_expired_otp(self, phone_hash: str):
        """Remove expired OTP from storage"""
        if phone_hash in self.otp_storage:
            del self.otp_storage[phone_hash]
    
    def cleanup_expired_otps(self):
        """Clean up all expired OTPs"""
        current_time = datetime.now()
        expired_hashes = [
            phone_hash for phone_hash, data in self.otp_storage.items()
            if current_time > data['expires_at']
        ]
        
        for phone_hash in expired_hashes:
            self.cleanup_expired_otp(phone_hash)
        
        if expired_hashes:
            self.logger.info(f"Cleaned up {len(expired_hashes)} expired OTPs")
    
    def get_otp_status(self, phone_number: str) -> Optional[Dict]:
        """Get OTP status for phone number"""
        try:
            normalized_phone = self._normalize_phone_number(phone_number)
            phone_hash = self._hash_phone_number(normalized_phone)
            
            if phone_hash not in self.otp_storage:
                return None
            
            otp_data = self.otp_storage[phone_hash]
            return {
                'exists': True,
                'verified': otp_data.get('verified', False),
                'expired': datetime.now() > otp_data['expires_at'],
                'attempts': otp_data.get('attempts', 0),
                'max_attempts': self.max_attempts,
                'expires_at': otp_data['expires_at'].isoformat(),
                'created_at': otp_data['created_at'].isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting OTP status: {str(e)}")
            return None


# Global instance
otp_service = OTPService()