"""
New Patient Form API endpoint
Sends new patient forms to a phone number
Used in the new patient onboarding process
"""

import requests
from datetime import datetime
from typing import Dict, Optional, Any
from fastapi import APIRouter, HTTPException
import logging
from api.models import SendNewPatientFormRequest

router = APIRouter(prefix="/api", tags=["patient-forms"])

@router.post("/send_new_patient_form")
async def send_new_patient_form(request: SendNewPatientFormRequest):
    """
    Sends new patient forms to a phone number
    Used in the new patient onboarding process
    """
    try:
        # Validate phone number format
        phone_number = request.phone_number.strip()
        if not phone_number:
            raise HTTPException(status_code=400, detail="Phone number is required")
        
        # Format phone number (remove any formatting characters)
        formatted_phone = ''.join(filter(str.isdigit, phone_number))
        
        if len(formatted_phone) != 10 and len(formatted_phone) != 11:
            raise HTTPException(status_code=400, detail="Invalid phone number format")
        
        # Create the patient form link/message
        form_data = {
            "phone_number": formatted_phone,
            "form_type": "new_patient_intake",
            "clinic_name": "BrightSmile Dental Clinic",
            "form_link": generate_patient_form_link(formatted_phone),
            "instructions": "Please complete this form before your appointment",
            "timestamp": datetime.now().isoformat()
        }
        
        # Send the form (this would integrate with SMS service)
        success = await send_form_via_sms(form_data)
        
        if success:
            # Log the form send event
            await log_form_sent_event(form_data)
            
            return {
                "success": True,
                "message": "New patient form sent successfully",
                "phone_number": formatted_phone,
                "form_link": form_data["form_link"],
                "sent_at": form_data["timestamp"]
            }
        else:
            return {
                "success": False,
                "message": "Failed to send new patient form",
                "phone_number": formatted_phone,
                "error": "SMS delivery failed"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending patient form: {str(e)}")

def generate_patient_form_link(phone_number: str) -> str:
    """Generate a unique form link for the patient"""
    # This would generate a secure, unique link for the patient
    # For now, we'll create a placeholder link
    form_id = f"form_{phone_number}_{int(datetime.now().timestamp())}"
    return f"https://forms.brightsmile-dental.com/new-patient/{form_id}"

async def send_form_via_sms(form_data: Dict[str, Any]) -> bool:
    """Send the form link via SMS"""
    try:
        # This would integrate with an SMS service like Twilio, AWS SNS, etc.
        # For now, we'll simulate the SMS sending
        
        message = f"""
Welcome to BrightSmile Dental Clinic!

Please complete your new patient intake form before your appointment:
{form_data['form_link']}

{form_data['instructions']}

If you have any questions, please call us at (555) 123-4567.
        """.strip()
        
        # Simulate SMS sending (replace with actual SMS service)    
    logging.info(f"SMS would be sent to {form_data['phone_number']}: {message}")
        
        # For demo purposes, always return True
        # In production, this would return the actual SMS delivery status
        return True
        
    except Exception as e:    
    logging.error(f"Error sending SMS: {e}")
        return False

async def log_form_sent_event(form_data: Dict[str, Any]):
    """Log the form sending event for tracking"""
    try:
        # This would log to a database or logging service
        log_entry = {
            "event_type": "new_patient_form_sent",
            "phone_number": form_data["phone_number"],
            "form_link": form_data["form_link"],
            "timestamp": form_data["timestamp"],
            "status": "sent"
        }
        
        # For now, just print the log entry
        print(f"Form sent log: {log_entry}")
        
        # In production, you would save this to a database
        
    except Exception as e:
        print(f"Error logging form sent event: {e}")

@router.get("/new_patient_form_status/{phone_number}")
async def get_form_status(phone_number: str):
    """Check the status of a sent form"""
    try:
        formatted_phone = ''.join(filter(str.isdigit, phone_number))
        
        # This would check the actual form completion status
        # For now, return a placeholder response
        return {
            "success": True,
            "phone_number": formatted_phone,
            "form_status": "sent",
            "completion_status": "pending",
            "sent_at": "2024-01-01T12:00:00",
            "completed_at": None,
            "message": "Form sent, awaiting completion"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking form status: {str(e)}")

@router.post("/resend_new_patient_form")
async def resend_new_patient_form(request: SendNewPatientFormRequest):
    """Resend a new patient form if the original was not received"""
    try:
        # Add a note that this is a resend
        result = await send_new_patient_form(request)
        
        if result["success"]:
            result["message"] = "New patient form resent successfully"
            result["resend"] = True
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resending patient form: {str(e)}")

@router.get("/patient_forms/stats")
async def get_form_stats():
    """Get statistics about patient forms"""
    try:
        # This would return actual statistics from a database
        # For now, return placeholder data
        return {
            "success": True,
            "stats": {
                "total_forms_sent": 0,
                "completed_forms": 0,
                "pending_forms": 0,
                "completion_rate": 0.0,
                "average_completion_time_hours": 0
            },
            "recent_activity": []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting form stats: {str(e)}")
