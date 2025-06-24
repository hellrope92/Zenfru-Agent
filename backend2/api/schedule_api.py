"""
Schedule-related API endpoints
Handles availability checking for appointment booking
"""
from datetime import datetime, timedelta
from fastapi import APIRouter

# Import dependencies (will be injected from main.py)
from services.getkolla_service import GetKollaService

router = APIRouter(prefix="/api", tags=["schedule"])

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
