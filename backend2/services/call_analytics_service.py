import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from zoneinfo import ZoneInfo

class CallAnalyticsService:
    def __init__(self):
        # Initialize Google Sheets connection
        self.sheet = None
        self._init_google_sheets()
    
    def _init_google_sheets(self):
        """Initialize Google Sheets API connection"""
        try:
            # Get credentials from environment variable
            creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
            if not creds_json:
                print("Warning: GOOGLE_SHEETS_CREDENTIALS not found")
                return
            
            # Parse JSON credentials
            creds_dict = json.loads(creds_json)
            
            # Define scope
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Authenticate
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            
            # Open the spreadsheet
            spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
            if not spreadsheet_id:
                print("Warning: GOOGLE_SPREADSHEET_ID not found")
                return
            
            self.sheet = client.open_by_key(spreadsheet_id).sheet1
            print("✓ Google Sheets connected successfully")
            
        except Exception as e:
            print(f"Error initializing Google Sheets: {e}")
            self.sheet = None
    
    def analyze_call(self, payload):
        """
        Analyze a call transcript and extract metrics
        
        Returns:
            dict: Call metrics including call type, status, duration, failure reason
        """
        try:
            data = payload.get("data", {})
            metadata = data.get("metadata", {})
            analysis = data.get("analysis", {})
            
            # 1. Basic info
            conversation_id = data.get("conversation_id", "unknown")
            call_status = data.get("status", "unknown")  # done, failed, etc.
            
            # 2. Call duration
            duration_secs = metadata.get("call_duration_secs", 0)
            
            # 3. Call type - from data collection results
            data_collection = analysis.get("data_collection_results", {})
            reason_data = data_collection.get("reason", {})
            call_type = reason_data.get("value") or "unknown"
            
            # 4. Success/Failure/Unknown determination
            call_successful = analysis.get("call_successful", "unknown")
            
            # Map to success/failure/unknown
            if call_successful == "success":
                result_status = "Success"
                failure_reason = None
            elif call_successful == "unknown":
                result_status = "Unknown"
                failure_reason = None
            else:
                result_status = "Failure"
                # Try to determine failure reason
                failure_reason = self._determine_failure_reason(data, metadata, analysis)
            
            # Timestamp
            start_time = metadata.get("start_time_unix_secs")
            timestamp = (datetime.fromtimestamp(start_time, tz=ZoneInfo("America/New_York")) 
                        if start_time else datetime.now(ZoneInfo("America/New_York")))
            
            return {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "conversation_id": conversation_id,
                "call_type": call_type,
                "call_status": call_status,
                "duration_secs": duration_secs,
                "result_status": result_status,
                "failure_reason": failure_reason
            }
            
        except Exception as e:
            print(f"Error analyzing call: {e}")
            return None
    
    def _determine_failure_reason(self, data, metadata, analysis):
        """Determine detailed, manager-friendly failure reason"""
        termination = metadata.get("termination_reason", "")
        call_duration = metadata.get("call_duration_secs", 0)
        transcript = data.get("transcript", [])
        transcript_length = len(transcript)
        
        # Get transcript summary for context
        transcript_summary = analysis.get("transcript_summary", "")
        
        # Check for system errors first
        error = metadata.get("error")
        if error:
            error_dict = error if isinstance(error, dict) else {}
            error_code = error_dict.get("code", "")
            error_reason = error_dict.get("reason", str(error))
            
            # Translate technical errors to manager-friendly language
            if error_code == 1002 or "No user message received" in error_reason:
                return "Network Issue: Patient's connection dropped or phone signal lost during call"
            elif error_code == 1001 or "timeout" in error_reason.lower():
                return "Timeout: Patient stopped responding mid-conversation"
            elif "authentication" in error_reason.lower():
                return "System Error: Authentication failed (technical issue)"
            else:
                return f"Technical Error: {error_reason[:100]}"  # Limit length but keep detail
        
        # Analyze call termination
        if "hung up" in termination.lower() or "ended by remote" in termination.lower():
            user_messages = [t for t in transcript if t.get("role") == "user"]
            
            if not user_messages:
                return "No Response: Patient didn't speak during the call"
            elif call_duration < 30 or len(user_messages) <= 2:
                return "Early Hangup: Patient hung up after brief interaction (likely didn't want to talk to AI)"
            elif transcript_length < 5:
                return "Premature End: Patient ended call with minimal interaction"
            
            # Check last user message for context
            last_user_msg = user_messages[-1].get("message", "").lower()
            
            # Check if patient wanted escalation (human/receptionist/transfer)
            wanted_human = any(word in last_user_msg for word in ["receptionist", "human", "person", "transfer", "assistant"])
            
            # Natural conversation end
            if any(word in last_user_msg for word in ["bye", "thank", "okay", "ok"]):
                # Use transcript summary for detailed context if available
                if transcript_summary and len(transcript_summary) > 50:
                    summary_lower = transcript_summary.lower()
                    # Check if there was an agent limitation
                    if "unable to" in summary_lower or "could not" in summary_lower or "couldn't" in summary_lower:
                        summary_snippet = transcript_summary[:150].strip()
                        summary_snippet = summary_snippet.replace("The user called", "User called")
                        summary_snippet = summary_snippet.replace("The patient called", "Patient called")
                        return f"Agent limitation: {summary_snippet}..."
                
                return "Natural End: Patient ended call after normal conversation"
            
            # Patient wanted escalation but hung up
            if wanted_human:
                if transcript_summary and len(transcript_summary) > 50:
                    summary_snippet = transcript_summary[:120].strip()
                    summary_snippet = summary_snippet.replace("The user called", "User called")
                    summary_snippet = summary_snippet.replace("The patient called", "Patient called")
                    return f"Agent limitation: {summary_snippet}"
                
                return "Agent limitation: Patient wanted to speak with human staff"
            
            return "Mid-Call Hangup: Patient hung up during conversation (reason unclear)"
        
        # Check AI evaluation
        call_successful = analysis.get("call_successful")
        if call_successful == "failure":
            # Try to get more context from evaluation
            eval_results = analysis.get("evaluation_criteria_results", {})
            if eval_results:
                for eval_name, eval_data in eval_results.items():
                    rationale = eval_data.get("rationale", "")
                    if rationale:
                        return f"AI Failed Task: {rationale[:150]}"
            
            # Check data collection for clues
            data_collection = analysis.get("data_collection_results", {})
            reason_data = data_collection.get("reason", {})
            call_type = reason_data.get("value")
            
            if call_type in ["booking", "rescheduling"]:
                return f"Incomplete {call_type.title()}: AI couldn't complete the appointment process"
            else:
                return "Goal Not Achieved: AI determined the call objective wasn't met"
        
        # Very short calls
        if call_duration < 5:
            return "Immediate Disconnect: Call lasted less than 5 seconds (likely accidental dial or immediate hangup)"
        
        if transcript_length < 3:
            return "Minimal Interaction: Very few exchanges between patient and AI (likely technical issue or immediate disconnect)"
        
        # Check termination patterns
        if "voicemail" in termination.lower():
            return "Voicemail: Call went to voicemail"
        if "timeout" in termination.lower():
            return "Inactivity Timeout: Patient stopped responding and call timed out"
        
        # Default with context
        context = f"with {transcript_length} interactions" if call_duration > 60 else ""
        return f"Unknown Failure: Call ended after {call_duration}s {context}(reason not determined)".replace("  ", " ")
    
    def push_to_sheets(self, metrics):
        """Push call metrics to Google Sheets"""
        if not self.sheet:
            print("Google Sheets not initialized, skipping push")
            return False
        
        try:
            # Prepare row data
            row = [
                metrics["timestamp"],
                metrics["conversation_id"],
                metrics["call_type"],
                metrics["call_status"],
                metrics["duration_secs"],
                metrics["result_status"],
                metrics["failure_reason"] or ""
            ]
            
            # Append to sheet
            self.sheet.append_row(row)
            print(f"✓ Pushed call analytics to Google Sheets: {metrics['conversation_id']}")
            return True
            
        except Exception as e:
            print(f"Error pushing to Google Sheets: {e}")
            return False
    
    def process_call(self, payload):
        """Complete pipeline: analyze and push to sheets"""
        metrics = self.analyze_call(payload)
        if metrics:
            self.push_to_sheets(metrics)
            return metrics
        return None


# Singleton instance
_analytics_service = None

def get_analytics_service():
    """Get or create analytics service instance"""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = CallAnalyticsService()
    return _analytics_service
