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

# Import local cache service to fetch appointment details
from .local_cache_service import LocalCacheService

# Optional email imports - make email functionality optional
try:
    import smtplib
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
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
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with default config
                    for key in default_config:
                        if key in loaded_config:
                            default_config[key].update(loaded_config[key])
                        else:
                            loaded_config[key] = default_config[key]
                    return loaded_config
            except Exception as e:
                print(f"Error loading config file, using defaults: {e}")
        
        # Save default config
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def _setup_daily_scheduler(self):
        """Setup the daily report scheduler"""
        if not EMAIL_AVAILABLE:
            print("📅 Daily report scheduler disabled - email functionality not available")
            return
            
        report_time = self.config["reporting"]["daily_email_time"]
        schedule.every().day.at(report_time).do(self._generate_and_send_daily_report)
        
        # Start scheduler in a separate thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print(f"📅 Daily report scheduler started - reports will be sent at {report_time}")
    
    def _fetch_appointment_details(self, appointment_id: str) -> Dict[str, Optional[str]]:
        """
        Fetch appointment details from local cache using appointment_id
        Returns patient_name, contact_number, service_type, and doctor
        """
        if not appointment_id:
            return {"patient_name": None, "contact_number": None, "service_type": None, "doctor": None}
        
        try:
            # Clean appointment_id - remove 'appointments/' prefix if present
            clean_id = appointment_id.replace("appointments/", "") if appointment_id.startswith("appointments/") else appointment_id
            full_id = f"appointments/{clean_id}"
            
            # Try both formats
            appointment_data = self.cache_service.get_appointment_by_id(full_id)
            if not appointment_data:
                appointment_data = self.cache_service.get_appointment_by_id(clean_id)
            
            if appointment_data:
                # Also try to get stored patient info from the database table
                stored_info = self._get_stored_appointment_info(full_id) or self._get_stored_appointment_info(clean_id)
                
                # Extract patient details from appointment data
                contact = appointment_data.get("contact", {})
                
                # Get patient name
                given_name = contact.get("given_name", "")
                family_name = contact.get("family_name", "")
                contact_name = contact.get("name", "")
                
                if contact_name:
                    patient_name = contact_name
                elif given_name and family_name:
                    patient_name = f"{given_name} {family_name}"
                elif given_name:
                    patient_name = given_name
                elif stored_info:
                    patient_name = stored_info.get("patient_name")
                else:
                    patient_name = None
                
                # Get contact number from phone_numbers array
                contact_number = None
                phone_numbers = contact.get("phone_numbers", [])
                primary_phone = contact.get("primary_phone_number", "")
                
                if primary_phone:
                    contact_number = primary_phone
                elif phone_numbers and len(phone_numbers) > 0:
                    contact_number = phone_numbers[0].get("number", "")
                elif stored_info and stored_info.get("patient_phone"):
                    contact_number = stored_info.get("patient_phone")
                
                # Get service/procedure information
                service_type = (appointment_data.get("service") or 
                              appointment_data.get("procedure") or 
                              appointment_data.get("appointment_type") or
                              appointment_data.get("type"))
                
                # Get doctor/provider information
                doctor = (appointment_data.get("doctor") or 
                         appointment_data.get("provider") or
                         appointment_data.get("practitioner"))
                
                print(f"📋 Fetched appointment details for {appointment_id}: {patient_name}, {contact_number}")
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
    
    def _get_stored_appointment_info(self, appointment_id: str) -> Optional[Dict[str, str]]:
        """Get stored appointment info from database table"""
        try:
            import sqlite3
            from pathlib import Path
            
            db_path = Path(__file__).parent.parent / "cache.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT patient_name, patient_phone FROM appointments 
                WHERE appointment_id = ?
            ''', (appointment_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "patient_name": result[0],
                    "patient_phone": result[1]
                }
            return None
        except Exception as e:
            print(f"Error getting stored appointment info: {e}")
            return None
    
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
        error_message: Optional[str] = None
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
        
        # Sanitize contact number for privacy in logs
        sanitized_contact = self._sanitize_contact(contact_number) if contact_number else None
        
        log_entry = {
            "interaction_id": interaction_id,
            "timestamp": timestamp.isoformat(),
            "date": timestamp.date().isoformat(),
            "time": timestamp.time().isoformat(),
            "interaction_type": interaction_type,
            "patient_name": patient_name,
            "contact_number": sanitized_contact,
            "success": success,
            "appointment_id": appointment_id,
            "service_type": service_type,
            "doctor": doctor,
            "error_message": error_message,
            "details": details or {}
        }
        
        # Save to daily log file
        self._save_to_daily_log(log_entry, timestamp.date())
        
        print(f"📝 Logged {interaction_type} interaction: {interaction_id} - Success: {success}")
        return interaction_id
    
    def _sanitize_contact(self, contact_number: str) -> str:
        """Sanitize contact number for privacy (show only last 4 digits)"""
        if not contact_number or len(contact_number) < 4:
            return "****"
        return "*" * (len(contact_number) - 4) + contact_number[-4:]
    
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
    
    def _generate_html_report(self, report_date: date, stats: Dict[str, Any], categorized: Dict[str, List[Dict[str, Any]]]) -> str:
        """Generate professional HTML report"""
        
        # Format date for display
        formatted_date = report_date.strftime("%B %d, %Y")
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Patient Interactions Report - {formatted_date}</title>
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
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
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
            background: rgba(255, 255, 255, 0.2);
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.9em;
        }}
        .interaction-list {{
            max-height: 400px;
            overflow-y: auto;
        }}
        .interaction-item {{
            padding: 15px 20px;
            border-bottom: 1px solid #f0f0f0;
            display: grid;
            grid-template-columns: 1fr 150px 100px;
            gap: 15px;
            align-items: center;
        }}
        .interaction-item:last-child {{
            border-bottom: none;
        }}
        .interaction-info h4 {{
            margin: 0 0 5px 0;
            color: #333;
        }}
        .interaction-info p {{
            margin: 0;
            color: #666;
            font-size: 0.9em;
        }}
        .interaction-time {{
            color: #666;
            font-size: 0.9em;
        }}
        .status-badge {{
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: 600;
            text-align: center;
        }}
        .status-success {{
            background: #d4edda;
            color: #155724;
        }}
        .status-failed {{
            background: #f8d7da;
            color: #721c24;
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
        .success-rate {{
            font-size: 1.1em;
            margin-top: 5px;
        }}
        .success-high {{ color: #28a745; }}
        .success-medium {{ color: #ffc107; }}
        .success-low {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1> Zenfru AI</h1>
            <p>Daily Patient Interactions Report - {formatted_date}</p>
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
                        <div class="stat-number">{stats['successful_calls']}</div>
                        <div class="stat-label">Successful</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['failed_calls']}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['success_rate']}%</div>
                        <div class="stat-label">Success Rate</div>
                    </div>
        """
        
        # Add peak hour if available
        if stats.get('peak_hour') is not None:
            peak_hour = stats['peak_hour']
            peak_time = f"{peak_hour:02d}:00"
            html += f"""
                    <div class="stat-card">
                        <div class="stat-number">{peak_time}</div>
                        <div class="stat-label">Peak Hour ({stats['peak_hour_count']} calls)</div>
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
                
            success_count = sum(1 for i in interactions if i.get('success', False))
            success_rate = (success_count / len(interactions) * 100) if interactions else 0
            success_class = "success-high" if success_rate >= 80 else "success-medium" if success_rate >= 60 else "success-low"
            
            html += f"""
                <div class="interaction-category">
                    <div class="category-header">
                        <span>{category_labels.get(category, category.title())}</span>
                        <span class="category-count">{len(interactions)} interactions</span>
                    </div>
                 
            """
            
            if self.config["reporting"]["include_patient_details"]:
                html += '<div class="interaction-list">'
                
                for interaction in interactions[-10:]:  # Show last 10 interactions
                    timestamp = datetime.fromisoformat(interaction['timestamp'])
                    time_str = timestamp.strftime("%I:%M %p")
                    
                    patient_info = interaction.get('patient_name', 'Unknown Patient')
                    if interaction.get('service_type'):
                        patient_info += f" - {interaction['service_type']}"
                    if interaction.get('doctor'):
                        patient_info += f" with {interaction['doctor']}"
                    
                    status_class = "status-success" if interaction.get('success', False) else "status-failed"
                    status_text = "Success" if interaction.get('success', False) else "Failed"
                    
                    error_info = ""
                    if not interaction.get('success', False) and interaction.get('error_message'):
                        error_info = f"<p>Error: {interaction['error_message'][:100]}...</p>"
                    
                    html += f"""
                        <div class="interaction-item">
                            <div class="interaction-info">
                                <h4>{patient_info}</h4>
                                <p>Contact: {interaction.get('contact_number', 'N/A')}</p>
                                {error_info}
                            </div>
                            <div class="interaction-time">{time_str}</div>
                            <div class="status-badge {status_class}">{status_text}</div>
                        </div>
                    """
                
                html += '</div>'
            else:
                html += '<div class="no-interactions">Patient details hidden for privacy</div>'
            
            html += '</div>'
        
        if not any(categorized.values()):
            html += '<div class="no-interactions">No interactions recorded for this date.</div>'
        
        html += """
            </div>
        </div>
        
        <div class="footer">
            <p>Report generated automatically by Zenfru AI Assistant</p>
            <p>Generated on """ + datetime.now().strftime("%B %d, %Y at %I:%M %p") + """</p>
        </div>
    </div>
</body>
</html>
        """
        
        return html
    
    def _generate_and_send_daily_report(self):
        """Generate and send daily report via email"""
        try:
            yesterday = date.today() - timedelta(days=1)
            html_report = self.generate_daily_report(yesterday)
            
            # Save report to file
            report_file = self.log_directory / f"daily_report_{yesterday.strftime('%Y_%m_%d')}.html"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(html_report)
            
            # Send email if configured and available
            if EMAIL_AVAILABLE and self.config["email"]["recipients"] and self.config["email"]["username"]:
                self._send_email_report(html_report, yesterday)
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
            msg = MimeMultipart('alternative')
            msg['Subject'] = f"Daily Patient Interactions Report - {report_date.strftime('%B %d, %Y')}"
            msg['From'] = f"{self.config['email']['sender_name']} <{self.config['email']['username']}>"
            msg['To'] = ", ".join(self.config["email"]["recipients"])
            
            # Attach HTML report
            html_part = MimeText(html_report, 'html')
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
                
            msg = MimeText(f"Daily report generation failed with error: {error_message}")
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
        """Update configuration settings"""
        self.config.update(new_config)
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
