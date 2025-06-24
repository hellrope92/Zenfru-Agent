"""
Callback Request API endpoint
Records callback requests when clinic is closed or tools fail
Parameters: name, contact, reason, preferred_callback_time
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pathlib import Path

from api.models import LogCallbackRequest

router = APIRouter(prefix="/api", tags=["callbacks"])

# In-memory storage for demo (in production, use a database)
callback_requests = []

@router.post("/log_callback_request")
async def log_callback_request(request: LogCallbackRequest):
    """
    Records callback requests when clinic is closed or tools fail
    Parameters: name, contact, reason, preferred_callback_time
    """
    try:
        # Create callback request entry
        callback_entry = {
            "id": f"cb_{int(datetime.now().timestamp())}_{len(callback_requests)}",
            "patient_name": request.name,
            "contact_info": request.contact,
            "reason": request.reason,
            "preferred_callback_time": request.preferred_callback_time,
            "request_timestamp": datetime.now().isoformat(),
            "status": "pending",
            "priority": determine_priority(request.reason),
            "callback_attempts": [],
            "resolution": None,
            "resolved_at": None,
            "created_by": "ai_assistant",
            "notes": []
        }
        
        # Store the callback request
        callback_requests.append(callback_entry)
        
        # Also save to file for persistence
        await save_callback_to_file(callback_entry)
        
        # Determine urgency and response time
        urgency_info = get_urgency_info(request.reason)
        
        return {
            "success": True,
            "message": "Callback request logged successfully",
            "callback_id": callback_entry["id"],
            "request_details": {
                "patient_name": request.name,
                "contact": request.contact,
                "reason": request.reason,
                "preferred_time": request.preferred_callback_time,
                "priority": callback_entry["priority"],
                "urgency": urgency_info["level"],
                "expected_response_time": urgency_info["response_time"]
            },
            "next_steps": urgency_info["next_steps"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error logging callback request: {str(e)}")

def determine_priority(reason: str) -> str:
    """Determine priority level based on the reason for callback"""
    reason_lower = reason.lower()
    
    # High priority keywords
    high_priority_keywords = [
        "emergency", "urgent", "pain", "bleeding", "swelling", "infection",
        "broken tooth", "lost filling", "accident", "trauma"
    ]
    
    # Medium priority keywords
    medium_priority_keywords = [
        "reschedule", "cancel", "change appointment", "insurance",
        "billing", "payment", "prescription", "medication"
    ]
    
    if any(keyword in reason_lower for keyword in high_priority_keywords):
        return "high"
    elif any(keyword in reason_lower for keyword in medium_priority_keywords):
        return "medium"
    else:
        return "low"

def get_urgency_info(reason: str) -> Dict[str, Any]:
    """Get urgency information and response guidelines"""
    reason_lower = reason.lower()
    
    if "emergency" in reason_lower or "pain" in reason_lower:
        return {
            "level": "urgent",
            "response_time": "within 30 minutes",
            "next_steps": [
                "Immediate callback required",
                "Consider emergency appointment",
                "Provide pain management guidance if needed"
            ]
        }
    elif any(word in reason_lower for word in ["reschedule", "cancel", "insurance"]):
        return {
            "level": "normal",
            "response_time": "within 2 hours during business hours",
            "next_steps": [
                "Schedule callback during business hours",
                "Prepare relevant information before calling"
            ]
        }
    else:
        return {
            "level": "low",
            "response_time": "within 24 hours",
            "next_steps": [
                "Schedule callback at convenient time",
                "Can be handled by support staff"
            ]
        }

async def save_callback_to_file(callback_entry: Dict[str, Any]):
    """Save callback request to file for persistence"""
    try:
        callbacks_file = Path(__file__).parent.parent / "callback_requests.json"
        
        # Load existing callbacks
        if callbacks_file.exists():
            with open(callbacks_file, 'r') as f:
                existing_callbacks = json.load(f)
        else:
            existing_callbacks = []
        
        # Add new callback
        existing_callbacks.append(callback_entry)
        
        # Save back to file
        with open(callbacks_file, 'w') as f:
            json.dump(existing_callbacks, f, indent=2)
            
    except Exception as e:
        print(f"Error saving callback to file: {e}")

@router.get("/callback_requests")
async def get_callback_requests(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: Optional[int] = 50
):
    """Get all callback requests with optional filtering"""
    try:
        # Load from file to get persistent data
        callbacks_file = Path(__file__).parent.parent / "callback_requests.json"
        all_callbacks = callback_requests.copy()
        
        if callbacks_file.exists():
            with open(callbacks_file, 'r') as f:
                file_callbacks = json.load(f)
                # Merge with in-memory callbacks (avoid duplicates)
                existing_ids = {cb["id"] for cb in all_callbacks}
                for cb in file_callbacks:
                    if cb["id"] not in existing_ids:
                        all_callbacks.append(cb)
        
        # Apply filters
        filtered_callbacks = all_callbacks
        
        if status:
            filtered_callbacks = [cb for cb in filtered_callbacks if cb["status"] == status]
        
        if priority:
            filtered_callbacks = [cb for cb in filtered_callbacks if cb["priority"] == priority]
        
        # Sort by timestamp (most recent first)
        filtered_callbacks.sort(key=lambda x: x["request_timestamp"], reverse=True)
        
        # Apply limit
        if limit:
            filtered_callbacks = filtered_callbacks[:limit]
        
        return {
            "success": True,
            "total_callbacks": len(all_callbacks),
            "filtered_count": len(filtered_callbacks),
            "filters_applied": {
                "status": status,
                "priority": priority,
                "limit": limit
            },
            "callback_requests": filtered_callbacks
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving callback requests: {str(e)}")

@router.get("/callback_requests/{callback_id}")
async def get_callback_request(callback_id: str):
    """Get a specific callback request by ID"""
    try:
        # Search in memory first
        for callback in callback_requests:
            if callback["id"] == callback_id:
                return {
                    "success": True,
                    "callback_request": callback
                }
        
        # Search in file
        callbacks_file = Path(__file__).parent.parent / "callback_requests.json"
        if callbacks_file.exists():
            with open(callbacks_file, 'r') as f:
                file_callbacks = json.load(f)
                for callback in file_callbacks:
                    if callback["id"] == callback_id:
                        return {
                            "success": True,
                            "callback_request": callback
                        }
        
        return {
            "success": False,
            "message": f"Callback request with ID {callback_id} not found"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving callback request: {str(e)}")

@router.put("/callback_requests/{callback_id}/status")
async def update_callback_status(callback_id: str, status: str, notes: Optional[str] = None):
    """Update the status of a callback request"""
    try:
        valid_statuses = ["pending", "in_progress", "completed", "cancelled"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        # Update in memory
        updated = False
        for callback in callback_requests:
            if callback["id"] == callback_id:
                callback["status"] = status
                if status == "completed":
                    callback["resolved_at"] = datetime.now().isoformat()
                if notes:
                    callback["notes"].append({
                        "timestamp": datetime.now().isoformat(),
                        "note": notes,
                        "added_by": "staff"
                    })
                updated = True
                break
        
        # Update in file
        callbacks_file = Path(__file__).parent.parent / "callback_requests.json"
        if callbacks_file.exists():
            with open(callbacks_file, 'r') as f:
                file_callbacks = json.load(f)
            
            for callback in file_callbacks:
                if callback["id"] == callback_id:
                    callback["status"] = status
                    if status == "completed":
                        callback["resolved_at"] = datetime.now().isoformat()
                    if notes:
                        if "notes" not in callback:
                            callback["notes"] = []
                        callback["notes"].append({
                            "timestamp": datetime.now().isoformat(),
                            "note": notes,
                            "added_by": "staff"
                        })
                    updated = True
                    break
            
            if updated:
                with open(callbacks_file, 'w') as f:
                    json.dump(file_callbacks, f, indent=2)
        
        if updated:
            return {
                "success": True,
                "message": f"Callback request {callback_id} status updated to {status}",
                "callback_id": callback_id,
                "new_status": status
            }
        else:
            return {
                "success": False,
                "message": f"Callback request {callback_id} not found"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating callback status: {str(e)}")

@router.get("/callback_requests/stats/summary")
async def get_callback_stats():
    """Get summary statistics for callback requests"""
    try:
        # Load all callbacks
        all_callbacks = callback_requests.copy()
        callbacks_file = Path(__file__).parent.parent / "callback_requests.json"
        
        if callbacks_file.exists():
            with open(callbacks_file, 'r') as f:
                file_callbacks = json.load(f)
                existing_ids = {cb["id"] for cb in all_callbacks}
                for cb in file_callbacks:
                    if cb["id"] not in existing_ids:
                        all_callbacks.append(cb)
        
        # Calculate statistics
        total_callbacks = len(all_callbacks)
        status_counts = {}
        priority_counts = {}
        
        for callback in all_callbacks:
            status = callback["status"]
            priority = callback["priority"]
            
            status_counts[status] = status_counts.get(status, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        # Calculate average response time for completed callbacks
        completed_callbacks = [cb for cb in all_callbacks if cb["status"] == "completed" and cb.get("resolved_at")]
        avg_response_time = None
        
        if completed_callbacks:
            total_time = 0
            for cb in completed_callbacks:
                request_time = datetime.fromisoformat(cb["request_timestamp"])
                resolved_time = datetime.fromisoformat(cb["resolved_at"])
                total_time += (resolved_time - request_time).total_seconds()
            
            avg_response_time = total_time / len(completed_callbacks) / 3600  # in hours
        
        return {
            "success": True,
            "statistics": {
                "total_callbacks": total_callbacks,
                "status_breakdown": status_counts,
                "priority_breakdown": priority_counts,
                "completion_rate": len(completed_callbacks) / total_callbacks if total_callbacks > 0 else 0,
                "average_response_time_hours": round(avg_response_time, 2) if avg_response_time else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting callback statistics: {str(e)}")
