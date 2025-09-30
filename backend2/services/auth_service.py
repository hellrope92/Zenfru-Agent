"""
Authentication service for API key validation
"""

import os
from typing import List, Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class AuthService:
    """Service for handling API key authentication"""
    
    def __init__(self):
        self.security = HTTPBearer()
        self.api_keys = self._load_api_keys()
        logging.info(f"🔐 Loaded {len(self.api_keys)} API keys for authentication")
    
    def _load_api_keys(self) -> List[str]:
        """Load API keys from environment variables"""
        keys_str = os.getenv("API_KEYS", "")
        if not keys_str:
            # Generate a default key for development if none provided
            default_key = secrets.token_urlsafe(32)
            logging.warning(f"⚠️ No API_KEYS found in environment. Generated development key: {default_key}")
            logging.warning("⚠️ Set API_KEYS environment variable for production!")
            return [default_key]
        
        keys = [key.strip() for key in keys_str.split(",") if key.strip()]
        if not keys:
            raise ValueError("API_KEYS environment variable is set but contains no valid keys")
        
        return keys
    
    def verify_token(self, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())) -> bool:
        """Verify the provided API token"""
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="Authorization header required"
            )
        
        token = credentials.credentials
        if token not in self.api_keys:
            logging.warning(f"🚫 Invalid API key attempt: {token[:10]}...")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
        
        logging.info(f"✅ Valid API key authenticated: {token[:10]}...")
        return True
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a new secure API key"""
        return secrets.token_urlsafe(32)
    
    def add_api_key(self, new_key: str) -> bool:
        """Add a new API key to the list (runtime only)"""
        if new_key not in self.api_keys:
            self.api_keys.append(new_key)
            logging.info(f"🔑 Added new API key: {new_key[:10]}...")
            return True
        return False
    
    def remove_api_key(self, key_to_remove: str) -> bool:
        """Remove an API key from the list (runtime only)"""
        if key_to_remove in self.api_keys:
            self.api_keys.remove(key_to_remove)
            logging.info(f"🗑️ Removed API key: {key_to_remove[:10]}...")
            return True
        return False
    
    def list_api_keys(self) -> List[str]:
        """List all API keys (masked for security)"""
        return [f"{key[:10]}..." for key in self.api_keys]

# Global auth service instance
auth_service = AuthService()

# FastAPI dependency for authentication
def require_api_key(credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())) -> bool:
    """FastAPI dependency that requires valid API key authentication"""
    return auth_service.verify_token(credentials)

# Convenience function for manual verification
def verify_api_key(token: str) -> bool:
    """Manually verify an API key"""
    return token in auth_service.api_keys