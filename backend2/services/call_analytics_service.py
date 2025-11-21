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

    def _ai_classify_call(self, transcript, analysis, metadata):
        """Use OpenAI to classify call_type and generate a concise call summary.
        Returns (call_type, summary) or (None, None) on failure.
        """
        try:
            if not self.openai_client:
                return None, None

            # Build plain text transcript
            lines = []
            for t in transcript or []:
                role = t.get("role", "agent")
                msg = t.get("message", "") or ""
                lines.append(f"{role}: {msg}")
            transcript_text = "\n".join(lines)[:6000]

            allowed_types = [
                "booking", "rescheduling", "confirmation", "general query",
                "callback request", "incomplete transcript", "unknown"
            ]

            prompt = (
                "You are classifying a phone call between an AI assistant and a patient.\n"
                "Return strict JSON with fields: call_type, summary.\n"
                f"Allowed call_type values: {allowed_types}.\n"
                "Rules:\n"
                "- If the user asks for a callback or the assistant offers to log one → 'callback request'.\n"
                "- If transcript is too short (greetings only) or insufficient to infer intent → 'incomplete transcript'.\n"
                "- Prefer booking/rescheduling/confirmation if clearly requested.\n"
                "- Otherwise use 'general query' if there is clear interaction but not the above.\n"
                "- Use 'unknown' only if none of the above fits.\n"
                "Summary: a single concise sentence (<= 20 words).\n\n"
                f"Transcript:\n{transcript_text}\n"
            )

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=180,
                temperature=0.2
            )
            content = response.choices[0].message.content or ""
            # Try to parse JSON
            result = None
            try:
                result = json.loads(content)
            except Exception:
                # Try to find JSON in text
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1 and end > start:
                    result = json.loads(content[start:end+1])
            if isinstance(result, dict):
                ctype = result.get("call_type")
                summary = result.get("summary") or ""
                if ctype in allowed_types:
                    return ctype, summary[:300]
            return None, None
        except Exception:
            return None, None
    
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
        """Analyze a call transcript and extract metrics for Google Sheets.
        Returns a dict with: timestamp, conversation_id, call_type, call_status,
        duration_secs, result_status (Success/Failure), failure_reason (optional),
        call_summary.
        """
        try:
            data = payload.get("data", {}) or {}
            metadata = data.get("metadata") or {}
            analysis = data.get("analysis") or {}
            transcript = data.get("transcript") or []
            unresolved_intent = False  # tracks intent expressed but not resolved
            # Count user messages early for special classification rules
            user_msg_count = sum(1 for t in transcript if t.get("role") == "user")
            
            # 1. Basic info
            conversation_id = data.get("conversation_id", "unknown")
            call_status = data.get("status", "unknown")  # done, failed, etc.
            
            # 2. Call duration
            duration_secs = metadata.get("call_duration_secs", 0)
            
            # 3. Call type - from data collection results
            data_collection = analysis.get("data_collection_results", {})
            reason_data = data_collection.get("reason", {})
            call_type = reason_data.get("value") or "unknown"

            # Transcript summary (used for failure reason logic elsewhere)
            # Normalize potentially None fields to empty string/dict
            transcript_summary = analysis.get("transcript_summary") or ""
            eval_results = analysis.get("evaluation_criteria_results") or {}

            # Call summary should come from the zenfrueval rationale if present
            zen_eval = eval_results.get("zenfrueval", {}) if isinstance(eval_results, dict) else {}
            call_summary = (zen_eval.get("rationale") or "") if isinstance(zen_eval, dict) else ""

            # Fallbacks if zenfrueval isn't present or empty
            if not call_summary:
                # Prefer transcript_summary if available
                if transcript_summary:
                    call_summary = transcript_summary
                else:
                    # Build from other evaluation rationales (first 2)
                    if isinstance(eval_results, dict):
                        rationales = [v.get("rationale") for v in eval_results.values() if v.get("rationale")]
                        if rationales:
                            call_summary = " ".join(rationales[:2])[:500]

            # Callback request detection (only if still unknown or general query)
            if call_type in ["unknown", "general query"]:
                lower_messages = [(t.get("message") or "").lower() for t in transcript]
                user_text_all = " ".join(lower_messages)
                user_messages_only = " ".join([m for t, m in zip(transcript, lower_messages) if t.get("role") == "user"])
                summary_lower = call_summary.lower()

                # 3a. Identify explicit callback intent
                callback_phrases = [
                    "callback request", "log a callback", "request a callback", "call me back",
                    "someone call me back", "have someone call me", "have sissy call", "have the receptionist call",
                    "can someone call", "please call me back", "leave a callback", "leave a message to call"
                ]
                if any(p in user_messages_only for p in callback_phrases) or any(p in summary_lower for p in callback_phrases):
                    call_type = "callback request"
                else:
                    # 3b. Classify as incomplete transcript if too short/insufficient info
                    incomplete_phrases = [
                        "transcript is incomplete", "too short to determine", "insufficient information",
                        "could not determine call reason", "not enough information", "unable to determine the outcome",
                        "insufficient context"
                    ]
                    user_msg_count_local = sum(1 for t in transcript if t.get("role") == "user")
                    total_turns = len(transcript)
                    too_short_numeric = duration_secs < 12 or total_turns < 3 or user_msg_count_local == 0
                    mentions_incomplete = any(p in summary_lower for p in incomplete_phrases) or any(p in user_text_all for p in incomplete_phrases)

                    if too_short_numeric or mentions_incomplete:
                        call_type = "incomplete transcript"

            # Summary-based overrides and classification
            if call_summary:
                summary_lower = call_summary.lower()
                resolution_keywords = [
                    # Booking
                    "appointment booked", "appointment scheduled", "booked for", "scheduled for", "your appointment is set",
                    "successfully scheduled", "successfully booked",
                    # Confirmation
                    "confirmed for", "appointment confirmed", "confirmed the appointment", "appointment was confirmed",
                    "appointment successfully confirmed", "successfully confirmed", "confirmation completed",
                    # Rescheduling
                    "rescheduled", "successfully rescheduled", "reschedule completed", "moved to", "updated to",
                    # Callback logged (resolution via callback)
                    "callback request logged", "logged a callback request", "successfully logged a callback request",
                    "logged a callback", "callback details confirmed", "confirmed the callback details",
                    "will call you back", "we will call you back"
                ]
                intent_keywords = [
                    "schedule", "book", "appointment", "reschedul", "confirm", "callback", "call back"
                ]
                has_resolution = any(k in summary_lower for k in resolution_keywords)
                has_intent_only = (not has_resolution) and any(k in summary_lower for k in intent_keywords)
                agent_last = transcript and transcript[-1].get("role") == "agent"

                # If intent present but no resolution and agent spoke last (waiting on user)
                # retain original intent instead of forcing 'incomplete transcript'
                if has_intent_only and agent_last and call_type in ["booking", "rescheduling", "confirmation", "general query", "unknown", "incomplete transcript"]:
                    # Derive an intent type if current is generic/unknown/incomplete
                    if call_type in ["general query", "unknown", "incomplete transcript"]:
                        if "reschedul" in summary_lower:
                            call_type = "rescheduling"
                        elif "confirm" in summary_lower:
                            call_type = "confirmation"
                        elif "schedule" in summary_lower or "book" in summary_lower or "appointment" in summary_lower:
                            call_type = "booking"
                    unresolved_intent = True
                # Also catch greeting + inquiry patterns without progress
                if ("greeted" in summary_lower or "inquired" in summary_lower) and has_intent_only and not has_resolution:
                    unresolved_intent = True

                # Rescheduling via logged callback: treat as rescheduling not incomplete
                if ("reschedul" in summary_lower) and any(cb in summary_lower for cb in ["callback request", "logged a callback", "callback details confirmed"]):
                    if call_type == "incomplete transcript":
                        call_type = "rescheduling"

                # Positive success signals should set explicit call types regardless of last speaker
                negative_markers = [
                    "unable to", "was unable to", "not able to", "couldn't", "failed to", "cannot", "can't",
                    "didn't manage to", "did not manage to"
                ]
                is_positive = not any(n in summary_lower for n in negative_markers)
                if is_positive:
                    if any(p in summary_lower for p in [
                        "confirmed the appointment", "appointment was confirmed", "appointment confirmed", "successfully confirmed", "confirmation completed"
                    ]):
                        call_type = "confirmation"
                    elif any(p in summary_lower for p in [
                        "appointment booked", "appointment scheduled", "booked for", "scheduled for", "successfully scheduled", "successfully booked", "your appointment is set"
                    ]):
                        call_type = "booking"
                    elif any(p in summary_lower for p in [
                        "rescheduled", "successfully rescheduled", "reschedule completed", "moved to", "updated to"
                    ]):
                        call_type = "rescheduling"

            # As a final fallback, ask AI to classify if still unknown
            if call_type == "unknown":
                ai_ctype, ai_summary = self._ai_classify_call(data.get("transcript"), analysis, metadata)
                if ai_ctype:
                    call_type = ai_ctype
                if ai_summary and not call_summary:
                    call_summary = ai_summary
            
            # 4. Success/Failure determination (eliminated 'Unknown' result status)
            call_successful = analysis.get("call_successful", "unknown")

            if call_successful == "success":
                result_status = "Success"
                failure_reason = None
            else:
                # Attempt to derive a failure reason for both explicit failures and previously 'unknown'
                failure_reason = self._determine_failure_reason(data, metadata, analysis)

                # user_msg_count already computed above

                # If the summary shows a resolved outcome via a logged callback (e.g., reschedule via callback),
                # remove AI-limitation failures and treat as success.
                summary_lower_post = (call_summary or "").lower()
                callback_resolution_markers = [
                    "callback request logged", "logged a callback request", "successfully logged a callback request",
                    "logged a callback", "callback details confirmed", "confirmed the callback details"
                ]
                if failure_reason and any(m in summary_lower_post for m in callback_resolution_markers):
                    # Only clear failure if the summary indicates intent (reschedule/book/confirm) and no strong negatives
                    if any(x in summary_lower_post for x in ["reschedul", "book", "schedule", "confirm"]):
                        if not any(n in summary_lower_post for n in [
                            "unable to", "was unable to", "not able to", "couldn't", "failed to", "cannot", "can't",
                            "didn't manage to", "did not manage to"
                        ]):
                            failure_reason = None

                # Prefer specific AI limitation: transfer to receptionist not supported
                transfer_markers = [
                    "transfer", "receptionist", "front desk", "connect me", "patch me", "speak with", "talk to"
                ]
                transfer_inability_markers = [
                    "unable to transfer", "cannot transfer", "can't transfer", "did not transfer", "didn't transfer", "couldn't transfer"
                ]
                has_transfer_intent = any(k in summary_lower_post for k in transfer_markers)
                has_transfer_inability = any(k in summary_lower_post for k in transfer_inability_markers)
                if (has_transfer_intent and (has_transfer_inability or "assistant" in summary_lower_post or "receptionist" in summary_lower_post)):
                    specific_limitation = "AI limitation: Agent cannot transfer calls to receptionist"
                    if (not failure_reason) or failure_reason.startswith("AI limitation") or failure_reason.startswith("Incomplete Transcript") or failure_reason.startswith("Mid-Call Hangup"):
                        failure_reason = specific_limitation

                # If summary clearly indicates abrupt end/incomplete, prefer hangup over generic AI limitation
                incomplete_markers = [
                    "conversation is incomplete", "ends abruptly", "abruptly", "incomplete transcript", "no further interaction",
                    "insufficient information", "too short to determine"
                ]
                if failure_reason and failure_reason.startswith("AI limitation") and any(m in summary_lower_post for m in incomplete_markers) and not has_transfer_intent:
                    failure_reason = "Mid-Call Hangup: Patient hung up during conversation"

                # Criteria for treating as failure when previously 'unknown':
                # - No user messages
                # - Incomplete transcript classification
                # - A derived failure_reason exists
                # - Very short duration / early hangup / timeout handled in failure_reason helper
                if call_successful == "unknown" and failure_reason is None and (call_type == "incomplete transcript" or user_msg_count == 0):
                    # Provide explicit reason if none inferred (unify incomplete wording with standard hangup phrasing)
                    failure_reason = "No User Input: Patient did not respond" if user_msg_count == 0 else "Mid-Call Hangup: Patient hung up during conversation"

                if failure_reason is None:
                    # If unresolved intent (patient dropped after expressing intent) treat as failure
                    if unresolved_intent:
                        failure_reason = "Mid-Call Hangup: Patient hung up during conversation"
                        result_status = "Failure"
                    elif call_type == "incomplete transcript":
                        # Prefer hangup wording if summary reflects abrupt ending/incomplete conversation
                        summary_lower_post = (call_summary or "").lower()
                        abrupt_markers = [
                            "ends abruptly", "ended abruptly", "abruptly", "conversation is incomplete", "incomplete transcript",
                            "no further interaction", "stopped responding", "hung up"
                        ]
                        if any(m in summary_lower_post for m in abrupt_markers):
                            failure_reason = "Mid-Call Hangup: Patient hung up during conversation"
                        else:
                            failure_reason = "Incomplete Transcript: Conversation ended before resolution"
                        result_status = "Failure"
                    else:
                        result_status = "Success"
                else:
                    result_status = "Failure"
            
            # Timestamp
            start_time = metadata.get("start_time_unix_secs")
            timestamp = (datetime.fromtimestamp(start_time, tz=ZoneInfo("America/New_York")) 
                        if start_time else datetime.now(ZoneInfo("America/New_York")))
            
            # Final override: if patient never spoke, classify as no conversation with blank-style result
            if user_msg_count == 0:
                call_type = "no conversation"
                # Use dash to indicate N/A result per requirement
                result_status = "-"
                # Failure reason should be empty (None so downstream becomes blank string)
                failure_reason = None

            return {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "conversation_id": conversation_id,
                "call_type": call_type,
                "call_status": call_status,
                "duration_secs": duration_secs,
                "result_status": result_status,
                "failure_reason": failure_reason,
                "call_summary": call_summary or ""
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
        termination = metadata.get("termination_reason") or ""
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
            error_reason = (error_dict.get("reason") or str(error))
            
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
                last_user_msg = (user_messages[-1].get("message") or "").lower()
                
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
                metrics["failure_reason"] or "",
                metrics.get("call_summary", "")
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
