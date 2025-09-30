"""
API endpoints for token management
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import logging

from services.auth_service import auth_service, require_api_key

router = APIRouter(prefix="/auth", tags=["authentication"])

class GenerateKeyResponse(BaseModel):
    """Response model for key generation"""
    api_key: str
    message: str

class ApiKeyRequest(BaseModel):
    """Request model for API key operations"""
    api_key: str

class ApiKeysResponse(BaseModel):
    """Response model for listing API keys"""
    api_keys: List[str]
    count: int

@router.post("/generate-key", response_model=GenerateKeyResponse)
async def generate_new_api_key(authenticated: bool = Depends(require_api_key)):
    """Generate a new API key (requires existing authentication)"""
    try:
        new_key = auth_service.generate_api_key()
        auth_service.add_api_key(new_key)
        
        logging.info("🔑 New API key generated via API")
        
        return GenerateKeyResponse(
            api_key=new_key,
            message="New API key generated successfully. Store this key securely - it cannot be retrieved again."
        )
    except Exception as e:
        logging.error(f"❌ Error generating API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate API key")

@router.get("/keys", response_model=ApiKeysResponse)
async def list_api_keys(authenticated: bool = Depends(require_api_key)):
    """List all API keys (masked for security)"""
    try:
        keys = auth_service.list_api_keys()
        
        return ApiKeysResponse(
            api_keys=keys,
            count=len(keys)
        )
    except Exception as e:
        logging.error(f"❌ Error listing API keys: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")

@router.delete("/keys")
async def revoke_api_key(
    request: ApiKeyRequest, 
    authenticated: bool = Depends(require_api_key)
):
    """Revoke an API key (requires existing authentication)"""
    try:
        success = auth_service.remove_api_key(request.api_key)
        
        if success:
            logging.info(f"🗑️ API key revoked via API: {request.api_key[:10]}...")
            return {"message": "API key revoked successfully"}
        else:
            raise HTTPException(status_code=404, detail="API key not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Error revoking API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")

@router.get("/test")
async def test_authentication(authenticated: bool = Depends(require_api_key)):
    """Test endpoint to verify authentication is working"""
    return {
        "message": "Authentication successful!",
        "authenticated": True,
        "timestamp": "2025-09-27"
    }