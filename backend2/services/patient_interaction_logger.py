"""
Patient Interaction Logger Service
Handles logging of all patient interactions with the AI assistant
Stores data in JSON format and generates daily reports
"""
import json
import os
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Literal
from pathlib import Path
import threading
import time
import base64

# Import local cache service to fetch appointment details
from .local_cache_service import LocalCacheService

# Optional email imports - make email functionality optional
try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import schedule
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    print("⚠️ Email functionality not available. Reports will only be saved to files.")

InteractionType = Literal["booking", "rescheduling", "confirmation", "callback", "faq", "new_patient_form", "misc"]

class PatientInteractionLogger:
    """Service for logging patient interactions and generating daily reports"""
    
    def __init__(self, log_directory: str = "interaction_logs", config_file: str = "reporting_config.json"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.cache_service = LocalCacheService()  # Initialize cache service
        self.last_report_sent_date = None  # Track last report sent to prevent duplicates
        self._setup_daily_scheduler()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load reporting configuration from file"""
        default_config = {
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "use_tls": True,
                "username": "",
                "password": "",
                "recipients": [],
                "sender_name": "Zenfru AI Assistant"
            },
            "reporting": {
                "daily_email_time": "17:00",  # 5:00 PM
                "timezone": "UTC",
                "include_patient_details": True,
                "include_statistics": True,
                "max_retries": 3
            },
            "fallback": {
                "backup_email": "",
                "log_to_file_only": False
            }
        }
        
    #     if self.config_file.exists():
    #         try:
    #             with open(self.config_file, 'r') as f:
    #                 loaded_config = json.load(f)
    #                 # Merge with default config
    #                 for key in default_config:
    #                     if key in loaded_config:
    #                         default_config[key].update(loaded_config[key])
    #                     else:
    #                         loaded_config[key] = default_config[key]
    #                 return loaded_config
    #         except Exception as e:
    #             print(f"Error loading config file, using defaults: {e}")
        
    #     # Save default config
    #     with open(self.config_file, 'w') as f:
    #         json.dump(default_config, f, indent=2)
        
    #     return default_config
    
    # def _setup_daily_scheduler(self):
    #     """Setup the daily report scheduler with timezone awareness"""
    #     if not EMAIL_AVAILABLE:
    #         print("📅 Daily report scheduler disabled - email functionality not available")
    #         return
            
    #     # Import pytz for timezone handling
    #     import pytz
        
    #     # Get timezone from config, default to Eastern
    #     timezone_str = self.config["reporting"].get("timezone", "US/Eastern")
    #     report_time = self.config["reporting"]["daily_email_time"]
        
    #     # Create a timezone-aware scheduler function
    #     def timezone_aware_scheduler():
    #         tz = pytz.timezone(timezone_str)
    #         now = datetime.now(tz)
    #         target_hour, target_minute = map(int, report_time.split(":"))
    #         today = now.date()
            
    #         # Check if it's the right time (with a 1-minute window) and not already sent today
    #         if (now.hour == target_hour and now.minute == target_minute and 
    #             self.last_report_sent_date != today):
    #             print(f"⏰ Triggering daily report at {now.strftime('%Y-%m-%d %I:%M %p %Z')}")
    #             self._generate_and_send_daily_report()
    #             self.last_report_sent_date = today
        
    #     # Start scheduler in a separate thread that checks every minute
    #     def run_scheduler():
    #         while True:
    #             try:
    #                 timezone_aware_scheduler()
    #             except Exception as e:
    #                 print(f"❌ Error in scheduler: {e}")
    #             time.sleep(60)  # Check every minute
        
    #     scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    #     scheduler_thread.start()
    #     print(f"📅 Daily report scheduler started - reports will be sent at {report_time} {timezone_str}")
    
    def _fetch_appointment_details(self, appointment_id: str) -> Dict[str, Optional[str]]:
        """
        Enhanced method to fetch appointment details from local cache using appointment_id
        Returns patient_name, contact_number, service_type, and doctor
        """
        if not appointment_id:
            return {"patient_name": None, "contact_number": None, "service_type": None, "doctor": None}
        
        try:
            # Clean appointment_id and try different formats
            clean_id = appointment_id.replace("appointments/", "") if appointment_id.startswith("appointments/") else appointment_id
            full_id = f"appointments/{clean_id}"
            
            # Try multiple formats
            appointment_data = None
            for test_id in [full_id, clean_id, appointment_id]:
                appointment_data = self.cache_service.get_appointment_by_id(test_id)
                if appointment_data:
                    break
            
            if appointment_data:
                # Extract patient details from appointment data
                contact = appointment_data.get("contact", {})
                
                # Get patient name from contact data
                patient_name = None
                contact_name = contact.get("name", "")
                given_name = contact.get("given_name", "")
                family_name = contact.get("family_name", "")
                
                if contact_name:
                    patient_name = contact_name
                elif given_name and family_name:
                    patient_name = f"{given_name} {family_name}"
                elif given_name:
                    patient_name = given_name
                elif family_name:
                    patient_name = family_name
                
                # Get contact number 
                contact_number = None
                primary_phone = contact.get("primary_phone_number", "")
                if primary_phone:
                    contact_number = primary_phone
                else:
                    phone_numbers = contact.get("phone_numbers", [])
                    if phone_numbers and len(phone_numbers) > 0:
                        phone_data = phone_numbers[0]
                        if isinstance(phone_data, dict):
                            contact_number = phone_data.get("number", "")
                        else:
                            contact_number = str(phone_data)
                
                # Get service information
                service_type = (appointment_data.get("service") or 
                              appointment_data.get("procedure") or 
                              appointment_data.get("appointment_type") or
                              appointment_data.get("type") or
                              appointment_data.get("service_type") or
                              appointment_data.get("short_description"))
                
                # Get doctor/provider information
                doctor = None
                providers = appointment_data.get("providers", [])
                if providers and len(providers) > 0:
                    provider = providers[0]
                    doctor = provider.get("display_name") or provider.get("name") or provider.get("remote_id")
                
                if not doctor:
                    doctor = (appointment_data.get("doctor") or 
                             appointment_data.get("provider") or
                             appointment_data.get("practitioner") or
                             appointment_data.get("provider_name"))
                
                print(f"📋 Fetched appointment details for {appointment_id}: {patient_name}, {contact_number}, {service_type}")
                return {
                    "patient_name": patient_name,
                    "contact_number": contact_number,
                    "service_type": service_type,
                    "doctor": doctor
                }
            else:
                print(f"⚠️ No appointment details found for ID: {appointment_id}")
                return {"patient_name": None, "contact_number": None, "service_type": None, "doctor": None}
                
        except Exception as e:
            print(f"❌ Error fetching appointment details for {appointment_id}: {e}")
            return {"patient_name": None, "contact_number": None, "service_type": None, "doctor": None}
    
    def log_interaction(
        self,
        interaction_type: InteractionType,
        patient_name: Optional[str] = None,
        contact_number: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        appointment_id: Optional[str] = None,
        service_type: Optional[str] = None,
        doctor: Optional[str] = None,
        error_message: Optional[str] = None,
        reason: Optional[str] = None
    ) -> str:
        """
        Log a patient interaction
        
        Args:
            interaction_type: Type of interaction (booking, rescheduling, etc.)
            patient_name: Patient's name (will be fetched from appointment if not provided)
            contact_number: Patient's contact number (will be fetched from appointment if not provided)
            success: Whether the interaction was successful
            details: Additional details about the interaction
            appointment_id: Associated appointment ID
            service_type: Type of service (will be fetched from appointment if not provided)
            doctor: Doctor name (will be fetched from appointment if not provided)
            error_message: Error message if interaction failed
            reason: Reason for the interaction (e.g., notes from request)
            
        Returns:
            Unique interaction ID
        """
        interaction_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # If patient details are missing but appointment_id is provided, fetch them
        if appointment_id and (not patient_name or not contact_number or not service_type or not doctor):
            appointment_details = self._fetch_appointment_details(appointment_id)
            
            # Use fetched details if not already provided
            patient_name = patient_name or appointment_details["patient_name"]
            contact_number = contact_number or appointment_details["contact_number"]
            service_type = service_type or appointment_details["service_type"]
            doctor = doctor or appointment_details["doctor"]
        
        # Store full contact number in logs (no sanitization)
        # Sanitization can be done later if needed for specific purposes
        
        log_entry = {
            "interaction_id": interaction_id,
            "timestamp": timestamp.isoformat(),
            "date": timestamp.date().isoformat(),
            "time": timestamp.time().isoformat(),
            "interaction_type": interaction_type,
            "patient_name": patient_name,
            "contact_number": contact_number,  # Store full contact number
            "success": success,
            "appointment_id": appointment_id,
            "service_type": service_type,
            "doctor": doctor,
            "error_message": error_message,
            "reason": reason,  # Add reason field
            "details": details or {}
        }
        
        # Save to daily log file
        self._save_to_daily_log(log_entry, timestamp.date())
        
        print(f"📝 Logged {interaction_type} interaction: {interaction_id} - Success: {success}")
        return interaction_id
    
    def _sanitize_contact(self, contact_number: str) -> str:
        """Return full contact number for clinic reports (no sanitization needed)"""
        if not contact_number:
            return "N/A"
        return contact_number
    
    def _save_to_daily_log(self, log_entry: Dict[str, Any], log_date: date):
        """Save log entry to daily log file"""
        log_file = self.log_directory / f"interactions_{log_date.strftime('%Y_%m_%d')}.json"
        
        # Load existing logs or create new list
        logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
                logs = []
        
        logs.append(log_entry)
        
        # Save updated logs
        try:
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
        except Exception as e:
            print(f"Error writing to log file {log_file}: {e}")
    
    def get_daily_interactions(self, target_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get all interactions for a specific date"""
        if target_date is None:
            target_date = date.today()
            
        log_file = self.log_directory / f"interactions_{target_date.strftime('%Y_%m_%d')}.json"
        
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading daily interactions for {target_date}: {e}")
            return []
    
    def generate_daily_report(self, target_date: Optional[date] = None) -> str:
        """Generate HTML daily report"""
        if target_date is None:
            target_date = date.today()
        
        interactions = self.get_daily_interactions(target_date)
        
        # Calculate statistics
        stats = self._calculate_statistics(interactions)
        categorized_interactions = self._categorize_interactions(interactions)
        
        # Generate HTML report
        html_report = self._generate_html_report(target_date, stats, categorized_interactions)
        
        return html_report
    
    def _calculate_statistics(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics from interactions"""
        total_calls = len(interactions)
        successful_calls = sum(1 for i in interactions if i.get('success', False))
        success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
        
        # Count new bookings (successful booking interactions)
        new_bookings = sum(1 for i in interactions 
                          if i.get('interaction_type') == 'booking' and i.get('success', False))
        
        # Count successful reschedulings
        reschedulings = sum(1 for i in interactions 
                          if i.get('interaction_type') == 'rescheduling' and i.get('success', False))
        
        # Count successful confirmations
        confirmations = sum(1 for i in interactions 
                          if i.get('interaction_type') == 'confirmation' and i.get('success', False))
        
        # Calculate minimum estimated revenue (bookings + reschedulings + confirmations) * $110
        min_est_revenue = (new_bookings + reschedulings + confirmations) * 110
        
        # Count by interaction type
        type_counts = {}
        successful_by_type = {}
        
        for interaction in interactions:
            interaction_type = interaction.get('interaction_type', 'misc')
            type_counts[interaction_type] = type_counts.get(interaction_type, 0) + 1
            
            if interaction.get('success', False):
                successful_by_type[interaction_type] = successful_by_type.get(interaction_type, 0) + 1
        
        # Calculate success rates by type
        type_success_rates = {}
        for interaction_type, count in type_counts.items():
            successful = successful_by_type.get(interaction_type, 0)
            type_success_rates[interaction_type] = (successful / count * 100) if count > 0 else 0
        
        # Get peak hours
        hourly_counts = {}
        for interaction in interactions:
            try:
                hour = datetime.fromisoformat(interaction['timestamp']).hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            except:
                continue
        
        peak_hour = max(hourly_counts.items(), key=lambda x: x[1]) if hourly_counts else (0, 0)
        
        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": total_calls - successful_calls,
            "success_rate": round(success_rate, 2),
            "new_bookings": new_bookings,
            "min_est_revenue": min_est_revenue,
            "type_counts": type_counts,
            "type_success_rates": {k: round(v, 2) for k, v in type_success_rates.items()},
            "peak_hour": peak_hour[0] if peak_hour[1] > 0 else None,
            "peak_hour_count": peak_hour[1] if peak_hour[1] > 0 else 0
        }
    
    def _categorize_interactions(self, interactions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize interactions by type"""
        categorized = {
            "booking": [],
            "rescheduling": [],
            "confirmation": [],
            "callback": [],
            "faq": [],
            "new_patient_form": [],
            "misc": []
        }
        
        for interaction in interactions:
            interaction_type = interaction.get('interaction_type', 'misc')
            if interaction_type not in categorized:
                interaction_type = 'misc'
            categorized[interaction_type].append(interaction)
        
        return categorized
    
    def _get_callback_requests(self, report_date: date) -> List[Dict[str, Any]]:
        """Get callback requests for the specified date from the callback requests file"""
        try:
            # Path to callback requests file
            callbacks_file = self.log_directory.parent / "callback_requests.json"
            
            if not callbacks_file.exists():
                return []
            
            with open(callbacks_file, 'r') as f:
                all_callbacks = json.load(f)
            
            # Filter callbacks for the specific date
            date_callbacks = []
            target_date_str = report_date.strftime('%Y-%m-%d')
            
            for callback in all_callbacks:
                callback_date = callback.get('request_timestamp', '')[:10]  # Get YYYY-MM-DD part
                if callback_date == target_date_str:
                    date_callbacks.append(callback)
            
            # Sort by priority (high -> medium -> low) and then by timestamp
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            date_callbacks.sort(key=lambda x: (priority_order.get(x.get('priority', 'low'), 2), x.get('request_timestamp', '')))
            
            return date_callbacks
            
        except Exception as e:
            print(f"Error getting callback requests: {e}")
            return []
    
    def _generate_html_report(self, report_date: date, stats: Dict[str, Any], categorized: Dict[str, List[Dict[str, Any]]]) -> str:
        """Generate professional HTML report"""
        
        # Get callback requests for this date
        callback_requests = self._get_callback_requests(report_date)
        
        # Format date for display
        formatted_date = report_date.strftime("%B %d, %Y")

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Patient Interactions Report {formatted_date}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f7fa;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
            position: relative;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2.5em;
            font-weight: 700;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header p {{
            margin: 0;
            font-size: 1.2em;
            opacity: 0.9;
            color: white;
        }}
        .content {{
            padding: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        /* Mobile responsive - stack stats vertically on smaller screens */
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        /* Tablet responsive - 2 columns on medium screens */
        @media (min-width: 769px) and (max-width: 1024px) {{
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        .stat-card {{
            background: #f8f9fc;
            border-left: 4px solid #667eea;
            padding: 20px;
            border-radius: 8px;
        }}
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin: 0;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            margin: 5px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .interaction-category {{
            margin-bottom: 30px;
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            overflow: hidden;
        }}
        .category-header {{
            background: #667eea;
            color: white;
            padding: 15px 20px;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .category-count {{
            background: white;
            color: #667eea;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.9em;
            font-weight: 600;
            margin-left: auto;
        }}
        .interaction-list {{
            max-height: 400px;
            overflow-y: auto;
        }}
        .interaction-item {{
            padding: 15px 20px;
            border-bottom: 1px solid #f0f0f0;
            display: grid;
            grid-template-columns: 50px 1fr 100px;
            gap: 15px;
            align-items: start;
        }}
        .interaction-item:last-child {{
            border-bottom: none;
        }}
        .interaction-number {{
            font-weight: bold;
            color: #667eea;
            font-size: 1.1em;
            margin-top: 5px;
        }}
        .interaction-info h4 {{
            margin: 0 0 5px 0;
            color: #333;
            font-size: 1em;
        }}
        .interaction-info p {{
            margin: 2px 0;
            color: #666;
            font-size: 0.85em;
            line-height: 1.3;
        }}
        .interaction-time {{
            color: #667eea;
            font-size: 0.85em;
            font-weight: 600;
            text-align: right;
            margin-top: 5px;
        }}
        .footer {{
            background: #f8f9fc;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        .no-interactions {{
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Zenfru AI</h1>
            <p>Daily Patient Interactions Report</p>
            <p>{formatted_date}</p>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>📊 Daily Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{stats['total_calls']}</div>
                        <div class="stat-label">Total Calls</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['new_bookings']}</div>
                        <div class="stat-label">New Bookings</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${stats['min_est_revenue']}</div>
                        <div class="stat-label">Min. Est. Revenue Booked</div>
                    </div>
        """
        
        # Always add the fourth stat card for consistent layout
        if stats.get('peak_hour') is not None:
            peak_hour = stats['peak_hour']
            peak_time = f"{peak_hour:02d}:00"
            html += f"""
                    <div class="stat-card">
                        <div class="stat-number">{peak_time}</div>
                        <div class="stat-label">Peak Hour ({stats['peak_hour_count']} calls)</div>
                    </div>
            """
        else:
            # Show success rate when no peak hour data is available
            html += f"""
                    <div class="stat-card">
                        <div class="stat-number">{stats['success_rate']}%</div>
                        <div class="stat-label">Success Rate</div>
                    </div>
            """
        
        html += """
                </div>
            </div>
        """
        
        # Add interaction categories
        html += """
            <div class="section">
                <h2>📋 Interactions by Category</h2>
        """
        
        category_labels = {
            "booking": "📅 New Appointments",
            "rescheduling": "🔄 Rescheduling",
            "confirmation": "✅ Confirmations", 
            "callback": "📞 Callback Requests",
            "faq": "❓ FAQ Queries",
            "new_patient_form": "📝 New Patient Forms",
            "misc": "📋 Other Interactions"
        }
        
        for category, interactions in categorized.items():
            if not interactions:
                continue
                
            html += f"""
                <div class="interaction-category">
                    <div class="category-header">
                        <span>{category_labels.get(category, category.title())}</span>
                        <span class="category-count">{len(interactions)} interactions</span>
                    </div>
                 
            """
            
            if self.config["reporting"]["include_patient_details"]:
                html += '<div class="interaction-list">'
                
                for index, interaction in enumerate(interactions[-10:], 1):  # Show last 10 interactions with numbering
                    timestamp = datetime.fromisoformat(interaction['timestamp'])
                    time_str = timestamp.strftime("%I:%M %p")
                    date_str = timestamp.strftime("%Y-%m-%d")
                    
                    # Build patient info with reason integrated beside the name
                    patient_name = interaction.get('patient_name', 'Unknown Patient')
                    reason = interaction.get('reason', '') or ''  # Handle None case
                    reason = reason.strip() if reason else ''
                    
                    # For booking interactions, use service_type as reason if reason is empty
                    if not reason and interaction.get('interaction_type') == 'booking':
                        service_type = interaction.get('service_type', '')
                        doctor = interaction.get('doctor', '')
                        if service_type:
                            reason = service_type
                            if doctor and not doctor.startswith('resources/'):
                                reason += f" with {doctor}"
                    
                    # First line: Name and reason
                    name_and_reason = patient_name
                    if reason:
                        name_and_reason += f" - {reason}"
                    
                    # Get appointment details from the interaction
                    appointment_date = interaction.get('details', {}).get('appointment_date', date_str)
                    appointment_start_time = interaction.get('details', {}).get('appointment_wall_start_time', '')
                    appointment_end_time = interaction.get('details', {}).get('appointment_wall_end_time', '')
                    
                    # Format appointment time range if available
                    appointment_time_str = ""
                    if appointment_start_time and appointment_end_time:
                        try:
                            start_dt = datetime.fromisoformat(appointment_start_time)
                            end_dt = datetime.fromisoformat(appointment_end_time)
                            appointment_time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
                        except:
                            appointment_time_str = "Time TBD"
                    else:
                        appointment_time_str = "Time TBD"
                    
                    contact_info = interaction.get('contact_number', 'N/A')
                    
                    html += f"""
                        <div class="interaction-item">
                            <div class="interaction-number">{index}</div>
                            <div class="interaction-info">
                                <h4>{name_and_reason}</h4>
                                <p>{appointment_date} {appointment_time_str}</p>
                                <p>Contact: {contact_info}</p>
                                <p>Call Time: {time_str}</p>
                            </div>
                            <div class="interaction-time">{time_str}</div>
                        </div>
                    """
                
                html += '</div>'
            else:
                html += '<div class="no-interactions">Patient details hidden for privacy</div>'
            
            html += '</div>'
        
        if not any(categorized.values()):
            html += '<div class="no-interactions">No interactions recorded for this date.</div>'
        
        # Add Callback Requests section
        html += """
            </div>
        </div>
        
       
        """
        
        if callback_requests:
            html += f'<div class="category-count">{len(callback_requests)} callback requests</div>'
            html += '<div class="interaction-list">'
            
            for index, callback in enumerate(callback_requests, 1):
                # Format time
                try:
                    timestamp = datetime.fromisoformat(callback['request_timestamp'])
                    time_str = timestamp.strftime("%I:%M %p")
                except:
                    time_str = "N/A"
                
                patient_name = callback.get('patient_name', 'Unknown Patient')
                contact_info = callback.get('contact_info', 'N/A')
                reason = callback.get('reason', 'No reason provided')
                
                html += f"""
                    <div class="interaction-item">
                        <div class="interaction-number">{index}</div>
                        <div class="interaction-info">
                            <h4>{patient_name}</h4>
                            <p>Contact: {contact_info}</p>
                            <p>Reason: {reason}</p>
                        </div>
                        <div class="interaction-time">{time_str}</div>
                    </div>
                """
            
            html += '</div>'
        else:
            html += '<div class="no-interactions">End of Report</div>'
        
        html += """
            </div>
        </div>
        
        <div class="footer">
            <p>Report generated automatically by Zenfru AI Assistant. All Rights Reserved</p>
            <p>Generated on """ + datetime.now().strftime("%B %d, %Y at %I:%M %p") + """</p>
        </div>
    </div>
</body>
</html>
        """
        
        return html
    
    def _generate_and_send_daily_report(self):
        """Generate and send daily report via email (timezone-aware)"""
        try:
            import pytz
            
            # Get timezone from config, default to Eastern
            timezone_str = self.config["reporting"].get("timezone", "US/Eastern")
            tz = pytz.timezone(timezone_str)
            
            # Use timezone-aware date calculation
            now = datetime.now(tz)
            yesterday = now.date() - timedelta(days=1)
            
            html_report = self.generate_daily_report(yesterday)
            
            # Save report to file
            report_file = self.log_directory / f"daily_report_{yesterday.strftime('%Y_%m_%d')}.html"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(html_report)
            
            # Send email if configured and available
            if EMAIL_AVAILABLE and self.config["email"]["recipients"] and self.config["email"]["username"]:
                self._send_email_report(html_report, yesterday)
                print(f"📧 Daily report sent at {now.strftime('%Y-%m-%d %I:%M %p %Z')} for {yesterday}")
            else:
                print(f"📧 Daily report generated but email not configured/available: {report_file}")
                
        except Exception as e:
            print(f"❌ Error generating/sending daily report: {e}")
            if EMAIL_AVAILABLE and self.config["fallback"]["backup_email"]:
                self._send_fallback_notification(str(e))
    
    def _send_email_report(self, html_report: str, report_date: date):
        """Send email report"""
        if not EMAIL_AVAILABLE:
            print("📧 Email functionality not available")
            return
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Daily Patient Interactions Report - {report_date.strftime('%B %d, %Y')}"
            msg['From'] = f"{self.config['email']['sender_name']} <{self.config['email']['username']}>"
            msg['To'] = ", ".join(self.config["email"]["recipients"])
            
            # Attach HTML report
            html_part = MIMEText(html_report, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.config["email"]["smtp_server"], self.config["email"]["smtp_port"]) as server:
                if self.config["email"]["use_tls"]:
                    server.starttls()
                server.login(self.config["email"]["username"], self.config["email"]["password"])
                server.send_message(msg)
            
            print(f"📧 Daily report sent successfully to {len(self.config['email']['recipients'])} recipients")
            
        except Exception as e:
            print(f"❌ Error sending email report: {e}")
            if self.config["fallback"]["backup_email"]:
                self._send_fallback_notification(f"Failed to send daily report: {e}")
    
    def _send_fallback_notification(self, error_message: str):
        """Send fallback notification in case of errors"""
        if not EMAIL_AVAILABLE:
            print(f"⚠️ Fallback notification failed - email not available: {error_message}")
            return
            
        try:
            if not self.config["fallback"]["backup_email"]:
                return
                
            msg = MIMEText(f"Daily report generation failed with error: {error_message}")
            msg['Subject'] = "Daily Report Generation Failed"
            msg['From'] = self.config["email"]["username"]
            msg['To'] = self.config["fallback"]["backup_email"]
            
            with smtplib.SMTP(self.config["email"]["smtp_server"], self.config["email"]["smtp_port"]) as server:
                if self.config["email"]["use_tls"]:
                    server.starttls()
                server.login(self.config["email"]["username"], self.config["email"]["password"])
                server.send_message(msg)
                
        except Exception as e:
            print(f"❌ Error sending fallback notification: {e}")
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update configuration settings with deep merge"""
        def deep_merge(target, source):
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    deep_merge(target[key], value)
                else:
                    target[key] = value
        
        deep_merge(self.config, new_config)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        print("📝 Configuration updated successfully")
    
    def get_interaction_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get summary of interactions over specified number of days"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        all_interactions = []
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            daily_interactions = self.get_daily_interactions(current_date)
            all_interactions.extend(daily_interactions)
        
        return {
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_interactions": len(all_interactions),
            "statistics": self._calculate_statistics(all_interactions),
            "daily_breakdown": {
                (start_date + timedelta(days=i)).strftime('%Y-%m-%d'): len(self.get_daily_interactions(start_date + timedelta(days=i)))
                for i in range(days)
            }
        }

# Global instance
patient_logger = PatientInteractionLogger()
