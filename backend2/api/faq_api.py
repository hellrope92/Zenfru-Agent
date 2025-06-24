"""
FAQ Query API endpoint
Queries the knowledge base for FAQ responses
Used for general clinic information questions
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pathlib import Path

from api.models import AnswerFAQRequest

router = APIRouter(prefix="/api", tags=["faq"])

def load_knowledge_base() -> Dict[str, Any]:
    """Load knowledge base from file"""
    knowledge_base_file = Path(__file__).parent.parent.parent / "knowledge_base.json"
    try:
        with open(knowledge_base_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        return {}

@router.post("/answer_faq_query")
async def answer_faq_query(request: AnswerFAQRequest):
    """
    Queries the knowledge base for FAQ responses
    Used for general clinic information questions
    """
    try:
        knowledge_base = load_knowledge_base()
        
        if not knowledge_base:
            return {
                "success": False,
                "message": "Knowledge base not available",
                "query": request.query,
                "answer": None
            }
        
        # Search for relevant information
        answer, category = search_knowledge_base(request.query, knowledge_base)
        
        if answer:
            # Log the FAQ query for analytics
            await log_faq_query(request.query, category, answer)
            
            return {
                "success": True,
                "query": request.query,
                "answer": answer,
                "category": category,
                "confidence": calculate_confidence(request.query, answer),
                "timestamp": datetime.now().isoformat(),
                "source": "knowledge_base"
            }
        else:
            return {
                "success": False,
                "message": "No relevant information found",
                "query": request.query,
                "answer": None,
                "suggestions": generate_suggestions(request.query, knowledge_base)
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing FAQ query: {str(e)}")

def search_knowledge_base(query: str, knowledge_base: Dict) -> tuple[Optional[str], Optional[str]]:
    """Search knowledge base for relevant information"""
    query_lower = query.lower()
    clinic_info = knowledge_base.get("clinic_info", {})
    
    # Address/Location queries
    if any(word in query_lower for word in ["address", "location", "where", "find", "directions"]):
        address = clinic_info.get("address")
        if address:
            response = f"Our clinic is located at: {address}"
            parking_info = clinic_info.get("parking_info")
            if parking_info:
                response += f"\n\nParking: {parking_info}"
            return response, "clinic_address"
    
    # Parking queries
    if any(word in query_lower for word in ["parking", "park"]):
        parking_info = clinic_info.get("parking_info")
        if parking_info:
            return parking_info, "parking_info"
    
    # Hours/Schedule queries
    if any(word in query_lower for word in ["hours", "open", "closed", "time", "schedule", "when"]):
        hours = clinic_info.get("office_hours_detailed", {})
        if hours:
            hours_text = "Our office hours are:\n" + "\n".join([f"{day}: {time}" for day, time in hours.items()])
            return hours_text, "office_hours"
    
    # Services queries
    if any(word in query_lower for word in ["service", "treatment", "procedure", "do you do", "offer"]):
        services = clinic_info.get("services_offered_summary", [])
        if services:
            services_text = "We offer the following services:\n• " + "\n• ".join(services)
            return services_text, "services"
    
    # Pricing queries
    if any(word in query_lower for word in ["cost", "price", "fee", "how much", "payment"]):
        pricing = clinic_info.get("service_pricing", {})
        if pricing:
            pricing_text = "Here are some of our prices:\n"
            for service, price in pricing.items():
                pricing_text += f"• {service}: {price}\n"
            pricing_text += "\nPrices may vary based on individual needs. Please contact us for a personalized quote."
            return pricing_text, "pricing"
    
    # Insurance queries
    if any(word in query_lower for word in ["insurance", "coverage", "accept", "plan"]):
        insurance_info = clinic_info.get("insurance_info", {})
        accepted_plans = insurance_info.get("accepted_plans", [])
        if accepted_plans:
            insurance_text = "We accept the following insurance plans:\n• " + "\n• ".join(accepted_plans)
            insurance_text += "\n\nPlease contact us to verify your specific coverage."
            return insurance_text, "insurance"
    
    # Doctor/Staff queries
    if any(word in query_lower for word in ["doctor", "dentist", "who", "staff", "team"]):
        doctors = clinic_info.get("dentist_team", [])
        if doctors:
            doctor_info = "Our dental team includes:\n"
            for doc in doctors:
                name = doc.get("name", "Unknown")
                speciality = doc.get("speciality", "General Dentistry")
                doctor_info += f"• Dr. {name} - {speciality}\n"
            return doctor_info, "staff_info"
    
    # Contact information queries
    if any(word in query_lower for word in ["phone", "call", "contact", "number"]):
        phone = clinic_info.get("phone")
        email = clinic_info.get("email")
        if phone or email:
            contact_text = "You can contact us:\n"
            if phone:
                contact_text += f"Phone: {phone}\n"
            if email:
                contact_text += f"Email: {email}\n"
            return contact_text, "contact_info"
    
    # Emergency queries
    if any(word in query_lower for word in ["emergency", "urgent", "after hours", "weekend"]):
        emergency_info = clinic_info.get("emergency_contact")
        if emergency_info:
            return emergency_info, "emergency_info"
        else:
            return "For dental emergencies, please call our main number. Emergency services may be available.", "emergency_info"
    
    # Appointment booking queries
    if any(word in query_lower for word in ["appointment", "book", "schedule", "availability"]):
        return "To book an appointment, please call us or use our online booking system. We'll help you find a convenient time.", "appointment_booking"
    
    # New patient queries
    if any(word in query_lower for word in ["new patient", "first visit", "first time"]):
        return "Welcome! New patients are always welcome. Please arrive 15 minutes early for your first visit to complete paperwork. We'll send you forms to fill out beforehand.", "new_patient_info"
    
    # Payment method queries
    if any(word in query_lower for word in ["payment", "credit card", "cash", "financing"]):
        payment_info = clinic_info.get("payment_methods", [])
        if payment_info:
            payment_text = "We accept the following payment methods:\n• " + "\n• ".join(payment_info)
            return payment_text, "payment_methods"
    
    return None, None

def calculate_confidence(query: str, answer: str) -> float:
    """Calculate confidence score for the answer"""
    if not answer:
        return 0.0
    
    # Simple confidence calculation based on query length and answer relevance
    query_words = set(query.lower().split())
    answer_words = set(answer.lower().split())
    
    # Count matching words
    matching_words = len(query_words.intersection(answer_words))
    total_query_words = len(query_words)
    
    if total_query_words == 0:
        return 0.0
    
    confidence = min(matching_words / total_query_words, 1.0)
    
    # Boost confidence for exact matches of key terms
    key_terms = ["address", "hours", "price", "insurance", "doctor", "phone"]
    for term in key_terms:
        if term in query.lower() and term in answer.lower():
            confidence = min(confidence + 0.2, 1.0)
    
    return round(confidence, 2)

def generate_suggestions(query: str, knowledge_base: Dict) -> List[str]:
    """Generate alternative query suggestions"""
    suggestions = []
    
    query_lower = query.lower()
    
    # Common alternative phrasings
    if "location" in query_lower or "where" in query_lower:
        suggestions.extend(["address", "directions", "parking"])
    
    if "time" in query_lower or "when" in query_lower:
        suggestions.extend(["office hours", "schedule", "availability"])
    
    if "cost" in query_lower or "price" in query_lower:
        suggestions.extend(["pricing", "fees", "insurance", "payment methods"])
    
    if "doctor" in query_lower:
        suggestions.extend(["staff", "dentist", "team"])
    
    # General suggestions if no specific matches
    if not suggestions:
        suggestions = [
            "office hours",
            "address and directions",
            "services offered", 
            "pricing information",
            "insurance accepted",
            "contact information"
        ]
    
    return suggestions[:5]  # Limit to 5 suggestions

async def log_faq_query(query: str, category: str, answer: str):
    """Log FAQ queries for analytics"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "category": category,
            "answer_provided": bool(answer),
            "answer_length": len(answer) if answer else 0
        }
        
        # Save to log file
        log_file = Path(__file__).parent.parent / "faq_logs.json"
        
        if log_file.exists():
            with open(log_file, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(log_entry)
        
        # Keep only last 1000 entries
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
            
    except Exception as e:
        print(f"Error logging FAQ query: {e}")

@router.get("/faq/categories")
async def get_faq_categories():
    """Get available FAQ categories"""
    try:
        knowledge_base = load_knowledge_base()
        clinic_info = knowledge_base.get("clinic_info", {})
        
        categories = [
            {
                "category": "clinic_address",
                "title": "Location & Directions",
                "description": "Find our clinic location and parking information"
            },
            {
                "category": "office_hours",
                "title": "Office Hours",
                "description": "Our operating hours and schedule"
            },
            {
                "category": "services",
                "title": "Services Offered",
                "description": "Dental treatments and procedures we provide"
            },
            {
                "category": "pricing",
                "title": "Pricing & Fees",
                "description": "Cost information for our services"
            },
            {
                "category": "insurance",
                "title": "Insurance",
                "description": "Accepted insurance plans and coverage"
            },
            {
                "category": "staff_info",
                "title": "Our Team",
                "description": "Meet our dental professionals"
            },
            {
                "category": "contact_info",
                "title": "Contact Information",
                "description": "Phone, email, and contact details"
            },
            {
                "category": "emergency_info",
                "title": "Emergency Care",
                "description": "After-hours and emergency services"
            },
            {
                "category": "new_patient_info",
                "title": "New Patient Information",
                "description": "Information for first-time visitors"
            },
            {
                "category": "payment_methods",
                "title": "Payment Options",
                "description": "Accepted payment methods and financing"
            }
        ]
        
        return {
            "success": True,
            "categories": categories,
            "total_categories": len(categories)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting FAQ categories: {str(e)}")

@router.get("/faq/popular")
async def get_popular_queries():
    """Get most popular FAQ queries"""
    try:
        log_file = Path(__file__).parent.parent / "faq_logs.json"
        
        if not log_file.exists():
            return {
                "success": True,
                "popular_queries": [],
                "message": "No query history available"
            }
        
        with open(log_file, 'r') as f:
            logs = json.load(f)
        
        # Count query categories
        category_counts = {}
        for log in logs:
            category = log.get("category", "unknown")
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Sort by popularity
        popular_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "success": True,
            "popular_queries": [
                {"category": cat, "count": count} 
                for cat, count in popular_categories[:10]
            ],
            "total_queries_logged": len(logs)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting popular queries: {str(e)}")
