"""
OTP API endpoints for sending and verifying SMS OTPs
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from services.otp_service import otp_service
from services.auth_service import require_api_key

router = APIRouter(prefix="/api/otp", tags=["otp"])
logger = logging.getLogger(__name__)


class SendOTPRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number to send OTP to (with or without country code)")
    
    class Config:
        schema_extra = {
            "example": {
                "phone_number": "+1234567890"
            }
        }


class VerifyOTPRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number that received the OTP")
    otp: str = Field(..., description="The OTP code to verify", min_length=4, max_length=10)
    otp_id: Optional[str] = Field(None, description="Optional OTP ID for additional verification")
    
    class Config:
        schema_extra = {
            "example": {
                "phone_number": "+1234567890",
                "otp": "123456",
                "otp_id": "otp_hash_20241018"
            }
        }


class OTPStatusRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number to check OTP status for")
    
    class Config:
        schema_extra = {
            "example": {
                "phone_number": "+1234567890"
            }
        }


@router.post("/send")
async def send_otp(
    request: SendOTPRequest,
    authenticated: bool = Depends(require_api_key)
):
    """
    Send OTP via SMS to the specified phone number
    
    - **phone_number**: Phone number to send OTP to (will be normalized)
    - Returns OTP ID for tracking and additional security
    """
    try:
        success, message, otp_id = otp_service.send_otp(request.phone_number)
        
        if success:
            logger.info(f"OTP sent successfully to {request.phone_number}")
            return {
                "success": True,
                "message": message,
                "otp_id": otp_id,
                "phone_number": request.phone_number,
                "expires_in_minutes": otp_service.otp_expiry_minutes
            }
        else:
            logger.warning(f"Failed to send OTP to {request.phone_number}: {message}")
            raise HTTPException(status_code=400, detail=message)
    
    except Exception as e:
        logger.error(f"Error in send_otp endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/verify")
async def verify_otp(
    request: VerifyOTPRequest,
    authenticated: bool = Depends(require_api_key)
):
    """
    Verify OTP for the specified phone number
    
    - **phone_number**: Phone number that received the OTP
    - **otp**: The OTP code to verify
    - **otp_id**: Optional OTP ID for additional security (recommended)
    """
    try:
        success, message = otp_service.verify_otp(
            request.phone_number, 
            request.otp, 
            request.otp_id
        )
        
        if success:
            logger.info(f"OTP verified successfully for {request.phone_number}")
            return {
                "success": True,
                "message": message,
                "verified": True,
                "phone_number": request.phone_number
            }
        else:
            logger.warning(f"OTP verification failed for {request.phone_number}: {message}")
            return {
                "success": False,
                "message": message,
                "verified": False,
                "phone_number": request.phone_number
            }
    
    except Exception as e:
        logger.error(f"Error in verify_otp endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/status")
async def get_otp_status(
    request: OTPStatusRequest,
    authenticated: bool = Depends(require_api_key)
):
    """
    Get OTP status for the specified phone number
    
    - **phone_number**: Phone number to check status for
    - Returns information about current OTP state
    """
    try:
        status = otp_service.get_otp_status(request.phone_number)
        
        if status is None:
            return {
                "success": True,
                "phone_number": request.phone_number,
                "exists": False,
                "message": "No OTP found for this phone number"
            }
        
        return {
            "success": True,
            "phone_number": request.phone_number,
            **status
        }
    
    except Exception as e:
        logger.error(f"Error in get_otp_status endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cleanup")
async def cleanup_expired_otps(
    authenticated: bool = Depends(require_api_key)
):
    """
    Manually cleanup expired OTPs (normally done automatically)
    
    - Removes all expired OTPs from memory
    - Useful for maintenance or testing
    """
    try:
        otp_service.cleanup_expired_otps()
        
        return {
            "success": True,
            "message": "Expired OTPs cleaned up successfully"
        }
    
    except Exception as e:
        logger.error(f"Error in cleanup_expired_otps endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Additional endpoint for testing (can be removed in production)
@router.get("/config")
async def get_otp_config(
    authenticated: bool = Depends(require_api_key)
):
    """
    Get OTP service configuration (for debugging)
    
    - Returns current OTP settings
    - Does not expose sensitive credentials
    """
    try:
        return {
            "success": True,
            "config": {
                "otp_length": otp_service.otp_length,
                "otp_expiry_minutes": otp_service.otp_expiry_minutes,
                "max_attempts": otp_service.max_attempts,
                "sms_provider": otp_service.sms_provider,
                "twilio_configured": bool(otp_service.twilio_account_sid and otp_service.twilio_auth_token),
                "textlocal_configured": bool(otp_service.textlocal_api_key),
                "active_otps_count": len(otp_service.otp_storage)
            }
        }
    
    except Exception as e:
        logger.error(f"Error in get_otp_config endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")