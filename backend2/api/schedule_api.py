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

# Provider ID mappings
DOCTOR_PROVIDER_MAPPING = {
    "Dr. Yuzvyak": "100",
    "Dr. Hanna": "001", 
    "Dr. Parmar": "101",
    "Dr. Lee": "102"
}

# Hygienist provider mappings
HYGIENIST_PROVIDER_MAPPING = {
    "Nadia Khan": "H20",
    "Imelda Soledad": "6"
}

# All possible hygienist provider IDs (including alternate IDs)
ALL_HYGIENIST_PROVIDER_IDS = ["H20", "6", "HO4"]

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

def get_provider_for_day(day_name, iscleaning=False):
    """Get the provider ID for a specific day and service type"""
    schedule = load_schedule()
    day_schedule = schedule.get(day_name, {})
    
    if iscleaning:
        # For cleaning appointments, return all possible hygienist provider IDs
        # This includes the scheduled hygienists plus any alternate provider IDs
        return ALL_HYGIENIST_PROVIDER_IDS
    else:
        # For doctor appointments, get the scheduled doctor for this day
        doctor_name = day_schedule.get("doctor", "")
        provider_id = DOCTOR_PROVIDER_MAPPING.get(doctor_name, "")
        return [provider_id] if provider_id else []

def get_hygienist_schedule_for_day(day_name, provider_id=None):
    """Get specific hygienist schedule details for a day"""
    schedule = load_schedule()
    day_schedule = schedule.get(day_name, {})
    hygienists = day_schedule.get("hygienists", [])
    
    if provider_id:
        # Return schedule for specific hygienist
        for hygienist in hygienists:
            if hygienist.get("provider_id") == provider_id:
                return hygienist
        return None
    else:
        # Return all hygienists for the day
        return hygienists

def filter_appointments_by_provider(appointments, provider_ids):
    """Filter appointments to only include specified provider IDs"""
    if not provider_ids:
        return []

    filtered_appointments = []
    for apt in appointments:
        # Check top-level provider_id
        apt_provider_id = apt.get("provider_id", "")
        if apt_provider_id and apt_provider_id in provider_ids:
            filtered_appointments.append(apt)
            continue

        # Check providers list (for Kolla API format)
        providers_list = apt.get("providers", [])
        for provider in providers_list:
            provider_remote_id = provider.get("remote_id", "")
            if provider_remote_id in provider_ids:
                filtered_appointments.append(apt)
                break

    return filtered_appointments

def generate_time_slots(open_time, close_time, slot_duration=30, lunch_start=None, lunch_end=None):
    """Generate all possible appointment slots for a day, excluding lunch break"""
    open_minutes = parse_time_to_minutes(open_time)
    close_minutes = parse_time_to_minutes(close_time)
    
    if open_minutes is None or close_minutes is None:
        return []
    
    # Convert lunch times to minutes if provided
    lunch_start_minutes = None
    lunch_end_minutes = None
    if lunch_start and lunch_end:
        lunch_start_minutes = parse_time_to_minutes(lunch_start)
        lunch_end_minutes = parse_time_to_minutes(lunch_end)
    
    slots = []
    current_minutes = open_minutes
    
    while current_minutes + slot_duration <= close_minutes:
        # Skip lunch break slots
        if lunch_start_minutes and lunch_end_minutes:
            # Check if this slot would overlap with lunch break
            slot_end_minutes = current_minutes + slot_duration
            if current_minutes < lunch_end_minutes and slot_end_minutes > lunch_start_minutes:
                # This slot overlaps with lunch, skip it
                current_minutes += slot_duration  # Move forward by slot duration to find next available slot
                continue
        
        slot_time = minutes_to_time_str(current_minutes)
        slots.append(slot_time)
        current_minutes += slot_duration
    
    return slots

def generate_hygienist_time_slots(day_name, provider_id):
    """Generate time slots for a specific hygienist on a specific day"""
    hygienist_schedule = get_hygienist_schedule_for_day(day_name, provider_id)
    
    if not hygienist_schedule:
        return []
    
    open_time = hygienist_schedule.get("open", "9:00 AM")
    close_time = hygienist_schedule.get("close", "5:00 PM")
    slot_duration = hygienist_schedule.get("slot_duration", 60)  # Default to 1 hour
    lunch_start = hygienist_schedule.get("lunch_start", "1:00 PM")  # Standard lunch if not specified
    lunch_end = hygienist_schedule.get("lunch_end", "2:00 PM")  # Standard lunch if not specified
    
    return generate_time_slots(open_time, close_time, slot_duration, lunch_start, lunch_end)

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
        
        
        response = requests.get(url, headers=KOLLA_HEADERS, params=params)
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ API Error: {response.text}")
            return []
        
        response.raise_for_status()
        
        data = response.json()
        appointments = data.get("appointments", [])
        

        return appointments
        
    except Exception as e:
        print(f"   ❌ Error fetching appointments: {e}")
        return []

async def get_availability(date: str, iscleaning: bool = False):
    """
    Enhanced availability API - takes a date and iscleaning flag, returns 3 days of availability
    Filters appointments by provider (doctor vs hygienist) based on iscleaning flag
    Uses static schedule.json and direct Kolla API calls
    """
    provider_type = "hygienist" if iscleaning else "doctor"
    
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
        
        availability_data = {}
        total_free_slots = 0
        
        # Process each day
        for i in range(3):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%A")
            
            # Get provider IDs for this day based on iscleaning flag
            provider_ids = get_provider_for_day(day_name, iscleaning)
            provider_type = "hygienist" if iscleaning else "doctor"
            
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
                continue
            
            # Handle days with no scheduled provider
            if not provider_ids:
                availability_data[date_str] = {
                    "date": date_str,
                    "day": day_name,
                    "status": f"No {provider_type} scheduled",
                    "free_slots": 0,
                    "booked_slots": 0,
                    "total_slots": 0,
                    "available_times": []
                }
                continue
            
            # Generate all possible slots for this day based on provider type
            slot_duration = 60  # Default to 60 minutes for all appointments
            if iscleaning and provider_ids:
                # For hygienists, generate slots based on their individual schedules
                all_slots = []
                for provider_id in provider_ids:
                    hygienist_slots = generate_hygienist_time_slots(day_name, provider_id)
                    all_slots.extend(hygienist_slots)
                # Remove duplicates and sort
                all_slots = sorted(list(set(all_slots)), key=lambda x: parse_time_to_minutes(x))
            else:
                # For doctors, use the clinic's general schedule with standard lunch break (1-hour slots)
                open_time = day_schedule.get("open", "9:00 AM")
                close_time = day_schedule.get("close", "5:00 PM")
                lunch_start = "1:00 PM"  # Standard lunch break
                lunch_end = "2:00 PM"
                all_slots = generate_time_slots(open_time, close_time, 60, lunch_start, lunch_end)  # 60-minute slots for doctors
            
            if not all_slots:
                availability_data[date_str] = {
                    "date": date_str,
                    "day": day_name,
                    "status": f"No slots available for {provider_type}",
                    "free_slots": 0,
                    "booked_slots": 0,
                    "total_slots": 0,
                    "available_times": []
                }
                continue
            
            # Filter appointments by provider for this day
            date_str_for_comparison = current_date.strftime("%Y-%m-%d")
            
            # Filter all appointments to only include relevant providers
            day_appointments = filter_appointments_by_provider(all_appointments, provider_ids)
            # Get all time slots that are blocked by appointments
            blocked_slots = set()
            appointments_found_for_day = 0
            
            for apt in day_appointments:
                # Skip cancelled appointments
                if apt.get("cancelled", False):
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
                            apt_provider_id = apt.get("provider_id", "N/A")
                            
                            # Calculate which slots this appointment blocks
                            # Use the correct slot duration (60 minutes for all appointments)
                            slots_blocked_by_this_apt = []
                            for slot_time_str in all_slots:
                                # Convert slot string to datetime for overlap checking
                                slot_datetime = datetime.strptime(f"{date_str_for_comparison} {slot_time_str}", "%Y-%m-%d %I:%M %p")
                                slot_end_datetime = slot_datetime + timedelta(minutes=slot_duration)
                                
                                # Check if this slot overlaps with the appointment
                                # Overlap occurs if: slot_start < apt_end AND slot_end > apt_start
                                if slot_datetime < apt_end and slot_end_datetime > apt_start:
                                    blocked_slots.add(slot_time_str)
                                    slots_blocked_by_this_apt.append(slot_time_str)
                            
                    except Exception as e:
                        pass
            
            # print(f"   📊 Found {appointments_found_for_day} {provider_type} appointments for {date_str_for_comparison}")
            # print(f"   🚫 Blocked slots: {sorted(blocked_slots)}")
            
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
            
        #     print(f"   📅 {date_str} ({day_name}): {free_slots_count} free, {booked_slots_count} booked out of {total_slots} total")
        
        # print(f"   ✅ Found {total_free_slots} total free slots across 3 days")
        
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
        #print(f"   ❌ Invalid date format: {date}")
        return {
            "success": False,
            "error": "Invalid date format. Please use YYYY-MM-DD format.",
            "requested_date": date,
            "availability": {}
        }
    except Exception as e:
        #print(f"   ❌ Error getting schedule for date: {e}")
        return {
            "success": False,
            "error": str(e),
            "requested_date": date,
            "availability": {}
        }

# async def debug_appointments(date: str, iscleaning: bool = False):
#     """
#     Debug endpoint to show raw appointment data from Kolla API
#     Filters by provider based on iscleaning flag
#     """
#     try:
#         start_date = datetime.strptime(date, "%Y-%m-%d")
#         end_date = start_date + timedelta(days=2)
        
#         # Get all appointments
#         all_appointments = get_booked_appointments(start_date, end_date)
        
#         # Filter by provider type for debugging
#         provider_type = "hygienist" if iscleaning else "doctor"
        
#         # Show provider filtering for each day
#         filtered_by_day = {}
#         for i in range(3):
#             current_date = start_date + timedelta(days=i)
#             day_name = current_date.strftime("%A")
#             provider_ids = get_provider_for_day(day_name, iscleaning)
#             day_appointments = filter_appointments_by_provider(all_appointments, provider_ids)
#             filtered_by_day[day_name] = {
#                 "provider_ids": provider_ids,
#                 "appointments": len(day_appointments)
#             }
       
  
        
#         return {
#             "success": True,
#             "date_range": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
#             "provider_type": provider_type,
#             "provider_filtering": filtered_by_day,
#             "total_appointments": len(all_appointments),
#             "appointments": all_appointments
#         }
        
#     except Exception as e:
#         print(f"Debug error: {e}")
#         return {"success": False, "error": str(e)}

# @router.get("/debug/hygienist-schedule/{day}")
# async def debug_hygienist_schedule(day: str):
#     """Debug endpoint to check hygienist schedule for a specific day"""
#     try:
#         schedule = load_schedule()
#         day_schedule = schedule.get(day, {})
#         hygienists = day_schedule.get("hygienists", [])
        
#         result = {
#             "day": day,
#             "clinic_open": day_schedule.get("open"),
#             "clinic_close": day_schedule.get("close"),
#             "doctor": day_schedule.get("doctor"),
#             "hygienists_count": len(hygienists),
#             "hygienists": []
#         }
        
#         for hygienist in hygienists:
#             name = hygienist.get("name")
#             provider_id = hygienist.get("provider_id")
#             slots = generate_hygienist_time_slots(day, provider_id)
            
#             result["hygienists"].append({
#                 "name": name,
#                 "provider_id": provider_id,
#                 "open": hygienist.get("open"),
#                 "close": hygienist.get("close"),
#                 "lunch_start": hygienist.get("lunch_start"),
#                 "lunch_end": hygienist.get("lunch_end"),
#                 "slot_duration": hygienist.get("slot_duration"),
#                 "available_slots": slots,
#                 "total_slots": len(slots)
#             })
        
#         return result
#     except Exception as e:
#         return {"error": str(e)}
