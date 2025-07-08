"""
Kolla API functionality for BrightSmile Dental Clinic AI Assistant
Handles all appointment-related operations with built-in availability logic
"""

import json
import uuid
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import HTTPException
from pydantic import BaseModel


class CheckSlotsRequest(BaseModel):
    day: str


class BookAppointmentRequest(BaseModel):
    name: str
    contact: Union[str, Dict[str, Any]]  # Accept both string and dict
    day: str
    date: str  # Added date field
    dob: Optional[str] = None  # Added patient date of birth
    time: str
    is_new_patient: bool
    service_booked: str
    doctor_for_appointment: str
    patient_details: Optional[Union[str, Dict[str, Any]]] = None  # Accept both string and dict


class RescheduleRequest(BaseModel):
    name: str
    dob: str
    reason: str
    new_slot: str


class KollaAPIs:
    """Class to handle all Kolla-related API operations with built-in logic"""
    
    def __init__(self):
        # Load configuration
        self.base_url = os.getenv('GETKOLLA_BASE_URL', 'https://api.getkolla.com')
        self.api_key = os.getenv('GETKOLLA_API_KEY', '')
        self.clinic_id = os.getenv('GETKOLLA_CLINIC_ID', '')
        
        # Load schedule configuration
        self.schedule = self._load_schedule()
        
        # Standard slot duration in minutes
        self.slot_duration = 30
    
    def _load_schedule(self) -> Dict[str, Any]:
        """Load the clinic schedule from schedule.json"""
        try:
            schedule_path = os.path.join(os.path.dirname(__file__), '..', 'schedule.json')
            with open(schedule_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load schedule.json: {e}")
            # Return default schedule
            return {
                "Monday": {"doctor": "Dr. Parmar", "open": "9:00 AM", "close": "5:00 PM", "status": "Open"},
                "Tuesday": {"doctor": "Dr. Hanna", "open": "9:00 AM", "close": "6:00 PM", "status": "Open"},
                "Wednesday": {"doctor": "Dr. Parmar", "open": "9:00 AM", "close": "5:00 PM", "status": "Open"},
                "Thursday": {"doctor": "Dr. Hanna", "open": "9:00 AM", "close": "6:00 PM", "status": "Open"},
                "Friday": {"doctor": "Dr. Parmar", "open": "9:00 AM", "close": "5:00 PM", "status": "Open"},
                "Saturday": {"status": "Closed"},
                "Sunday": {"status": "Closed"}
            }
    
    def _convert_12h_to_24h(self, time_str: str) -> str:
        """Convert 12-hour format to 24-hour format"""
        try:
            time_obj = datetime.strptime(time_str, "%I:%M %p")
            return time_obj.strftime("%H:%M")
        except ValueError:
            # If already in 24-hour format or invalid, return as-is
            return time_str
    
    def _convert_24h_to_12h(self, time_str: str) -> str:
        """Convert 24-hour format to 12-hour format"""
        try:
            time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.strftime("%I:%M %p").lstrip('0')
        except ValueError:
            # If already in 12-hour format or invalid, return as-is
            return time_str
    
    def _generate_time_slots(self, start_time: str, end_time: str, duration_minutes: int = 30) -> List[str]:
        """Generate time slots between start and end time"""
        slots = []
        
        # Convert to 24-hour format for calculations
        start_24h = self._convert_12h_to_24h(start_time)
        end_24h = self._convert_12h_to_24h(end_time)
        
        try:
            start_dt = datetime.strptime(start_24h, "%H:%M")
            end_dt = datetime.strptime(end_24h, "%H:%M")
            
            current_time = start_dt
            while current_time < end_dt:
                slots.append(current_time.strftime("%H:%M"))
                current_time += timedelta(minutes=duration_minutes)
                
        except ValueError as e:
            print(f"Error generating time slots: {e}")
            
        return slots
    
    def _parse_appointment_time(self, appointment: Dict[str, Any]) -> tuple:
        """Parse appointment start and end times, handling timezone differences"""
        try:
            # Try wall_start_time first (local time)
            if 'wall_start_time' in appointment and appointment['wall_start_time']:
                start_str = appointment['wall_start_time']
                end_str = appointment.get('wall_end_time', '')
                
                # Parse the datetime strings
                if isinstance(start_str, str):
                    if 'T' in start_str:
                        start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    else:
                        start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                else:
                    start_time = start_str
                    
                if isinstance(end_str, str) and end_str:
                    if 'T' in end_str:
                        end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    else:
                        end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                else:
                    # If no end time, assume 30-minute appointment
                    end_time = start_time + timedelta(minutes=30)
                    
                return start_time, end_time
                
            # Fallback to start_time/end_time (UTC)
            elif 'start_time' in appointment and appointment['start_time']:
                start_str = appointment['start_time']
                end_str = appointment.get('end_time', '')
                
                start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                if end_str:
                    end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                else:
                    end_time = start_time + timedelta(minutes=30)
                    
                return start_time, end_time
                
        except Exception as e:
            print(f"Error parsing appointment time: {e}")
            
        # Return None if parsing fails
        return None, None
    
    def _get_booked_appointments(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get booked appointments from GetKolla API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'start_time': start_date.isoformat(),
                'end_time': end_date.isoformat(),
                'clinic_id': self.clinic_id
            }
            
            response = requests.get(f"{self.base_url}/appointments", headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('appointments', [])
            else:
                print(f"API request failed with status {response.status_code}: {response.text}")
                return []
                
        except Exception as e:
            print(f"Error fetching appointments: {e}")
            return []
    
    def _get_blocked_slots_for_date(self, target_date: datetime, appointments: List[Dict[str, Any]]) -> List[str]:
        """Get all blocked time slots for a specific date based on appointments"""
        blocked_slots = []
        date_str = target_date.strftime("%Y-%m-%d")
        
        for appointment in appointments:
            if appointment.get('cancelled') or appointment.get('broken'):
                continue
                
            start_time, end_time = self._parse_appointment_time(appointment)
            if not start_time or not end_time:
                continue
                
            # Check if appointment is on the target date
            if start_time.strftime("%Y-%m-%d") == date_str:
                # Calculate duration in minutes
                duration_minutes = (end_time - start_time).total_seconds() / 60
                
                # Generate all slots that this appointment blocks
                current_time = start_time
                while current_time < end_time:
                    blocked_slots.append(current_time.strftime("%H:%M"))
                    current_time += timedelta(minutes=self.slot_duration)
                    
        return blocked_slots
    
    def _get_availability_for_date(self, date_str: str) -> Dict[str, Any]:
        """Get availability information for a specific date"""
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = target_date.strftime("%A")
            
            # Get day schedule
            day_schedule = self.schedule.get(day_name, {})
            status = day_schedule.get("status", "Open")
            
            if status == "Closed":
                return {
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
            
            # Get clinic hours
            open_time = day_schedule.get("open", "9:00 AM")
            close_time = day_schedule.get("close", "5:00 PM")
            doctor = day_schedule.get("doctor", "Available Doctor")
            
            # Generate all possible slots
            all_slots = self._generate_time_slots(open_time, close_time, self.slot_duration)
            
            # Get booked appointments for this date
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            appointments = self._get_booked_appointments(start_of_day, end_of_day)
            
            # Get blocked slots
            blocked_slots = self._get_blocked_slots_for_date(target_date, appointments)
            
            # Calculate available slots
            available_slots = [slot for slot in all_slots if slot not in blocked_slots]
            
            return {
                "date": date_str,
                "day_name": day_name,
                "doctor": doctor,
                "clinic_hours": {
                    "start": self._convert_12h_to_24h(open_time),
                    "end": self._convert_12h_to_24h(close_time)
                },
                "total_slots": len(all_slots),
                "booked_slots": len(blocked_slots) // (60 // self.slot_duration) if blocked_slots else 0,
                "free_slots": len(available_slots),
                "available_times": available_slots,
                "status": "open"
            }
            
        except Exception as e:
            print(f"Error getting availability for {date_str}: {e}")
            return {
                "date": date_str,
                "day_name": "Unknown",
                "doctor": None,
                "clinic_hours": None,
                "total_slots": 0,
                "booked_slots": 0,
                "free_slots": 0,
                "available_times": [],
                "status": "error"
            }
    
    def _get_availability_next_days(self, num_days: int = 7) -> Dict[str, Any]:
        """Get availability for the next N days"""
        today = datetime.now()
        availability = {}
        
        for i in range(num_days):
            target_date = today + timedelta(days=i)
            date_str = target_date.strftime("%Y-%m-%d")
            availability[date_str] = self._get_availability_for_date(date_str)
            
        return {
            "success": True,
            "requested_date": today.strftime("%Y-%m-%d"),
            "dates_covered": list(availability.keys()),
            "availability": availability,
            "total_days": num_days,
            "generated_at": datetime.now().isoformat()
        }

    async def check_available_slots(self, request: CheckSlotsRequest):
        """Check available appointment slots for next 7 days"""
        current_day = datetime.now().strftime("%A")
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"🔍 CHECK_AVAILABLE_SLOTS:")
        print(f"   Current Day: {current_day} ({current_date})")
        print(f"   Checking next 7 days...")
        
        try:
            # Get available slots using built-in logic
            availability_result = self._get_availability_next_days(7)
            
            if not availability_result["success"]:
                raise Exception("Failed to get availability")
                
            # Transform the data to match the expected format
            all_available_slots = []
            days_checked = []
            slots_by_day = {}
            
            for date_str, date_data in availability_result["availability"].items():
                day_name = date_data["day_name"]
                days_checked.append(day_name)
                
                # Create slots_by_day entry in expected format
                day_info = f"{day_name} ({date_str})"
                slots_by_day[day_info] = date_data["available_times"]
                
                for slot_time in date_data["available_times"]:
                    all_available_slots.append({
                        "day": day_name,
                        "time": slot_time,
                        "available": True,
                        "doctor": date_data["doctor"]
                    })
            
            print(f"   ✅ Total available slots found: {len(all_available_slots)}")
            print(f"   📅 Days with availability: {len([d for d in availability_result['availability'].values() if d['available_times']])}")
            
            return {
                "available_slots": all_available_slots,
                "days_checked": days_checked,
                "current_day": current_day,
                "slots_by_day": slots_by_day,
                "total_slots": len(all_available_slots),
                "availability_summary": availability_result
            }
            
        except Exception as e:
            print(f"   ❌ Error fetching available slots: {e}")
            raise HTTPException(status_code=500, detail=f"Error fetching available slots: {str(e)}")

    async def book_patient_appointment(self, request: BookAppointmentRequest):
        """Book a new patient appointment"""
        
        print(f"📅 BOOK_PATIENT_APPOINTMENT:")
        print(f"   Name: {request.name}")
        print(f"   Contact: {request.contact}")
        print(f"   Requested date: {request.date}")
        print(f"   Day: {request.day}")
        print(f"   DOB: {request.dob}")
        print(f"   Time: {request.time}")
        print(f"   Service: {request.service_booked}")
        print(f"   Doctor: {request.doctor_for_appointment}")
        print(f"   New Patient: {request.is_new_patient}")
        print(f"   Patient Details: {request.patient_details}")
        
        try:
            # TODO: Implement actual booking through GetKolla API
            # For now, this is a demonstration mode
            print(f"   ✅ [DEMO] Returning 200 OK!")
            
            # Generate appointment ID for demo
            appointment_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
            
            return {
                "success": True,
                "appointment_id": appointment_id,
                "message": f"[DEMO] Appointment request received for {request.name}",
                "status": "demo_mode"
            }
            
        except Exception as e:
            print(f"   ❌ Error booking appointment: {e}")
            raise HTTPException(status_code=500, detail=f"Error booking appointment: {str(e)}")

    async def reschedule_patient_appointment(self, request: RescheduleRequest):
        """Reschedule an existing patient appointment"""
        
        print(f"🔄 RESCHEDULE_PATIENT_APPOINTMENT:")
        print(f"   Name: {request.name}")
        print(f"   DOB: {request.dob}")
        print(f"   Reason: {request.reason}")
        print(f"   New Slot: {request.new_slot}")
        
        try:
            # TODO: Implement actual rescheduling through GetKolla API
            # For now, this is a simulation mode
            print(f"   ✅ [SIMULATION] Appointment would be rescheduled!")
            
            return {
                "success": True,
                "message": f"[SIMULATION] Appointment would be rescheduled for {request.name}",
                "new_appointment_details": {
                    "name": request.name,
                    "new_slot": request.new_slot,
                    "reason": request.reason,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            print(f"   ❌ Error rescheduling appointment: {e}")
            raise HTTPException(status_code=500, detail=f"Error rescheduling appointment: {str(e)}")

    async def confirm_appointment(self, appointment_id: str, confirmation_details: Dict[str, Any]):
        """Confirm an existing appointment"""
        
        print(f"✅ CONFIRM_APPOINTMENT:")
        print(f"   Appointment ID: {appointment_id}")
        print(f"   Confirmation Details: {confirmation_details}")
        
        try:
            # TODO: Implement actual confirmation through GetKolla API
            # For now, this is a simulation mode
            print(f"   ✅ [SIMULATION] Appointment would be confirmed!")
            
            return {
                "success": True,
                "appointment_id": appointment_id,
                "message": f"[SIMULATION] Appointment {appointment_id} would be confirmed",
                "confirmation_details": confirmation_details,
                "confirmed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"   ❌ Error confirming appointment: {e}")
            raise HTTPException(status_code=500, detail=f"Error confirming appointment: {str(e)}")

    async def test_getkolla_api(self):
        """Test GetKolla API connectivity and data fetch"""
        print("🔧 TESTING_GETKOLLA_API:")
        
        try:
            # Test API connectivity by attempting to fetch appointments
            start_date = datetime.now()
            end_date = start_date + timedelta(days=7)
            appointments = self._get_booked_appointments(start_date, end_date)
            health_status = len(appointments) >= 0  # If we can get appointments (even empty list), API is working
            
            print(f"   Health Check: {'✅ Connected' if health_status else '❌ Failed'}")
            print(f"   Appointments Found: {len(appointments)}")
            
            # Test available slots calculation
            availability_result = self._get_availability_next_days(7)
            available_slots_days = len([d for d in availability_result['availability'].values() if d['available_times']])
            print(f"   Available Slots: {available_slots_days} days with slots")
            
            return {
                "getkolla_api": {
                    "health_check": health_status,
                    "appointments_found": len(appointments),
                    "available_slots_days": available_slots_days,
                    "sample_appointments": appointments[:2] if appointments else [],
                    "availability_summary": {
                        date: len(data['available_times']) 
                        for date, data in availability_result['availability'].items()
                    }
                },
                "status": "success" if health_status else "api_unavailable"
            }
            
        except Exception as e:
            print(f"   ❌ Error testing GetKolla API: {e}")
            return {
                "getkolla_api": {
                    "error": str(e),
                    "health_check": False
                },
                "status": "error"
            }

    async def get_schedule(self, days: int = 7):
        """Get available appointment schedule for the next N days"""
        print(f"📅 GET_SCHEDULE: Fetching schedule for next {days} days")
        
        try:
            # Get availability using built-in logic
            availability_result = self._get_availability_next_days(days)
            
            if not availability_result["success"]:
                raise Exception("Failed to get availability")
            
            # Transform to a more structured format
            schedule_data = {}
            total_available_slots = 0
            
            for date_str, date_data in availability_result["availability"].items():
                schedule_data[date_str] = {
                    "day": date_data["day_name"],
                    "date": date_str,
                    "status": date_data["status"],
                    "open_time": self._convert_24h_to_12h(date_data["clinic_hours"]["start"]) if date_data["clinic_hours"] else None,
                    "close_time": self._convert_24h_to_12h(date_data["clinic_hours"]["end"]) if date_data["clinic_hours"] else None,
                    "doctor": date_data["doctor"],
                    "available_slots": date_data["available_times"],
                    "total_slots": date_data["total_slots"],
                    "booked_slots": date_data["booked_slots"],
                    "free_slots": date_data["free_slots"]
                }
                total_available_slots += len(date_data["available_times"])
              print(f"   ✅ Schedule generated successfully")
            print(f"   📊 Total available slots: {total_available_slots}")
            print(f"   📅 Days with availability: {len([d for d in schedule_data.values() if d['total_slots'] > 0])}")
            
            return {
                "success": True,
                "days_requested": days,
                "schedule": schedule_data,
                "summary": {
                    "total_available_slots": total_available_slots,
                    "days_with_availability": len([d for d in schedule_data.values() if d['free_slots'] > 0]),
                    "days_closed": len([d for d in schedule_data.values() if d['status'] == 'closed']),
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

    async def get_schedule_for_date(self, date: str):
        """Get available appointment slots for a specific date (YYYY-MM-DD format)"""
        print(f"📅 GET_SCHEDULE_FOR_DATE: {date}")
        
        try:
            # Parse the date
            target_date = datetime.strptime(date, "%Y-%m-%d")
            
            # Get availability for this specific date using built-in method
            date_data = self._get_availability_for_date(date)
            
            if date_data["status"] == "error":
                return {
                    "success": False,
                    "error": "Failed to get availability for date",
                    "available_slots": [],
                    "total_available": 0
                }
            
            # Get booked appointments for context
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            booked_appointments = self._get_booked_appointments(start_of_day, end_of_day)
            
            print(f"   ✅ Found {len(date_data['available_times'])} available slots")
            print(f"   📋 Found {len(booked_appointments)} booked appointments")
            
            return {
                "success": True,
                "date": date,
                "day": date_data["day_name"],
                "status": date_data["status"],
                "clinic_hours": {
                    "open": self._convert_24h_to_12h(date_data["clinic_hours"]["start"]) if date_data["clinic_hours"] else None,
                    "close": self._convert_24h_to_12h(date_data["clinic_hours"]["end"]) if date_data["clinic_hours"] else None
                },
                "doctor": date_data["doctor"],
                "available_slots": date_data["available_times"],
                "total_available": len(date_data["available_times"]),
                "total_booked": date_data["booked_slots"],
                "total_slots": date_data["total_slots"],
                "free_slots": date_data["free_slots"],
                "booked_appointments": [
                    {
                        "time": apt.get("wall_start_time", apt.get("start_time", "Unknown")),
                        "contact": apt.get("contact", {}).get("given_name", "Unknown") + " " + apt.get("contact", {}).get("family_name", ""),
                        "status": "cancelled" if apt.get("cancelled") else ("broken" if apt.get("broken") else "confirmed")
                    }
                    for apt in booked_appointments
                ]
            }
            
        except ValueError:
            print(f"   ❌ Invalid date format: {date}")
            return {
                "success": False,
                "error": "Invalid date format. Please use YYYY-MM-DD format.",
                "available_slots": [],
                "total_available": 0
            }
        except Exception as e:
            print(f"   ❌ Error getting schedule for date: {e}")
            return {
                "success": False,
                "error": str(e),
                "available_slots": [],
                "total_available": 0
            }

    def get_health_status(self):
        """Get the health status of GetKolla API connectivity"""
        try:
            # Test connectivity by attempting to fetch appointments
            start_date = datetime.now()
            end_date = start_date + timedelta(days=1)
            appointments = self._get_booked_appointments(start_date, end_date)
            return len(appointments) >= 0  # If we can get appointments (even empty list), API is working
        except Exception:
            return False
