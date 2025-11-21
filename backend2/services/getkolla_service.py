"""
GetKolla PMS integration service for syncing patient data and appointments
"""

import json
import logging
import requests
import os
from typing import Dict, Any, List, Optional
from services.service_status_sheet import update_kolla_integration, update_fastapi_backend
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class GetKollaService:
    def __init__(self):
        # Kolla API configuration from environment variables
        self.base_url = os.getenv("KOLLA_BASE_URL", "https://unify.kolla.dev/dental/v1")
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {os.getenv('KOLLA_BEARER_TOKEN')}",
            "connector-id": os.getenv("KOLLA_CONNECTOR_ID", "eaglesoft"),
            "consumer-id": os.getenv("KOLLA_CONSUMER_ID", "dajc")
        }
          # Load schedule configuration
        self.schedule_file = Path(__file__).parent.parent.parent / "schedule.json"
        self.schedule = self._load_schedule()
    
    def _load_schedule(self) -> Dict[str, Any]:
        """Load schedule from schedule.json file"""
        try:
            with open(self.schedule_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading schedule: {e}")
            return {}
    
    def _parse_time(self, time_str: str) -> datetime:
        """Parse time string to datetime object"""
        try:
            return datetime.strptime(time_str, "%I:%M %p")
        except ValueError:
            try:
                return datetime.strptime(time_str, "%H:%M")
            except ValueError:
                logger.error(f"Cannot parse time: {time_str}")
                return datetime.strptime("09:00", "%H:%M")
    
    def _get_day_name(self, date_obj: datetime) -> str:
        """Get day name from datetime object"""
        return date_obj.strftime("%A")
    
    def _get_service_duration(self, service_type: str) -> int:
        """Get duration for a specific service type"""
        service_durations = self.schedule.get("service_durations", {})
        service_key = service_type.lower().strip()
        
        # Try exact match first
        if service_key in service_durations:
            return service_durations[service_key]
        
        # Try partial matches for common variations
        for service, duration in service_durations.items():
            if service in service_key or service_key in service:
                return duration
        
        # Default duration if no match found
        return 30
    
    def _generate_time_slots(self, start_time: str, end_time: str, slot_duration: int, lunch_break: Dict = None) -> List[str]:
        """Generate available time slots for a day with specified slot duration"""
        slots = []
        
        start_dt = self._parse_time(start_time)
        end_dt = self._parse_time(end_time)
        
        current_time = start_dt
        slot_timedelta = timedelta(minutes=slot_duration)
        
        while current_time + slot_timedelta <= end_dt:
            # Check if slot conflicts with lunch break
            if lunch_break:
                lunch_start = self._parse_time(lunch_break["start"])
                lunch_end = self._parse_time(lunch_break["end"])
                
                slot_end = current_time + slot_timedelta
                
                # Skip if slot overlaps with lunch break
                if not (slot_end <= lunch_start or current_time >= lunch_end):
                    current_time += timedelta(minutes=slot_duration)
                    continue
            
            # Format time in 12-hour format
            slot_time = current_time.strftime("%I:%M %p").lstrip('0')
            slots.append(slot_time)
            
            current_time += timedelta(minutes=slot_duration)
        
        return slots
    
    def _convert_24h_to_12h(self, time_24h: str) -> str:
        """Convert 24-hour format (HH:MM) to 12-hour format (H:MM AM/PM)"""
        try:
            dt = datetime.strptime(time_24h, "%H:%M")
            return dt.strftime("%I:%M %p").lstrip('0')
        except ValueError:
            logger.error(f"Cannot convert time format: {time_24h}")
            return time_24h
    
    def _generate_time_slots_24h(self, start_time: str, end_time: str, slot_duration: int = 30) -> List[str]:
        """Generate available time slots in 24-hour format"""
        slots = []
        
        try:
            start_dt = datetime.strptime(start_time, "%H:%M")
            end_dt = datetime.strptime(end_time, "%H:%M")
            
            current_time = start_dt
            slot_timedelta = timedelta(minutes=slot_duration)
            
            while current_time + slot_timedelta <= end_dt:
                # Format time in 24-hour format
                slot_time = current_time.strftime("%H:%M")
                slots.append(slot_time)
                current_time += slot_timedelta
                
        except ValueError as e:
            logger.error(f"Error generating 24h time slots: {e}")
            
        return slots

    def get_available_slots_for_service(self, target_date: datetime, service_type: str) -> List[str]:
        """Get available appointment slots for a specific date and service type"""
        try:
            day_name = self._get_day_name(target_date)
            
            # Check if clinic is open on this day
            day_schedule = self.schedule.get(day_name, {})
            if day_schedule.get("status") == "Closed":
                return []
            
            open_time = day_schedule.get("open")
            close_time = day_schedule.get("close")
            lunch_break = day_schedule.get("lunch_break")
            
            if not open_time or not close_time:
                return []
            
            # Get duration for this specific service
            service_duration = self._get_service_duration(service_type)
            
            # Generate all possible slots for the day with service-specific duration
            all_slots = self._generate_time_slots(open_time, close_time, service_duration, lunch_break)
            
            # Get booked appointments for this date
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            booked_appointments = self.get_booked_appointments(start_of_day, end_of_day)
            
            # Extract booked time slots - need to check for overlaps, not just exact matches
            available_slots = []
            
            for slot_time_str in all_slots:
                slot_start = self._parse_time(slot_time_str)
                slot_start = target_date.replace(hour=slot_start.hour, minute=slot_start.minute, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=service_duration)
                  # Check if this slot conflicts with any booked appointment
                slot_available = True
                
                for appointment in booked_appointments:
                    if appointment.get("cancelled") or appointment.get("broken"):
                        continue
                    
                    apt_start = self._parse_appointment_time(appointment, "wall_start_time")
                    apt_end = self._parse_appointment_time(appointment, "wall_end_time")
                    
                    if apt_start and apt_start.date() == target_date.date():
                        # If we don't have end time, calculate it
                        if not apt_end:
                            apt_end = apt_start + timedelta(minutes=30)  # Default duration
                        
                        # Check for overlap
                        if not (slot_end <= apt_start or slot_start >= apt_end):
                            slot_available = False
                            break
                
                if slot_available:
                    available_slots.append(slot_time_str)
            
            logger.info(f"Available slots for {service_type} on {target_date.strftime('%Y-%m-%d')}: {len(available_slots)}")
            return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots for {service_type} on {target_date}: {e}")
            return []
    def get_booked_appointments(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Fetch booked appointments from Kolla API for the given date range.

        Updates the Service Status sheet for Kolla Integration and Backend.
        """
        try:
            url = f"{self.base_url}/appointments"

            params = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }

            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                data = response.json()
                appointments = data.get("appointments", [])
                logger.info(f"Fetched {len(appointments)} booked appointments from Kolla API")
                update_kolla_integration(True, "Fetched appointments successfully")
                update_fastapi_backend(True, "Kolla appointments fetch OK")
                return appointments
            else:
                logger.error(f"Error fetching appointments: {response.status_code} - {response.text}")
                update_kolla_integration(False, f"HTTP {response.status_code} fetching appointments")
                update_fastapi_backend(False, "Kolla appointments fetch error")
                return []

        except Exception as e:
            logger.error(f"Error fetching booked appointments: {e}")
            update_kolla_integration(False, f"Exception: {e.__class__.__name__}")
            update_fastapi_backend(False, "Kolla appointments fetch exception")
            return []
    def _parse_appointment_time(self, appointment: Dict[str, Any], field_name: str = "wall_start_time") -> Optional[datetime]:
        """Parse appointment time from Kolla API response"""
        try:
            # Use specified field or fall back to wall_start_time
            time_str = appointment.get(field_name) 
            if not time_str:
                return None
            
            # Parse different time formats
            if "T" in time_str and "Z" in time_str:
                # ISO format with Z (UTC)
                return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            elif "T" in time_str:
                # ISO format
                return datetime.fromisoformat(time_str)
            else:
                # Try parsing as datetime string
                return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                
        except Exception as e:
            logger.error(f"Error parsing appointment time {time_str}: {e}")
            return None
    
    def get_available_slots_for_date(self, target_date: datetime) -> List[str]:
        """Get available appointment slots for a specific date"""
        try:
            day_name = self._get_day_name(target_date)
              # Check if clinic is open on this day
            day_schedule = self.schedule.get(day_name, {})
            if day_schedule.get("status") == "Closed":
                return []
            
            open_time = day_schedule.get("open")
            close_time = day_schedule.get("close")
            duration = day_schedule.get("default_slot_duration", 30)
            lunch_break = day_schedule.get("lunch_break")
            
            if not open_time or not close_time:
                return []
            
            # Generate all possible slots for the day
            all_slots = self._generate_time_slots(open_time, close_time, duration, lunch_break)
            
            # Get booked appointments for this date
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            booked_appointments = self.get_booked_appointments(start_of_day, end_of_day)
              # Extract booked time slots - handle appointments that span multiple slots
            available_slots = []
            
            for slot_time_str in all_slots:
                slot_start = self._parse_time(slot_time_str)
                slot_start = target_date.replace(hour=slot_start.hour, minute=slot_start.minute, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=duration)
                
                # Check if this slot conflicts with any booked appointment
                slot_available = True
                
                for appointment in booked_appointments:
                    if appointment.get("cancelled") or appointment.get("broken"):
                        continue  # Skip cancelled or broken appointments
                    
                    apt_start = self._parse_appointment_time(appointment, "wall_start_time")
                    apt_end = self._parse_appointment_time(appointment, "wall_end_time")
                    
                    if apt_start and apt_start.date() == target_date.date():
                        # If we don't have end time, assume 30 minutes default
                        if not apt_end:
                            apt_end = apt_start + timedelta(minutes=30)
                        
                        # Check for overlap: appointment and slot overlap if they don't end before each other starts
                        if not (slot_end <= apt_start or slot_start >= apt_end):
                            slot_available = False
                            logger.debug(f"Slot {slot_time_str} conflicts with appointment {apt_start.strftime('%H:%M')}-{apt_end.strftime('%H:%M')}")
                            break
                
                if slot_available:
                    available_slots.append(slot_time_str)
            
            logger.info(f"Available slots for {target_date.strftime('%Y-%m-%d')}: {len(available_slots)}")
            return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots for {target_date}: {e}")
            return []
    
    def get_available_slots_next_7_days(self) -> Dict[str, List[str]]:
        """Get available appointment slots for the next 7 days"""
        try:
            available_slots = {}
            today = datetime.now()
            
            for i in range(7):
                target_date = today + timedelta(days=i)
                date_str = target_date.strftime("%Y-%m-%d")
                day_name = self._get_day_name(target_date)
                
                slots = self.get_available_slots_for_date(target_date)
                
                if slots:  # Only include days with available slots
                    available_slots[f"{day_name} ({date_str})"] = slots
            
            logger.info(f"Generated available slots for next 7 days: {len(available_slots)} days with slots")
            return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots for next 7 days: {e}")
            return {}
    
    def book_appointment(self, appointment_data: Dict[str, Any]) -> bool:
        """Book an appointment through Kolla API"""
        try:
            url = f"{self.base_url}/appointments"
            
            # Transform appointment data to Kolla API format
            payload = {
                "contact": {
                    "given_name": appointment_data.get("name", "").split()[0],
                    "family_name": " ".join(appointment_data.get("name", "").split()[1:]),
                    "phone": appointment_data.get("contact", ""),
                    "email": appointment_data.get("email", "")
                },
                "start_time": appointment_data.get("start_time"),
                "end_time": appointment_data.get("end_time"),
                "appointment_type_id": "appointmenttypes/1",  # Default appointment type
                "short_description": appointment_data.get("service_booked", "General Appointment"),
                "notes": f"Booked via AI Assistant. New patient: {appointment_data.get('is_new_patient', False)}",
                "operatory": "resources/operatory_1",  # Default operatory
                "providers": [
                    {
                        "name": "resources/provider_1",
                        "remote_id": "provider_1",
                        "type": "provider"
                    }
                ]
            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Successfully booked appointment: {result}")
                return True
            else:
                logger.error(f"Error booking appointment: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if Kolla API is accessible"""
        try:
            # Try to fetch appointments to test connectivity
            response = requests.get(f"{self.base_url}/appointments", headers=self.headers)
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Kolla API health check failed: {e}")
            return False
        
    def get_availability_with_schedule_data(self, requested_date: str, days_to_check: int = 3) -> Dict[str, Any]:
        """
        Get availability using the new schedule data format that matches your JSON structure
        This method properly handles appointments that span multiple 30-minute slots
        """
        try:
            start_date = datetime.strptime(requested_date, "%Y-%m-%d")
            
            result = {
                "success": True,
                "requested_date": requested_date,
                "dates_covered": [],
                "availability": {},
                "total_days": days_to_check,
                "generated_at": datetime.now().isoformat()
            }
            
            for i in range(days_to_check):
                current_date = start_date + timedelta(days=i)
                date_str = current_date.strftime("%Y-%m-%d")
                day_name = current_date.strftime("%A")
                
                result["dates_covered"].append(date_str)
                
                # Get day schedule
                day_schedule = self.schedule.get(day_name, {})
                
                if day_schedule.get("status") == "Closed":
                    result["availability"][date_str] = {
                        "date": date_str,
                        "day_name": day_name,
                        "doctor": None,
                        "clinic_hours": None,
                        "total_slots": 0,
                        "booked_slots": 0,
                        "free_slots": 0,
                        "available_times": [],
                        "status": "closed"
                    }
                    continue
                  # Get clinic hours and doctor info
                open_time = day_schedule.get("open", "09:00")
                close_time = day_schedule.get("close", "17:00")
                doctor_name = day_schedule.get("doctor", "Dr. Parmar")
                
                # Convert 12-hour format to 24-hour format if needed
                if "AM" in open_time or "PM" in open_time:
                    open_time_24h = datetime.strptime(open_time, "%I:%M %p").strftime("%H:%M")
                else:
                    open_time_24h = open_time
                    
                if "AM" in close_time or "PM" in close_time:
                    close_time_24h = datetime.strptime(close_time, "%I:%M %p").strftime("%H:%M") 
                else:
                    close_time_24h = close_time
                  # Generate all possible 30-minute slots
                all_slots_24h = self._generate_time_slots_24h(open_time_24h, close_time_24h, 30)
                total_slots = len(all_slots_24h)
                
                # Get booked appointments for this date
                start_of_day = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = start_of_day + timedelta(days=1)
                booked_appointments = self.get_booked_appointments(start_of_day, end_of_day)
                
                # Find available slots by checking for conflicts
                available_slots_24h = []
                booked_slot_count = 0
                
                for slot_time in all_slots_24h:
                    slot_start = datetime.strptime(f"{date_str} {slot_time}", "%Y-%m-%d %H:%M")
                    slot_end = slot_start + timedelta(minutes=30)
                    
                    # Check if this slot conflicts with any appointment
                    slot_available = True
                    
                    for appointment in booked_appointments:
                        if appointment.get("cancelled") or appointment.get("broken"):
                            continue
                        
                        apt_start = self._parse_appointment_time(appointment, "wall_start_time")
                        apt_end = self._parse_appointment_time(appointment, "wall_end_time")
                        
                        if apt_start and apt_start.date() == current_date.date():
                            if not apt_end:
                                apt_end = apt_start + timedelta(minutes=30)
                            
                            # Check for overlap
                            if not (slot_end <= apt_start or slot_start >= apt_end):
                                slot_available = False
                                break
                    
                    if slot_available:
                        available_slots_24h.append(slot_time)
                    else:
                        booked_slot_count += 1
                
                # Calculate free slots
                free_slots = len(available_slots_24h)
                
                result["availability"][date_str] = {
                    "date": date_str,
                    "day_name": day_name,
                    "doctor": doctor_name,                    "clinic_hours": {
                        "start": open_time_24h,
                        "end": close_time_24h
                    },
                    "total_slots": total_slots,
                    "booked_slots": booked_slot_count,
                    "free_slots": free_slots,
                    "available_times": available_slots_24h,
                    "status": "open" if free_slots > 0 else "fully_booked"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting availability with schedule data: {e}")
            return {
                "success": False,
                "error": str(e),
                "requested_date": requested_date,
                "generated_at": datetime.now().isoformat()
            }
    
    def _get_available_slots_for_date_with_appointments(self, target_date: datetime, booked_appointments: List[Dict[str, Any]]) -> List[str]:
        """
        Get available appointment slots for a specific date using pre-fetched appointments
        This optimized version avoids making additional API calls
        """
        try:
            day_name = self._get_day_name(target_date)
            
            # Check if clinic is open on this day
            day_schedule = self.schedule.get(day_name, {})
            if day_schedule.get("status") == "Closed":
                return []
            
            open_time = day_schedule.get("open")
            close_time = day_schedule.get("close")
            duration = day_schedule.get("default_slot_duration", 30)
            lunch_break = day_schedule.get("lunch_break")
            
            if not open_time or not close_time:
                return []
            
            # Generate all possible slots for the day
            all_slots = self._generate_time_slots(open_time, close_time, duration, lunch_break)
            
            # Extract booked time slots from pre-fetched appointments
            available_slots = []
            
            for slot_time_str in all_slots:
                slot_start = self._parse_time(slot_time_str)
                slot_start = target_date.replace(hour=slot_start.hour, minute=slot_start.minute, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=duration)
                  # Check if this slot conflicts with any booked appointment
                is_available = True
                for appointment in booked_appointments:
                    if appointment.get("cancelled") or appointment.get("broken"):
                        continue
                        
                    apt_start = self._parse_appointment_time(appointment, "wall_start_time")
                    apt_end = self._parse_appointment_time(appointment, "wall_end_time")
                    
                    if not apt_start:
                        continue
                    
                    # If no end time, try to calculate from duration or use default
                    if not apt_end:
                        apt_duration = appointment.get("duration_minutes", duration)
                        apt_end = apt_start + timedelta(minutes=apt_duration)
                    
                    # Ensure we're checking appointments on the same date
                    if apt_start.date() != target_date.date():
                        continue
                    
                    # Check for overlap with slot
                    if not (slot_end <= apt_start or slot_start >= apt_end):
                        is_available = False
                        break
                
                if is_available:
                    available_slots.append(slot_time_str)
            
            return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots for {target_date}: {e}")
            return []
