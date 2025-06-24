import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.local_cache_service import LocalCacheService

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

router = APIRouter(prefix="/api", tags=["appointment-details"])
cache_service = LocalCacheService()

class AppointmentDetailsRequest(BaseModel):
    name: str
    dob: str

# Endpoints removed as requested
