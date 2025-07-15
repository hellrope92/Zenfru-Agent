"""
Conversation Logging API endpoint
Creates conversation logs at the end of each call
Tracks patient interactions and outcomes
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pathlib import Path
import logging
import asyncio

from api.models import LogConversationRequest

router = APIRouter(prefix="/api", tags=["conversation-logs"])
logger = logging.getLogger(__name__)

@router.post("/log_conversation_summary", status_code=201)
async def log_conversation_summary(request: LogConversationRequest):
    """
    Creates conversation logs at the end of each call
    Tracks patient interactions and outcomes
    """
    try:
        # Create conversation log entry
        log_entry = {
            "id": f"conv_{int(datetime.now().timestamp())}",
            "timestamp": request.timestamp or datetime.now().isoformat(),
            "patient_name": request.patient_name,
            "conversation_summary": request.conversation_summary,
            "call_outcome": request.call_outcome,
            "duration_seconds": None,  # Could be calculated if start/end times provided
            "interaction_type": determine_interaction_type(request.conversation_summary),
            "success_metrics": extract_success_metrics(request.conversation_summary, request.call_outcome),
            "topics_discussed": extract_topics(request.conversation_summary),
            "next_actions": extract_next_actions(request.call_outcome),
            "patient_satisfaction": estimate_satisfaction(request.conversation_summary, request.call_outcome),
            "created_by": "ai_assistant",
            "metadata": {
                "summary_length": len(request.conversation_summary),
                "outcome_category": categorize_outcome(request.call_outcome)
            }
        }
        # Save asynchronously to avoid blocking
        await asyncio.to_thread(save_conversation_log, log_entry)
        insights = await generate_conversation_insights(log_entry)
        return {
            "success": True,
            "message": "Conversation logged successfully",
            "log_id": log_entry["id"],
            "summary": {
                "patient_name": request.patient_name,
                "interaction_type": log_entry["interaction_type"],
                "outcome_category": log_entry["metadata"]["outcome_category"],
                "topics_count": len(log_entry["topics_discussed"]),
                "estimated_satisfaction": log_entry["patient_satisfaction"]
            },
            "insights": insights,
            "timestamp": log_entry["timestamp"]
        }
    except Exception:
        logger.error("Error logging conversation", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error logging conversation")

def determine_interaction_type(summary: str) -> str:
    """Determine the type of interaction based on summary content"""
    summary_lower = summary.lower()
    
    if any(word in summary_lower for word in ["book", "schedule", "appointment"]):
        return "appointment_booking"
    elif any(word in summary_lower for word in ["reschedule", "change", "move"]):
        return "appointment_rescheduling"
    elif any(word in summary_lower for word in ["cancel", "cancelled"]):
        return "appointment_cancellation"
    elif any(word in summary_lower for word in ["information", "question", "ask"]):
        return "information_inquiry"
    elif any(word in summary_lower for word in ["emergency", "urgent", "pain"]):
        return "emergency_inquiry"
    elif any(word in summary_lower for word in ["billing", "payment", "insurance"]):
        return "billing_inquiry"
    else:
        return "general_inquiry"

def extract_success_metrics(summary: str, outcome: str) -> Dict[str, Any]:
    """Extract success metrics from the conversation"""
    summary_lower = summary.lower()
    outcome_lower = outcome.lower()
    
    metrics = {
        "appointment_booked": "booked" in outcome_lower or "scheduled" in outcome_lower,
        "question_answered": "answered" in outcome_lower or "resolved" in outcome_lower,
        "issue_resolved": "resolved" in outcome_lower or "completed" in outcome_lower,
        "callback_required": "callback" in outcome_lower or "call back" in outcome_lower,
        "escalation_needed": "escalate" in outcome_lower or "transfer" in outcome_lower,
        "patient_satisfied": any(word in summary_lower for word in ["thank", "great", "excellent", "satisfied"])
    }
    
    return metrics

def extract_topics(summary: str) -> List[str]:
    """Extract main topics discussed in the conversation"""
    summary_lower = summary.lower()
    topics = []
    
    topic_keywords = {
        "appointment_scheduling": ["appointment", "book", "schedule", "available"],
        "pricing": ["cost", "price", "fee", "payment"],
        "services": ["service", "treatment", "procedure", "cleaning"],
        "insurance": ["insurance", "coverage", "plan"],
        "location": ["address", "location", "directions"],
        "hours": ["hours", "open", "closed", "time"],
        "emergency": ["emergency", "urgent", "pain"],
        "staff": ["doctor", "dentist", "staff"],
        "new_patient": ["new patient", "first time", "first visit"],
        "rescheduling": ["reschedule", "change", "move"]
    }
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in summary_lower for keyword in keywords):
            topics.append(topic)
    
    return topics

def extract_next_actions(outcome: str) -> List[str]:
    """Extract next actions from the call outcome"""
    outcome_lower = outcome.lower()
    actions = []
    
    if "callback" in outcome_lower:
        actions.append("Schedule callback")
    if "appointment" in outcome_lower and "booked" in outcome_lower:
        actions.append("Send appointment confirmation")
    if "form" in outcome_lower:
        actions.append("Send patient forms")
    if "follow up" in outcome_lower:
        actions.append("Schedule follow-up")
    if "escalate" in outcome_lower:
        actions.append("Escalate to staff")
    
    return actions

def categorize_outcome(outcome: str) -> str:
    """Categorize the call outcome"""
    outcome_lower = outcome.lower()
    
    if any(word in outcome_lower for word in ["success", "completed", "booked", "scheduled"]):
        return "successful"
    elif any(word in outcome_lower for word in ["callback", "follow up", "pending"]):
        return "pending_action"
    elif any(word in outcome_lower for word in ["cancelled", "declined", "refused"]):
        return "cancelled"
    elif any(word in outcome_lower for word in ["escalate", "transfer", "complex"]):
        return "escalated"
    else:
        return "unknown"

def estimate_satisfaction(summary: str, outcome: str) -> str:
    """Estimate patient satisfaction based on conversation content"""
    text = (summary + " " + outcome).lower()
    
    positive_indicators = ["thank", "great", "excellent", "satisfied", "helpful", "wonderful"]
    negative_indicators = ["frustrated", "upset", "angry", "disappointed", "confused", "problem"]
    
    positive_count = sum(1 for word in positive_indicators if word in text)
    negative_count = sum(1 for word in negative_indicators if word in text)
    
    if positive_count > negative_count and positive_count > 0:
        return "high"
    elif negative_count > positive_count and negative_count > 0:
        return "low"
    else:
        return "medium"

async def save_conversation_log(log_entry: Dict[str, Any]):
    """Save conversation log to file"""
    logs_file = Path(__file__).parent.parent / "conversation_logs.json"
    try:
        if logs_file.exists():
            with open(logs_file, 'r') as f:
                existing_logs = json.load(f)
        else:
            existing_logs = []
        existing_logs.append(log_entry)
        if len(existing_logs) > 1000:
            existing_logs = existing_logs[-1000:]
        with open(logs_file, 'w') as f:
            json.dump(existing_logs, f, indent=2)
    except Exception:
        logger.error("Failed to save conversation log", exc_info=True)

async def generate_conversation_insights(log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Generate insights from the conversation log"""
    try:
        insights = {
            "efficiency_score": calculate_efficiency_score(log_entry),
            "topics_coverage": len(log_entry["topics_discussed"]),
            "resolution_status": "resolved" if log_entry["success_metrics"]["issue_resolved"] else "pending",
            "satisfaction_level": log_entry["patient_satisfaction"],
            "follow_up_required": len(log_entry["next_actions"]) > 0,
            "complexity_level": determine_complexity(log_entry)
        }
        
        return insights
    except Exception:
        logger.error("Error generating conversation insights", exc_info=True)
        return {}

def calculate_efficiency_score(log_entry: Dict[str, Any]) -> float:
    """Calculate conversation efficiency score"""
    try:
        score = 0.0
        
        # Base score for issue resolution
        if log_entry["success_metrics"]["issue_resolved"]:
            score += 0.4
        
        # Score for successful appointment booking
        if log_entry["success_metrics"]["appointment_booked"]:
            score += 0.3
        
        # Score for answered questions
        if log_entry["success_metrics"]["question_answered"]:
            score += 0.2
        
        # Bonus for high satisfaction
        if log_entry["patient_satisfaction"] == "high":
            score += 0.1
        
        # Penalty for escalation needed
        if log_entry["success_metrics"]["escalation_needed"]:
            score -= 0.2
        
        return max(0.0, min(1.0, score))
        
    except:
        return 0.5

def determine_complexity(log_entry: Dict[str, Any]) -> str:
    """Determine conversation complexity level"""
    try:
        complexity_factors = 0
        
        # Multiple topics increase complexity
        if len(log_entry["topics_discussed"]) > 2:
            complexity_factors += 1
        
        # Escalation needed indicates complexity
        if log_entry["success_metrics"]["escalation_needed"]:
            complexity_factors += 2
        
        # Multiple next actions indicate complexity
        if len(log_entry["next_actions"]) > 2:
            complexity_factors += 1
        
        # Emergency nature increases complexity
        if "emergency" in log_entry["topics_discussed"]:
            complexity_factors += 1
        
        if complexity_factors >= 3:
            return "high"
        elif complexity_factors >= 1:
            return "medium"
        else:
            return "low"
            
    except:
        return "medium"

@router.get("/conversation_logs")
async def get_conversation_logs(
    patient_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    interaction_type: Optional[str] = None,
    limit: Optional[int] = 50
):
    """Get conversation logs with optional filtering"""
    try:
        logs_file = Path(__file__).parent.parent / "conversation_logs.json"
        
        if not logs_file.exists():
            return {
                "success": True,
                "conversation_logs": [],
                "total_logs": 0,
                "message": "No conversation logs found"
            }
        
        with open(logs_file, 'r') as f:
            all_logs = json.load(f)
        
        # Apply filters
        filtered_logs = all_logs
        
        if patient_name:
            filtered_logs = [log for log in filtered_logs 
                           if log.get("patient_name", "").lower() == patient_name.lower()]
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            filtered_logs = [log for log in filtered_logs 
                           if datetime.fromisoformat(log["timestamp"]) >= start_dt]
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            filtered_logs = [log for log in filtered_logs 
                           if datetime.fromisoformat(log["timestamp"]) <= end_dt]
        
        if interaction_type:
            filtered_logs = [log for log in filtered_logs 
                           if log.get("interaction_type") == interaction_type]
        
        # Sort by timestamp (most recent first)
        filtered_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Apply limit
        if limit:
            filtered_logs = filtered_logs[:limit]
        
        return {
            "success": True,
            "conversation_logs": filtered_logs,
            "total_logs": len(all_logs),
            "filtered_count": len(filtered_logs),
            "filters_applied": {
                "patient_name": patient_name,
                "start_date": start_date,
                "end_date": end_date,
                "interaction_type": interaction_type,
                "limit": limit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation logs: {str(e)}")

@router.get("/conversation_logs/analytics")
async def get_conversation_analytics():
    """Get analytics and insights from conversation logs"""
    try:
        logs_file = Path(__file__).parent.parent / "conversation_logs.json"
        
        if not logs_file.exists():
            return {
                "success": True,
                "analytics": {},
                "message": "No conversation logs available for analysis"
            }
        
        with open(logs_file, 'r') as f:
            all_logs = json.load(f)
        
        if not all_logs:
            return {
                "success": True,
                "analytics": {},
                "message": "No conversation logs available for analysis"
            }
        
        # Calculate analytics
        total_conversations = len(all_logs)
        
        # Interaction type distribution
        interaction_types = {}
        outcome_categories = {}
        satisfaction_levels = {}
        topics_frequency = {}
        
        successful_conversations = 0
        total_efficiency = 0
        
        for log in all_logs:
            # Interaction types
            interaction_type = log.get("interaction_type", "unknown")
            interaction_types[interaction_type] = interaction_types.get(interaction_type, 0) + 1
            
            # Outcome categories
            outcome_category = log.get("metadata", {}).get("outcome_category", "unknown")
            outcome_categories[outcome_category] = outcome_categories.get(outcome_category, 0) + 1
            
            # Satisfaction levels
            satisfaction = log.get("patient_satisfaction", "unknown")
            satisfaction_levels[satisfaction] = satisfaction_levels.get(satisfaction, 0) + 1
            
            # Topics frequency
            for topic in log.get("topics_discussed", []):
                topics_frequency[topic] = topics_frequency.get(topic, 0) + 1
            
            # Success rate calculation
            if log.get("success_metrics", {}).get("issue_resolved", False):
                successful_conversations += 1
        
        # Calculate success rate
        success_rate = successful_conversations / total_conversations if total_conversations > 0 else 0
        
        analytics = {
            "total_conversations": total_conversations,
            "success_rate": round(success_rate, 2),
            "interaction_type_distribution": interaction_types,
            "outcome_category_distribution": outcome_categories,
            "satisfaction_distribution": satisfaction_levels,
            "most_discussed_topics": dict(sorted(topics_frequency.items(), key=lambda x: x[1], reverse=True)[:10]),
            "high_satisfaction_rate": satisfaction_levels.get("high", 0) / total_conversations if total_conversations > 0 else 0
        }
        
        return {
            "success": True,
            "analytics": analytics,
            "period": "all_time",
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating conversation analytics: {str(e)}")

@router.delete("/conversation_logs/cleanup")
async def cleanup_old_logs(days_to_keep: int = 30):
    """Clean up old conversation logs"""
    try:
        logs_file = Path(__file__).parent.parent / "conversation_logs.json"
        
        if not logs_file.exists():
            return {
                "success": True,
                "message": "No logs file found",
                "logs_removed": 0
            }
        
        with open(logs_file, 'r') as f:
            all_logs = json.load(f)
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Filter logs to keep
        logs_to_keep = [
            log for log in all_logs
            if datetime.fromisoformat(log["timestamp"]) > cutoff_date
        ]
        
        logs_removed = len(all_logs) - len(logs_to_keep)
        
        # Save filtered logs
        with open(logs_file, 'w') as f:
            json.dump(logs_to_keep, f, indent=2)
        
        return {
            "success": True,
            "message": f"Cleanup completed",
            "logs_removed": logs_removed,
            "logs_remaining": len(logs_to_keep),
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up logs: {str(e)}")
