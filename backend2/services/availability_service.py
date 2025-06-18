"""
Enhanced Availability Calculation Service using GetKolla unified API format
Implements the availability calculation approach recommended by GetKolla founder
"""

import json
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, time
from pathlib import Path

logger = logging.getLogger(__name__)

class AvailabilityService:
    def __init__(self):
        # Kolla API configuration
        self.base_url = "https://unify.kolla.dev/dental/v1"
        self.headers = {
            "accept": "application/json",
            "authorization": "Bearer kc.hd4iscieh5emlk75rsjuowweya",
            "connector-id": "opendental",
            "consumer-id": "kolla-opendental-sandbox"
        }
        
        # Load local schedule configuration as fallback
        self.schedule_file = Path(__file__).parent.parent.parent / "schedule.json"
        self.local_schedule = self._load_local_schedule()
    
    def _load_local_schedule(self) -> Dict[str, Any]:
        """Load local schedule configuration as fallback"""
        try:
            with open(self.schedule_file, 'r') as f:
                return json.load(f)        
        except Exception as e:
            logger.error(f"Error loading local schedule: {e}")
            return {}
    
    def get_practice_schedule(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Get practice schedule from GetKolla API
        Returns the resource schedule for the practice (practice hours)
        """
        try:
            url = f"{self.base_url}/resources/practice_0:loadSchedule"
            params = {
                "start_date": start_date,
                "end_date": end_date
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching practice schedule: {e}")
            # Fallback to local schedule
            return self._generate_fallback_schedule(start_date, end_date)
    
    def get_appointments(self, start_date: str, end_date: str, 
                        provider_filter: Optional[str] = None,
                        operatory_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get appointments from GetKolla API with optional filtering
        """
        try:
            url = f"{self.base_url}/appointments"
            params = {
                "start_date": start_date,
                "end_date": end_date
            }
            
            # Add filters if provided
            if provider_filter:
                params["provider"] = provider_filter
            if operatory_filter:
                params["operatory"] = operatory_filter
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching appointments: {e}")
            return {"appointments": [], "next_page_token": ""}
    
    def calculate_availability(self, date: str, service_type: str = "consultation", 
                             duration_minutes: int = 30,
                             provider_preference: Optional[str] = None,
                             operatory_preference: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate availability for a specific date based on GetKolla's recommended approach:
        1. Get practice hours (resource schedule)
        2. Get current appointments 
        3. Apply blockouts/notes
        4. Calculate available slots
        """
        try:
            # Step 1: Get practice schedule for the date
            practice_schedule = self.get_practice_schedule(date, date)
            
            # Step 2: Get appointments for the date
            appointments = self.get_appointments(date, date, provider_preference, operatory_preference)
            
            # Step 3: Process the data
            available_slots = self._process_availability(
                practice_schedule, appointments, date, duration_minutes, service_type
            )
            
            return {
                "date": date,
                "service_type": service_type,
                "duration_minutes": duration_minutes,
                "available_slots": available_slots,
                "total_slots": len(available_slots),
                "practice_schedule": practice_schedule,
                "appointment_count": len(appointments.get("appointments", []))
            }
            
        except Exception as e:
            logger.error(f"Error calculating availability: {e}")
            return {
                "date": date,
                "service_type": service_type,
                "available_slots": [],
                "error": str(e)
            }
    
    def _process_availability(self, practice_schedule: Dict, appointments: Dict, 
                            date: str, duration_minutes: int, service_type: str) -> List[Dict[str, Any]]:
        """
        Process practice schedule and appointments to calculate available slots
        """
        available_slots = []
        
        # Extract schedule blocks for the specific date
        schedule_data = practice_schedule.get("schedule", [])
        date_schedule = None
        
        for day_schedule in schedule_data:
            if day_schedule.get("date") == date:
                date_schedule = day_schedule
                break
        
        if not date_schedule:
            logger.warning(f"No practice schedule found for date: {date}")
            return []
        
        # Get practice blocks and notes (blockouts)
        practice_blocks = date_schedule.get("blocks", [])
        practice_notes = date_schedule.get("notes", [])
        
        # Process each practice block
        for block in practice_blocks:
            start_time = block.get("start_time")
            end_time = block.get("end_time")
            
            if start_time and end_time:
                # Generate time slots for this block
                block_slots = self._generate_time_slots_for_block(
                    date, start_time, end_time, duration_minutes
                )
                
                # Filter out booked appointments and blockouts
                filtered_slots = self._filter_booked_slots(
                    block_slots, appointments, practice_notes, date, duration_minutes
                )
                
                available_slots.extend(filtered_slots)
        
        # Sort slots by time
        available_slots.sort(key=lambda x: x["start_time"])
        
        return available_slots
    
    def _generate_time_slots_for_block(self, date: str, start_time: str, 
                                     end_time: str, duration_minutes: int) -> List[Dict[str, Any]]:
        """
        Generate all possible time slots within a practice block
        """
        slots = []
        
        try:
            # Parse start and end times
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
            
            # Generate slots
            current_time = start_dt
            while current_time + timedelta(minutes=duration_minutes) <= end_dt:
                slot_end = current_time + timedelta(minutes=duration_minutes)
                
                slots.append({
                    "start_time": current_time.strftime("%H:%M"),
                    "end_time": slot_end.strftime("%H:%M"),
                    "start_datetime": current_time.isoformat(),
                    "end_datetime": slot_end.isoformat(),
                    "duration_minutes": duration_minutes
                })
                
                current_time += timedelta(minutes=duration_minutes)
        
        except Exception as e:
            logger.error(f"Error generating time slots: {e}")
        
        return slots
    
    def _filter_booked_slots(self, slots: List[Dict], appointments: Dict, 
                           practice_notes: List, date: str, duration_minutes: int) -> List[Dict[str, Any]]:
        """
        Filter out slots that conflict with appointments or blockouts
        """
        available_slots = []
        appointment_list = appointments.get("appointments", [])
        
        for slot in slots:
            slot_start = datetime.fromisoformat(slot["start_datetime"])
            slot_end = datetime.fromisoformat(slot["end_datetime"])
            
            # Check against appointments
            is_available = True
            
            for appointment in appointment_list:
                # Skip cancelled or broken appointments
                if appointment.get("cancelled") or appointment.get("broken"):
                    continue
                
                # Parse appointment times
                apt_start_str = appointment.get("wall_start_time") or appointment.get("start_time")
                apt_end_str = appointment.get("wall_end_time") or appointment.get("end_time")
                
                if apt_start_str and apt_end_str:
                    try:
                        # Handle different time formats
                        apt_start = self._parse_appointment_time(apt_start_str, date)
                        apt_end = self._parse_appointment_time(apt_end_str, date)
                        
                        # Check for time overlap
                        if self._times_overlap(slot_start, slot_end, apt_start, apt_end):
                            is_available = False
                            break
                            
                    except Exception as e:
                        logger.warning(f"Error parsing appointment time: {e}")
            
            # Check against practice notes/blockouts
            if is_available and practice_notes:
                for note in practice_notes:
                    # Process blockout notes - this depends on the specific format
                    # GetKolla founder mentioned blockouts are in the notes property
                    if self._is_blockout_conflict(slot_start, slot_end, note):
                        is_available = False
                        break
            
            # Apply business rules (lunch breaks, etc.)
            if is_available:
                is_available = self._apply_business_rules(slot_start, slot_end, date)
            
            if is_available:
                # Add additional metadata
                slot["available"] = True
                slot["conflicts"] = []
                available_slots.append(slot)
        
        return available_slots
    
    def _parse_appointment_time(self, time_str: str, date: str) -> datetime:
        """Parse appointment time string to datetime object"""
        try:
            # Handle ISO format
            if 'T' in time_str:
                return datetime.fromisoformat(time_str.replace('Z', '+00:00')).replace(tzinfo=None)
            
            # Handle wall time format
            if len(time_str.split()) == 2:
                return datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %Y-%m-%d %H:%M:%S")
            
            # Handle time only
            return datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            logger.error(f"Error parsing appointment time {time_str}: {e}")
            raise
    
    def _times_overlap(self, start1: datetime, end1: datetime, 
                      start2: datetime, end2: datetime) -> bool:
        """Check if two time periods overlap"""
        return start1 < end2 and end1 > start2
    
    def _is_blockout_conflict(self, slot_start: datetime, slot_end: datetime, note: Dict) -> bool:
        """
        Check if slot conflicts with a blockout note
        This depends on how GetKolla structures blockout information in notes
        """
        # This would need to be implemented based on actual GetKolla note format
        # For now, return False as placeholder
        return False
    
    def _apply_business_rules(self, slot_start: datetime, slot_end: datetime, date: str) -> bool:
        """
        Apply business-specific scheduling rules (lunch breaks, etc.)
        """
        try:
            # Get day of week
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            day_name = date_obj.strftime("%A")
            
            # Check local schedule for business rules
            day_schedule = self.local_schedule.get(day_name, {})
            
            # Check lunch break
            lunch_break = day_schedule.get("lunch_break")
            if lunch_break:
                lunch_start = datetime.strptime(f"{date} {lunch_break['start']}", "%Y-%m-%d %I:%M %p")
                lunch_end = datetime.strptime(f"{date} {lunch_break['end']}", "%Y-%m-%d %I:%M %p")
                
                if self._times_overlap(slot_start, slot_end, lunch_start, lunch_end):
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error applying business rules: {e}")
            return True
    
    def _generate_fallback_schedule(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate fallback schedule when API is unavailable"""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            schedule = []
            current_date = start_dt
            
            while current_date <= end_dt:
                day_name = current_date.strftime("%A")
                day_schedule = self.local_schedule.get(day_name, {})
                
                if day_schedule.get("status") != "Closed" and day_schedule.get("open"):
                    schedule.append({
                        "resource": "resources/practice_0",
                        "date": current_date.strftime("%Y-%m-%d"),
                        "blocks": [
                            {
                                "start_time": self._convert_time_format(day_schedule["open"]),
                                "end_time": self._convert_time_format(day_schedule["close"])
                            }
                        ],
                        "notes": []
                    })
                
                current_date += timedelta(days=1)
            
            return {"resource": None, "schedule": schedule}
            
        except Exception as e:
            logger.error(f"Error generating fallback schedule: {e}")
            return {"resource": None, "schedule": []}
    
    def _convert_time_format(self, time_str: str) -> str:
        """Convert 12-hour format to 24-hour format"""
        try:
            time_obj = datetime.strptime(time_str, "%I:%M %p")
            return time_obj.strftime("%H:%M")
        except:
            return time_str

    def get_multi_day_availability(self, start_date: str, end_date: str, 
                                 service_type: str = "consultation",
                                 duration_minutes: int = 30) -> Dict[str, Any]:
        """
        Get availability for multiple days
        """
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            availability_by_date = {}
            current_date = start_dt
            
            while current_date <= end_dt:
                date_str = current_date.strftime("%Y-%m-%d")
                day_availability = self.calculate_availability(
                    date_str, service_type, duration_minutes
                )
                availability_by_date[date_str] = day_availability
                current_date += timedelta(days=1)
            
            return {
                "start_date": start_date,
                "end_date": end_date,
                "service_type": service_type,
                "availability_by_date": availability_by_date,
                "summary": self._generate_availability_summary(availability_by_date)
            }
            
        except Exception as e:
            logger.error(f"Error getting multi-day availability: {e}")
            return {"error": str(e)}
    
    def _generate_availability_summary(self, availability_by_date: Dict) -> Dict[str, Any]:
        """Generate summary statistics for availability"""
        total_slots = 0
        total_days = len(availability_by_date)
        days_with_availability = 0
        
        for date, day_data in availability_by_date.items():
            slot_count = day_data.get("total_slots", 0)
            total_slots += slot_count
            if slot_count > 0:
                days_with_availability += 1
        
        return {
            "total_days": total_days,
            "days_with_availability": days_with_availability,
            "total_available_slots": total_slots,
            "average_slots_per_day": total_slots / total_days if total_days > 0 else 0
        }
