"""
Current Date/Time API
Provides current day and date information
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any
import pytz

router = APIRouter()

class CurrentDateTimeResponse(BaseModel):
    success: bool
    current_day: str
    current_date: str
    current_datetime: str
    timezone: str

@router.get("/get_current")
async def get_current() -> CurrentDateTimeResponse:
    """
    Get current day and date information
    Returns current day of week, date in YYYY-MM-DD format, and datetime
    """
    try:
        # Get current datetime in EST/EDT (New Jersey timezone)
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # Format the response
        current_day = now.strftime("%A")  # Full day name (e.g., "Monday")
        current_date = now.strftime("%Y-%m-%d")  # YYYY-MM-DD format
        current_datetime = now.strftime("%Y-%m-%d %H:%M:%S")  # Full datetime
        timezone = str(now.tzinfo)
        
        print(f"🕐 Current datetime requested: {current_day}, {current_date} at {now.strftime('%H:%M:%S')} {timezone}")
        
        return CurrentDateTimeResponse(
            success=True,
            current_day=current_day,
            current_date=current_date,
            current_datetime=current_datetime,
            timezone=timezone
        )
        
    except Exception as e:
        print(f"❌ Error getting current datetime: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get current datetime: {str(e)}")

# Alternative endpoint with different path structure if needed
@router.get("/current")
async def get_current_alternative() -> CurrentDateTimeResponse:
    """
    Alternative endpoint for getting current day and date information
    """
    return await get_current()