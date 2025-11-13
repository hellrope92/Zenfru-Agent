import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

class CallAnalyticsService:
    def __init__(self):
        # Initialize Google Sheets connection
        self.sheet = None
        self._init_google_sheets()
        
        # Initialize OpenAI client for summarization
        self.openai_client = None
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.openai_client = OpenAI(api_key=openai_key)
    
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
                
                # If failure reason is None (natural end), mark as Success instead
                if failure_reason is None:
                    result_status = "Success"
            
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
    
    def _summarize_with_ai(self, text, category):
        """Use OpenAI to create concise summary of failure reason"""
        if not self.openai_client or not text:
            return text[:100]  # Fallback to simple truncation
        
        try:
            if category == "Technical Error":
                prompt = f"""Summarize this technical error in ONE short sentence (max 15 words):

{text}

Focus on what tool/system failed and what it couldn't do. Start with "Tool call failed" or similar.
Format: Just the concise reason, no category prefix."""
            else:
                prompt = f"""Summarize this in ONE short sentence (max 12 words):

{text}

Focus on what the agent cannot do by design (not a technical failure).
Format: Just the concise reason, no category prefix."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=40,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            print(f"AI summarization error: {e}")
            return text[:100]  # Fallback
    
    def _determine_failure_reason(self, data, metadata, analysis):
        """Determine detailed, manager-friendly failure reason"""
        termination = metadata.get("termination_reason", "")
        call_duration = metadata.get("call_duration_secs", 0)
        transcript = data.get("transcript", [])
        transcript_length = len(transcript)
        
        # Get transcript summary and evaluation rationale
        transcript_summary = analysis.get("transcript_summary", "")
        eval_results = analysis.get("evaluation_criteria_results", {})
        
        # 1. Check for network/system errors first
        error = metadata.get("error")
        if error:
            error_dict = error if isinstance(error, dict) else {}
            error_code = error_dict.get("code", "")
            error_reason = error_dict.get("reason", str(error))
            
            if error_code == 1002 or "No user message received" in error_reason:
                return "Network Issue: Patient's connection dropped or phone signal lost"
            elif "timeout" in error_reason.lower():
                return "Inactivity Timeout: Patient stopped responding"
            else:
                return f"Technical Error: {error_reason[:80]}"
        
        # 2. Check evaluation rationale for technical failures vs AI limitations
        for eval_name, eval_data in eval_results.items():
            rationale = eval_data.get("rationale", "")
            result = eval_data.get("result", "")
            
            if result == "failure" and rationale:
                rationale_lower = rationale.lower()
                
                # TECHNICAL ERROR: Tool/system failures
                if any(keyword in rationale_lower for keyword in [
                    "tool call failed", "tool failed", "tool error",
                    "unable to retrieve", "failed to retrieve", "couldn't retrieve",
                    "failed to book", "couldn't book", "unable to book",
                    "failed to confirm", "couldn't confirm", "unable to confirm",
                    "failed to reschedule", "couldn't reschedule", "unable to reschedule",
                    "system error", "api error", "database error"
                ]):
                    summary = self._summarize_with_ai(rationale, "Technical Error")
                    return f"Technical Error: {summary}"
        
        # 3. Analyze call termination patterns
        if "hung up" in termination.lower() or "ended by remote" in termination.lower():
            user_messages = [t for t in transcript if t.get("role") == "user"]
            
            # Early hangup - patient didn't want to interact
            if call_duration < 10:
                return "Early Hangup: Patient hung up within first 10 seconds"
            
            # Check last user message for intent
            if user_messages:
                last_user_msg = user_messages[-1].get("message", "").lower()
                
                # Patient wanted human/escalation - this is AI LIMITATION (agent can't transfer by design)
                wanted_human = any(word in last_user_msg for word in 
                                 ["receptionist", "human", "person", "transfer", "assistant", "someone"])
                
                # Check for language barrier - AI LIMITATION
                wanted_spanish = any(word in last_user_msg for word in ["spanish", "español", "espanol"])
                
                if wanted_spanish:
                    return "AI limitation: Agent cannot speak Spanish"
                
                if wanted_human:
                    return "AI limitation: Agent cannot transfer calls to receptionist"
                
                # Natural end with "bye/thank you" - NOT A FAILURE, skip this
                if any(word in last_user_msg for word in ["bye", "thank", "okay", "ok"]):
                    # Check if there was an underlying technical issue
                    if transcript_summary:
                        summary_lower = transcript_summary.lower()
                        # Check for tool failures
                        if any(keyword in summary_lower for keyword in [
                            "tool call failed", "failed to retrieve", "unable to retrieve",
                            "failed to book", "failed to confirm", "couldn't book"
                        ]):
                            summary = self._summarize_with_ai(transcript_summary, "Technical Error")
                            return f"Technical Error: {summary}"
                        # Check for AI limitations (can't transfer, etc.)
                        elif any(keyword in summary_lower for keyword in [
                            "unable to transfer", "cannot transfer", "can't transfer",
                            "unable to directly transfer"
                        ]):
                            return "AI limitation: Agent cannot transfer calls to receptionist"
                    
                    # Pure natural end - this should not be marked as failure
                    # Return None so it doesn't get logged as failure
                    return None
            
            # Mid-call hangup without clear reason
            return "Mid-Call Hangup: Patient hung up during conversation"
        
        # 4. Timeout scenarios
        if "timeout" in termination.lower():
            return "Inactivity Timeout: Patient stopped responding"
        
        # 5. Very short calls
        if call_duration < 5:
            return "Early Hangup: Call lasted less than 5 seconds"
        
        # 6. Check evaluation rationale for remaining failures
        for eval_name, eval_data in eval_results.items():
            rationale = eval_data.get("rationale", "")
            if rationale and len(rationale) > 20:
                rationale_lower = rationale.lower()
                
                # Check if it's actually a technical error
                if any(keyword in rationale_lower for keyword in [
                    "tool", "failed to", "couldn't", "unable to retrieve",
                    "error", "failed"
                ]):
                    summary = self._summarize_with_ai(rationale, "Technical Error")
                    return f"Technical Error: {summary}"
                else:
                    summary = self._summarize_with_ai(rationale, "AI limitation")
                    return f"AI limitation: {summary}"
        
        return f"Mid-Call Hangup: Call ended after {call_duration}s"
    
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
