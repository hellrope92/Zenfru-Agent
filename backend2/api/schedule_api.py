"""
Schedule-related API endpoints
Handles schedule viewing, availability checking, and time slot management
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException

# Import shared models
from .models import CheckSlotsRequest, CheckServiceSlotsRequest

# Import dependencies (will be injected from main.py)
from services.getkolla_service import GetKollaService

router = APIRouter(prefix="/api", tags=["schedule"])

def get_next_n_days(n: int = 5) -> List[str]:
    """Get the next N days starting from tomorrow"""
    today = datetime.now()
    days = []
    for i in range(1, n + 1):  # Start from tomorrow
        future_date = today + timedelta(days=i)
        day_name = future_date.strftime("%A")
        days.append(day_name)
    return days

def get_available_slots_for_day(day: str, schedule: Dict, bookings: List) -> List[Dict[str, str]]:
    """Get available time slots for a specific day"""
    if day not in schedule:
        return []
    
    day_info = schedule[day]
    
    # Check if clinic is closed
    if day_info.get("status") == "Closed":
        return []
    
    # Generate time slots based on open/close times
    open_time = day_info.get("open", "9:00 AM")
    close_time = day_info.get("close", "5:00 PM")
    doctor = day_info.get("doctor", "Available Doctor")
    
    # Simple slot generation (every hour)
    slots = []
    if "9:00 AM" in open_time:
        base_slots = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"]
        
        # Filter based on close time
        if "4:00 PM" in close_time:
            base_slots = [slot for slot in base_slots if slot not in ["5:00 PM"]]
        elif "5:00 PM" in close_time:
            base_slots = [slot for slot in base_slots if slot not in []]
        elif "6:00 PM" in close_time:
            base_slots.append("5:00 PM")
        
        for slot in base_slots:
            # Check if slot is already booked
            is_booked = any(
                booking.get("day") == day and booking.get("time") == slot 
                for booking in bookings
            )
            
            if not is_booked:
                slots.append({
                    "time": slot,
                    "doctor": doctor,
                    "duration_minutes": 30
                })
    
    return slots

async def get_current_day():
    """Get the current day of the week"""
    current_day = datetime.now().strftime("%A")
    current_date = datetime.now().strftime("%Y-%m-%d")
    print(f"🗓️ GET_CURRENT_DAY: {current_day}")
    
    return {
        "day": current_day,
        "date": current_date,
    }

async def check_available_slots(
    request: CheckSlotsRequest, 
    getkolla_service: GetKollaService, 
    schedule: Dict, 
    bookings: List
):
    """Check available appointment slots for next 7 days using GetKolla API"""
    current_day = datetime.now().strftime("%A")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"🔍 CHECK_AVAILABLE_SLOTS:")
    print(f"   Current Day: {current_day} ({current_date})")
    print(f"   Checking next 7 days with GetKolla API integration...")
    
    try:
        # Get available slots from GetKolla service
        available_slots_by_day = getkolla_service.get_available_slots_next_7_days()
        
        # Transform the data to match the expected format
        all_available_slots = []
        days_checked = []
        
        for day_info, slots in available_slots_by_day.items():
            day_name = day_info.split(' (')[0]  # Extract day name from "Monday (2025-06-18)"
            days_checked.append(day_name)
            
            for slot_time in slots:
                all_available_slots.append({
                    "day": day_name,
                    "time": slot_time,
                    "available": True,
                    "doctor": getkolla_service.schedule.get(day_name.split()[0], {}).get("doctor", "Available Doctor")
                })
        
        print(f"   ✅ Total available slots found: {len(all_available_slots)}")
        print(f"   📅 Days with availability: {len(available_slots_by_day)}")
        
        return {
            "available_slots": all_available_slots,
            "days_checked": days_checked,
            "current_day": current_day,
            "slots_by_day": available_slots_by_day,
            "total_slots": len(all_available_slots)
        }
        
    except Exception as e:
        print(f"   ❌ Error fetching available slots: {e}")
        # Fallback to original logic if GetKolla service fails
        next_days = get_next_n_days(5)
        all_available_slots = []
        
        for day in next_days:
            day_slots = get_available_slots_for_day(day, schedule, bookings)
            if day_slots:
                for slot in day_slots:
                    slot["day"] = day
                    all_available_slots.append(slot)
        
        return {
            "available_slots": all_available_slots,
            "days_checked": next_days,
            "current_day": current_day,
            "error": "GetKolla API unavailable, using fallback logic"
        }

async def get_schedule(getkolla_service: GetKollaService, days: int = 7):
    """Get available appointment schedule for the next N days using GetKolla API"""
    print(f"📅 GET_SCHEDULE: Fetching schedule for next {days} days")
    
    try:
        if days == 7:
            # Use the optimized method for 7 days
            available_slots_by_day = getkolla_service.get_available_slots_next_7_days()
            
            # Transform to a more structured format
            schedule_data = {}
            total_available_slots = 0
            
            for day_info, slots in available_slots_by_day.items():
                # Extract day name and date from "Monday (2025-06-18)" format
                parts = day_info.split(' (')
                day_name = parts[0]
                date_str = parts[1].rstrip(')')
                
                # Get doctor info from schedule
                day_schedule = getkolla_service.schedule.get(day_name, {})
                doctor = day_schedule.get("doctor", "Available Doctor")
                open_time = day_schedule.get("open", "9:00 AM")
                close_time = day_schedule.get("close", "5:00 PM")
                
                schedule_data[date_str] = {
                    "day": day_name,
                    "date": date_str,
                    "status": "Open" if slots else "No availability",
                    "open_time": open_time,
                    "close_time": close_time,
                    "doctor": doctor,
                    "available_slots": slots,
                    "total_slots": len(slots)
                }
                total_available_slots += len(slots)
        else:
            # For custom number of days, calculate individually
            schedule_data = {}
            total_available_slots = 0
            today = datetime.now()
            
            for i in range(days):
                target_date = today + timedelta(days=i)
                date_str = target_date.strftime("%Y-%m-%d")
                day_name = target_date.strftime("%A")
                
                # Get available slots for this specific date
                slots = getkolla_service.get_available_slots_for_date(target_date)
                
                # Get doctor info from schedule
                day_schedule = getkolla_service.schedule.get(day_name, {})
                doctor = day_schedule.get("doctor", "Available Doctor")
                open_time = day_schedule.get("open", "9:00 AM")
                close_time = day_schedule.get("close", "5:00 PM")
                status = day_schedule.get("status", "Open")
                
                if status == "Closed":
                    schedule_data[date_str] = {
                        "day": day_name,
                        "date": date_str,
                        "status": "Closed",
                        "open_time": None,
                        "close_time": None,
                        "doctor": None,
                        "available_slots": [],
                        "total_slots": 0
                    }
                else:
                    schedule_data[date_str] = {
                        "day": day_name,
                        "date": date_str,
                        "status": "Open" if slots else "No availability",
                        "open_time": open_time,
                        "close_time": close_time,
                        "doctor": doctor,
                        "available_slots": slots,
                        "total_slots": len(slots)
                    }
                    total_available_slots += len(slots)
        
        print(f"   ✅ Schedule generated successfully")
        print(f"   📊 Total available slots: {total_available_slots}")
        print(f"   📅 Days with availability: {len([d for d in schedule_data.values() if d['total_slots'] > 0])}")
        
        return {
            "success": True,
            "days_requested": days,
            "schedule": schedule_data,
            "summary": {
                "total_available_slots": total_available_slots,
                "days_with_availability": len([d for d in schedule_data.values() if d['total_slots'] > 0]),
                "days_closed": len([d for d in schedule_data.values() if d['status'] == 'Closed']),
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        print(f"   ❌ Error generating schedule: {e}")
        return {
            "success": False,
            "error": str(e),
            "schedule": {},
            "summary": {
                "total_available_slots": 0,
                "days_with_availability": 0,
                "days_closed": 0,
                "generated_at": datetime.now().isoformat()
            }
        }

async def get_availability(date: str, getkolla_service: GetKollaService):
    """
    Simple availability API - takes a date, returns 3 days of availability
    Uses GetKolla API to get clinic schedule + appointments, calculates free slots
    OPTIMIZED: Makes single API call for all 3 days
    """
    print(f"🔍 GET_AVAILABILITY: {date} (+ next 2 days)")
    
    try:
        # Parse the starting date
        start_date = datetime.strptime(date, "%Y-%m-%d")
        end_date = start_date + timedelta(days=2)  # 3 days total
        
        # Make a single API call to get appointments for all 3 days
        print(f"📞 Making single API call for date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        start_of_range = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_range = end_date.replace(hour=23, minute=59, second=59, microsecond=0)
        all_booked_appointments = getkolla_service.get_booked_appointments(start_of_range, end_of_range)
        
        availability_data = {}
        total_free_slots = 0
        
        # Process each day using the cached appointment data
        for i in range(3):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%A")
            
            # Get clinic schedule info for this day
            day_schedule = getkolla_service.schedule.get(day_name, {})
            status = day_schedule.get("status", "Open")
              # Filter appointments for just this day
            day_start = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_appointments = []
            for apt in all_booked_appointments:
                apt_time = getkolla_service._parse_appointment_time(apt)
                if apt_time and day_start <= apt_time < day_end:
                    day_appointments.append(apt)
              # Calculate available slots for this day
            available_slots = getkolla_service._get_available_slots_for_date_with_appointments(current_date, day_appointments)
            
            # Handle closed days
            if status == "Closed":
                availability_data[date_str] = {
                    "date": date_str,
                    "day": day_name,
                    "status": "Closed",
                    "free_slots": 0,
                    "booked_slots": 0,
                    "total_slots": 0,
                    "available_times": []
                }
                print(f"   📅 {date_str} ({day_name}): Closed")
                continue
            
            # Calculate total slots and booked slots for this day
            day_schedule = getkolla_service.schedule.get(day_name, {})
            open_time = day_schedule.get("open", "9:00 AM")
            close_time = day_schedule.get("close", "5:00 PM")
            duration = day_schedule.get("default_slot_duration", 30)
            lunch_break = day_schedule.get("lunch_break")
            
            # Generate all possible slots accounting for lunch breaks (same method used for available slots)
            all_possible_slots = getkolla_service._generate_time_slots(open_time, close_time, duration, lunch_break)
            total_slots = len(all_possible_slots)
            
            free_slots_count = len(available_slots)
            booked_slots_count = total_slots - free_slots_count
            total_free_slots += free_slots_count
            
            availability_data[date_str] = {
                "date": date_str,
                "day": day_name,
                "status": "Closed" if status == "Closed" else ("Open" if available_slots else "Fully booked"),
                "free_slots": free_slots_count,
                "booked_slots": booked_slots_count,
                "total_slots": total_slots,
                "available_times": available_slots if len(available_slots) <= 10 else available_slots  # Show up to 10 slots
            }
            
            print(f"   📅 {date_str} ({day_name}): {free_slots_count} free, {booked_slots_count} booked out of {total_slots} total")
        
        print(f"   ✅ Found {total_free_slots} total free slots across 3 days")
        
        return {
            "success": True,
            "requested_date": date,
            "availability": availability_data,
            "summary": {
                "total_free_slots": total_free_slots,
                "days_checked": 3
            }
        }
        
    except ValueError:
        print(f"   ❌ Invalid date format: {date}")
        return {
            "success": False,
            "error": "Invalid date format. Please use YYYY-MM-DD format.",
            "requested_date": date,
            "availability": {}
        }
    except Exception as e:
        print(f"   ❌ Error getting schedule for date: {e}")
        return {
            "success": False,
            "error": str(e),
            "available_slots": [],
            "total_available": 0
        }
