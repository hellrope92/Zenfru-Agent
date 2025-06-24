"""
Availability API endpoint
Handles fetching real-time availability for the next 3 days from the requested date
Uses local caching with 24-hour refresh for schedules from Kolla API
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query

from services.local_cache_service import LocalCacheService
from services.availability_service import AvailabilityService

router = APIRouter(prefix="/api", tags=["availability"])

cache_service = LocalCacheService()
availability_service = AvailabilityService()

@router.get("/availability")
async def get_availability(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Fetches real-time availability for the next 3 days from the requested date
    Uses caching for schedule data from Kolla API (24-hour cache)
    """
    try:
        # Validate date format
        try:
            start_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Calculate the next 3 days
        dates_to_check = []
        for i in range(3):
            check_date = start_date + timedelta(days=i)
            dates_to_check.append(check_date.strftime("%Y-%m-%d"))
        
        availability_data = {}
        
        # Check if we have cached schedule data for the date range
        end_date = (start_date + timedelta(days=2)).strftime("%Y-%m-%d")
        schedule_cache_key = f"{date}_{end_date}"
        
        # Try to get cached schedule data
        cached_schedule = cache_service.get_schedule(schedule_cache_key)
        
        if cached_schedule:
            # Use cached schedule data and process availability
            availability_data = await process_cached_schedule_data(cached_schedule, dates_to_check)
        else:
            # Fetch fresh schedule data from Kolla API
            schedule_data = await fetch_schedule_from_kolla(date, end_date)
            if schedule_data:
                # Store in cache
                cache_service.store_schedule(schedule_cache_key, schedule_data)
                # Process availability
                availability_data = await process_schedule_data(schedule_data, dates_to_check)
            else:
                # Fallback to empty availability
                for check_date in dates_to_check:
                    availability_data[check_date] = {
                        "available_slots": [],
                        "message": "No schedule data available for this date"
                    }
        
        return {
            "success": True,
            "requested_date": date,
            "availability": availability_data,
            "total_days": len(dates_to_check),
            "cache_used": cached_schedule is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching availability: {str(e)}")

async def fetch_schedule_from_kolla(start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
    """Fetch schedule data from Kolla API using the loadSchedule endpoint"""
    try:
        # Get practice schedule from Kolla API
        practice_schedule = availability_service.get_practice_schedule(start_date, end_date)
        
        # Get current appointments
        appointments = availability_service.get_appointments(start_date, end_date)
        
        # Return the raw schedule data in the format expected by the user
        return {
            "resource": None,
            "schedule": practice_schedule.get("schedule", []),
            "appointments": appointments.get("appointments", []),
            "fetched_at": datetime.now().isoformat(),
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
    except Exception as e:
        print(f"Error fetching schedule from Kolla API: {e}")
        return None

async def process_cached_schedule_data(cached_data: Dict[str, Any], dates_to_check: List[str]) -> Dict[str, Any]:
    """Process cached schedule data to generate availability for requested dates"""
    availability_data = {}
    
    schedule_blocks = cached_data.get("schedule", [])
    appointments = cached_data.get("appointments", [])
    
    for check_date in dates_to_check:
        # Find schedule blocks for this date
        date_blocks = [
            block for block in schedule_blocks 
            if block.get("date") == check_date
        ]
        
        # Find appointments for this date
        date_appointments = [
            apt for apt in appointments
            if apt.get("start_time", "").startswith(check_date)
        ]
        
        # Calculate available slots
        available_slots = calculate_available_slots(date_blocks, date_appointments, check_date)
        
        availability_data[check_date] = {
            "date": check_date,
            "available_slots": available_slots,
            "schedule_blocks": date_blocks,
            "booked_appointments": len(date_appointments)
        }
    
    return availability_data

async def process_schedule_data(schedule_data: Dict[str, Any], dates_to_check: List[str]) -> Dict[str, Any]:
    """Process fresh schedule data to generate availability for requested dates"""
    # This is the same logic as process_cached_schedule_data
    return await process_cached_schedule_data(schedule_data, dates_to_check)

def calculate_available_slots(schedule_blocks: List[Dict], appointments: List[Dict], date: str) -> List[Dict[str, Any]]:
    """Calculate available 30-minute slots based on schedule blocks and appointments"""
    available_slots = []
    
    if not schedule_blocks:
        return available_slots
    
    # Process each schedule block for the date
    for block in schedule_blocks:
        if block.get("date") != date:
            continue
            
        # Get the time blocks for this date
        time_blocks = block.get("blocks", [])
        
        for time_block in time_blocks:
            start_time_str = time_block.get("start_time", "00:00")
            end_time_str = time_block.get("end_time", "23:59")
            
            # Convert to datetime objects for the specific date
            try:
                start_datetime = datetime.strptime(f"{date} {start_time_str}", "%Y-%m-%d %H:%M")
                end_datetime = datetime.strptime(f"{date} {end_time_str}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            
            # Generate 30-minute slots
            current_time = start_datetime
            while current_time + timedelta(minutes=30) <= end_datetime:
                slot_end_time = current_time + timedelta(minutes=30)
                
                # Check if this slot conflicts with any appointments
                is_available = True
                for appointment in appointments:
                    apt_start_str = appointment.get("start_time", "")
                    apt_end_str = appointment.get("end_time", "")
                    
                    if apt_start_str and apt_end_str:
                        try:
                            apt_start = datetime.fromisoformat(apt_start_str.replace("Z", "+00:00"))
                            apt_end = datetime.fromisoformat(apt_end_str.replace("Z", "+00:00"))
                            
                            # Check for overlap
                            if (current_time < apt_end and slot_end_time > apt_start):
                                is_available = False
                                break
                        except ValueError:
                            continue
                
                if is_available:
                    available_slots.append({
                        "start_time": current_time.strftime("%H:%M"),
                        "end_time": slot_end_time.strftime("%H:%M"),
                        "datetime": current_time.isoformat(),
                        "duration_minutes": 30,
                        "available": True
                    })
                
                current_time += timedelta(minutes=30)
    
    return available_slots

@router.get("/availability/refresh")
async def refresh_availability_cache():
    """Manually refresh the availability cache for the next 7 days"""
    try:
        today = datetime.now()
        refreshed_ranges = []
        
        # Refresh cache in 3-day chunks to match the API usage pattern
        for start_offset in range(0, 7, 3):
            start_date = (today + timedelta(days=start_offset)).strftime("%Y-%m-%d")
            end_offset = min(start_offset + 2, 6)
            end_date = (today + timedelta(days=end_offset)).strftime("%Y-%m-%d")
            
            schedule_cache_key = f"{start_date}_{end_date}"
            
            # Fetch fresh data from Kolla API
            schedule_data = await fetch_schedule_from_kolla(start_date, end_date)
            
            if schedule_data:
                cache_service.store_schedule(schedule_cache_key, schedule_data)
                refreshed_ranges.append(f"{start_date} to {end_date}")
        
        # Cleanup old data
        cache_service.cleanup_old_data()
        
        return {
            "success": True,
            "message": "Cache refreshed successfully",
            "refreshed_ranges": refreshed_ranges,
            "refreshed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing cache: {str(e)}")

@router.get("/availability/cache-status")
async def get_cache_status():
    """Get information about the current cache status"""
    try:
        # Get all cached schedules
        all_schedules = cache_service.get_all_schedules(days=7)
        
        cache_info = {
            "cached_date_ranges": list(all_schedules.keys()),
            "total_cached_ranges": len(all_schedules),
            "cache_coverage": {},
            "checked_at": datetime.now().isoformat()
        }
        
        # Check coverage for next 7 days
        today = datetime.now()
        for i in range(7):
            check_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            
            # Look for any cache entry that covers this date
            is_cached = False
            for cache_key in all_schedules.keys():
                if "_" in cache_key:
                    start_date, end_date = cache_key.split("_")
                    if start_date <= check_date <= end_date:
                        is_cached = True
                        break
            
            cache_info["cache_coverage"][check_date] = is_cached
        
        return cache_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache status: {str(e)}")
