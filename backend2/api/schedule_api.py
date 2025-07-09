"""
Schedule-related API endpoints
Handles availability checking for appointment booking
Simplified version using static schedule.json and direct Kolla API calls
"""
import json
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/api", tags=["schedule"])

# Kolla API configuration
KOLLA_BASE_URL = os.getenv("KOLLA_BASE_URL", "https://unify.kolla.dev/dental/v1")
KOLLA_HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {os.getenv('KOLLA_BEARER_TOKEN')}",
    "connector-id": os.getenv("KOLLA_CONNECTOR_ID", "eaglesoft"),
    "consumer-id": os.getenv("KOLLA_CONSUMER_ID", "dajc")
}

def load_schedule():
    """Load static schedule from schedule.json"""
    schedule_file = Path(__file__).parent.parent.parent / "schedule.json"
    try:
        with open(schedule_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading schedule.json: {e}")
        return {}

def parse_time_to_minutes(time_str):
    """Convert time string like '9:00 AM' to minutes from midnight"""
    try:
        time_obj = datetime.strptime(time_str, "%I:%M %p")
        return time_obj.hour * 60 + time_obj.minute
    except ValueError:
        try:
            time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.hour * 60 + time_obj.minute
        except ValueError:
            return None

def minutes_to_time_str(minutes):
    """Convert minutes from midnight back to time string"""
    hours = minutes // 60
    mins = minutes % 60
    if hours == 0:
        return f"12:{mins:02d} AM"
    elif hours < 12:
        return f"{hours}:{mins:02d} AM"
    elif hours == 12:
        return f"12:{mins:02d} PM"
    else:
        return f"{hours-12}:{mins:02d} PM"

def generate_time_slots(open_time, close_time, slot_duration=30):
    """Generate all possible appointment slots for a day"""
    open_minutes = parse_time_to_minutes(open_time)
    close_minutes = parse_time_to_minutes(close_time)
    
    if open_minutes is None or close_minutes is None:
        return []
    
    slots = []
    current_minutes = open_minutes
    
    while current_minutes + slot_duration <= close_minutes:
        slot_time = minutes_to_time_str(current_minutes)
        slots.append(slot_time)
        current_minutes += slot_duration
    
    return slots

def get_booked_appointments(start_date, end_date):
    """Fetch appointments from Kolla API for the date range"""
    try:
        # Format dates for the API filter
        start_filter = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_filter = end_date.strftime("%Y-%m-%dT23:59:59Z")
        
        # Build the filter query
        filter_query = f"start_time > '{start_filter}' AND start_time < '{end_filter}'"
        
        url = f"{KOLLA_BASE_URL}/appointments"
        params = {"filter": filter_query}
        
        print(f"📞 Calling Kolla API: {url}")
        print(f"   Filter: {filter_query}")
        print(f"   Headers: {KOLLA_HEADERS}")
        
        response = requests.get(url, headers=KOLLA_HEADERS, params=params)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return []
        
        response.raise_for_status()
        
        data = response.json()
        appointments = data.get("appointments", [])
        
        print(f"   ✅ Retrieved {len(appointments)} appointments")
        if len(appointments) > 0:
            print(f"   📋 First appointment sample: {appointments[0].get('start_time', 'N/A')} - {appointments[0].get('wall_start_time', 'N/A')}")
        return appointments
        
    except Exception as e:
        print(f"   ❌ Error fetching appointments: {e}")
        return []

async def get_availability(date: str):
    """
    Simple availability API - takes a date, returns 3 days of availability
    Uses static schedule.json and direct Kolla API calls
    """
    print(f"🔍 GET_AVAILABILITY: {date} (+ next 2 days) - UPDATED OVERLAP LOGIC")
    
    try:
        # Parse the starting date
        start_date = datetime.strptime(date, "%Y-%m-%d")
        end_date = start_date + timedelta(days=2)  # 3 days total
        
        # Load static schedule
        schedule = load_schedule()
        if not schedule:
            return {
                "success": False,
                "error": "Could not load clinic schedule",
                "requested_date": date,
                "availability": {}
            }
        
        # Get all appointments for the 3-day period
        all_appointments = get_booked_appointments(start_date, end_date)
        print(f"📋 Total appointments fetched: {len(all_appointments)}")
        
        availability_data = {}
        total_free_slots = 0
        
        # Process each day
        for i in range(3):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%A")
            
            # Get clinic schedule for this day
            day_schedule = schedule.get(day_name, {})
            status = day_schedule.get("status", "Open")
            
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
            
            # Generate all possible slots for this day
            open_time = day_schedule.get("open", "9:00 AM")
            close_time = day_schedule.get("close", "5:00 PM")
            all_slots = generate_time_slots(open_time, close_time, 30)  # 30-minute slots
            
            # Filter appointments for this specific day
            date_str_for_comparison = current_date.strftime("%Y-%m-%d")
            print(f"   🔍 Looking for appointments on {date_str_for_comparison}")
            
            # Get all time slots that are blocked by appointments
            blocked_slots = set()
            appointments_found_for_day = 0
            
            for apt in all_appointments:
                # Skip cancelled appointments
                if apt.get("cancelled", False):
                    print(f"   ⏭️ Skipping cancelled appointment: {apt.get('contact', {}).get('given_name', 'N/A')}")
                    continue
                    
                # Use wall_start_time and wall_end_time (local time)
                wall_start_time = apt.get("wall_start_time", "")
                wall_end_time = apt.get("wall_end_time", "")
                
                if wall_start_time and wall_end_time:
                    try:
                        # Parse appointment start and end times
                        apt_start = datetime.strptime(wall_start_time, "%Y-%m-%d %H:%M:%S")
                        apt_end = datetime.strptime(wall_end_time, "%Y-%m-%d %H:%M:%S")
                        apt_date_str = apt_start.strftime("%Y-%m-%d")
                        
                        # Check if appointment is on this day
                        if apt_date_str == date_str_for_comparison:
                            appointments_found_for_day += 1
                            patient_name = f"{apt.get('contact', {}).get('given_name', 'N/A')} {apt.get('contact', {}).get('family_name', 'N/A')}"
                            
                            # Calculate which 30-minute slots this appointment blocks
                            # Generate all possible 30-minute slots and check which ones overlap
                            slots_blocked_by_this_apt = []
                            for slot_time_str in all_slots:
                                # Convert slot string to datetime for overlap checking
                                slot_datetime = datetime.strptime(f"{date_str_for_comparison} {slot_time_str}", "%Y-%m-%d %I:%M %p")
                                slot_end_datetime = slot_datetime + timedelta(minutes=30)
                                
                                # Check if this 30-minute slot overlaps with the appointment
                                # Overlap occurs if: slot_start < apt_end AND slot_end > apt_start
                                if slot_datetime < apt_end and slot_end_datetime > apt_start:
                                    blocked_slots.add(slot_time_str)
                                    slots_blocked_by_this_apt.append(slot_time_str)
                            
                            duration_minutes = int((apt_end - apt_start).total_seconds() / 60)
                            print(f"   📍 {patient_name}: {apt_start.strftime('%I:%M %p')} - {apt_end.strftime('%I:%M %p')} ({duration_minutes}min)")
                            print(f"      → Blocks slots: {slots_blocked_by_this_apt}")
                            
                    except Exception as e:
                        print(f"   ⚠️ Could not parse appointment times: {wall_start_time} - {wall_end_time} - {e}")
            
            print(f"   📊 Found {appointments_found_for_day} appointments for {date_str_for_comparison}")
            print(f"   � Blocked slots: {sorted(blocked_slots)}")
            
            # Convert blocked slots to booked_times list for compatibility
            booked_times = list(blocked_slots)
            
            # Calculate available slots
            available_slots = [slot for slot in all_slots if slot not in booked_times]
            
            free_slots_count = len(available_slots)
            booked_slots_count = len(booked_times)
            total_slots = len(all_slots)
            total_free_slots += free_slots_count
            
            availability_data[date_str] = {
                "date": date_str,
                "day": day_name,
                "status": "Open" if available_slots else "Fully booked",
                "free_slots": free_slots_count,
                "booked_slots": booked_slots_count,
                "total_slots": total_slots,
                "available_times": available_slots[:10]  # Show up to 10 slots
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
            "requested_date": date,
            "availability": {}
        }

async def debug_appointments(date: str):
    """
    Debug endpoint to show raw appointment data from Kolla API
    """
    try:
        start_date = datetime.strptime(date, "%Y-%m-%d")
        end_date = start_date + timedelta(days=2)
        
        appointments = get_booked_appointments(start_date, end_date)
        
        print(f"\n🔍 DEBUG: Found {len(appointments)} appointments")
        for i, apt in enumerate(appointments):
            print(f"  Appointment {i+1}:")
            print(f"    start_time: {apt.get('start_time', 'N/A')}")
            print(f"    wall_start_time: {apt.get('wall_start_time', 'N/A')}")
            print(f"    end_time: {apt.get('end_time', 'N/A')}")
            print(f"    wall_end_time: {apt.get('wall_end_time', 'N/A')}")
            print(f"    patient: {apt.get('contact', {}).get('given_name', 'N/A')} {apt.get('contact', {}).get('family_name', 'N/A')}")
            print(f"    description: {apt.get('short_description', 'N/A')}")
            print("")
        
        return {
            "success": True,
            "date_range": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_appointments": len(appointments),
            "appointments": appointments
        }
        
    except Exception as e:
        print(f"Debug error: {e}")
        return {"success": False, "error": str(e)}
