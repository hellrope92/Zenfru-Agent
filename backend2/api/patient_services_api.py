"""
Patient services API endpoints
Handles patient forms, callback requests, FAQ queries, and conversation logging
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, HTTPException

# Import shared models
from .models import CallbackRequest, SendFormRequest, FAQRequest, ConversationSummaryRequest

router = APIRouter(prefix="/api", tags=["patient-services"])

def search_knowledge_base(query: str, knowledge_base: Dict) -> tuple[str, str]:
    """Search knowledge base for relevant information"""
    query_lower = query.lower()
    clinic_info = knowledge_base.get("clinic_info", {})
    
    # Address/Location queries
    if any(word in query_lower for word in ["address", "location", "where", "find"]):
        return clinic_info.get("address", "Address not available"), "clinic_address"
    
    # Parking queries
    if any(word in query_lower for word in ["parking", "park"]):
        return clinic_info.get("parking_info", "Parking information not available"), "parking_info"
    
    # Hours queries
    if any(word in query_lower for word in ["hours", "open", "closed", "time"]):
        hours = clinic_info.get("office_hours_detailed", {})
        hours_text = "\n".join([f"{day}: {time}" for day, time in hours.items()])
        return f"Our office hours are:\n{hours_text}", "office_hours"
    
    # Services queries
    if any(word in query_lower for word in ["service", "treatment", "procedure", "do you do"]):
        services = clinic_info.get("services_offered_summary", [])
        services_text = ", ".join(services)
        return f"We offer the following services: {services_text}", "services"
    
    # Pricing queries
    if any(word in query_lower for word in ["cost", "price", "fee", "how much"]):
        pricing = clinic_info.get("service_pricing", {})
        pricing_text = "\n".join([f"{service}: {price}" for service, price in pricing.items()])
        return f"Here are some of our prices:\n{pricing_text}", "pricing"
    
    # Doctor queries
    if any(word in query_lower for word in ["doctor", "dentist", "who", "staff"]):
        doctors = clinic_info.get("dentist_team", [])
        doctor_info = []
        for doc in doctors:
            doctor_info.append(f"{doc['name']} - {doc['working_days_hours']}")
        return "\n".join(doctor_info), "doctor_info"
    
    # Default response
    return "I don't have specific information about that. Please call our office for more details.", "general"

async def send_new_patient_form(request: SendFormRequest, knowledge_base: Dict):
    """Send new patient forms to the provided phone number"""
    
    form_url = knowledge_base.get("intake_form_url", "https://forms.brightsmile-dental.com/new-patient")
    
    print(f"📱 SEND_NEW_PATIENT_FORM:")
    print(f"   Phone: {request.contact_number}")
    print(f"   Form URL: {form_url}")
    print(f"   ✅ [SIMULATION] SMS would be sent!")
    
    return {
        "success": True,
        "message": f"[SIMULATION] New patient forms would be sent to {request.contact_number}",
        "form_url": form_url
    }

async def log_callback_request(request: CallbackRequest, callback_requests: List):
    """Log a callback request for staff follow-up"""
    
    print(f"📞 LOG_CALLBACK_REQUEST:")
    print(f"   Name: {request.name}")
    print(f"   Phone: {request.contact_number}")
    print(f"   Preferred Time: {request.preferred_callback_time}")
    
    # Generate callback ID
    callback_id = f"CB-{uuid.uuid4().hex[:8].upper()}"
    
    # Store in runtime storage
    callback_record = {
        "callback_id": callback_id,
        "name": request.name,
        "contact_number": request.contact_number,
        "preferred_callback_time": request.preferred_callback_time,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    callback_requests.append(callback_record)
    
    print(f"   ✅ Callback request logged successfully!")
    print(f"   📋 Callback ID: {callback_id}")
    
    return {
        "success": True,
        "callback_id": callback_id,
        "message": f"Callback request logged for {request.name}"
    }

async def answer_faq_query(request: FAQRequest, knowledge_base: Dict):
    """Answer frequently asked questions using knowledge base"""
    
    print(f"❓ ANSWER_FAQ_QUERY:")
    print(f"   Query: {request.query}")
    
    # Search knowledge base
    answer, source = search_knowledge_base(request.query, knowledge_base)
    
    print(f"   💡 Answer: {answer}")
    print(f"   📚 Source: {source}")
    
    return {
        "success": True,
        "query": request.query,
        "answer": answer,
        "source": source
    }

async def log_conversation_summary(request: ConversationSummaryRequest, conversation_logs: List):
    """Log a comprehensive summary of the conversation"""
    
    print(f"📝 LOG_CONVERSATION_SUMMARY:")
    if request.summary:
        print(f"   Summary: {request.summary}")
    print(f"   Patient: {request.patient_name or 'Unknown'}")
    print(f"   Primary Intent: {request.primary_intent}")
    print(f"   Outcome: {request.outcome}")
    if request.appointment_details:
        print(f"   Appointment Details: {request.appointment_details}")
    if request.call_duration:
        print(f"   Call Duration: {request.call_duration} seconds")
    if request.additional_notes:
        print(f"   Notes: {request.additional_notes}")
    
    # Generate summary ID
    summary_id = f"CONV-{uuid.uuid4().hex[:8].upper()}"
    
    # Store in runtime storage
    conversation_record = {
        "summary_id": summary_id,
        "summary": request.summary,
        "patient_name": request.patient_name,
        "primary_intent": request.primary_intent,
        "appointment_details": request.appointment_details,
        "outcome": request.outcome,
        "call_duration": request.call_duration,
        "additional_notes": request.additional_notes,
        "logged_at": datetime.now().isoformat()
    }
    
    conversation_logs.append(conversation_record)
    
    print(f"   ✅ Conversation summary logged successfully!")
    print(f"   📋 Summary ID: {summary_id}")
    
    return {
        "success": True,
        "summary_id": summary_id,
        "message": "Conversation summary logged successfully"
    }
