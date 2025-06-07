"""
Simple test script for the dental clinic API
Run this to test all endpoints
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api"

def test_api():
    print("🧪 Testing BrightSmile Dental AI Assistant API")
    print("=" * 50)
    
    # Test 1: Health Check
    print("\n1. 🏥 Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Get Current Day
    print("\n2. 🗓️ Get Current Day")
    try:
        response = requests.get(f"{BASE_URL}/get_current_day")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Check Available Slots
    print("\n3. 🔍 Check Available Slots")
    try:
        data = {
            "day": "Monday",
            "service_details": "routine cleaning and check-up"
        }
        response = requests.post(f"{BASE_URL}/check_available_slots", json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: Book Patient Appointment
    print("\n4. 📅 Book Patient Appointment")
    try:
        data = {
            "name": "John Smith",
            "contact": "5551234567",
            "day": "Monday",
            "time": "10:00 AM",
            "is_new_patient": True,
            "service_booked": "routine cleaning and check-up",
            "doctor_for_appointment": "Dr. Hanna"
        }
        response = requests.post(f"{BASE_URL}/book_patient_appointment", json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 5: Answer FAQ
    print("\n5. ❓ Answer FAQ")
    try:
        data = {
            "query": "What are your office hours?"
        }
        response = requests.post(f"{BASE_URL}/answer_faq_query", json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
      # Test 6: Log Callback Request
    print("\n6. 📞 Log Callback Request")
    try:
        data = {
            "name": "Jane Doe",
            "contact_number": "5559876543",
            "preferred_callback_time": "Tomorrow morning"
        }
        response = requests.post(f"{BASE_URL}/log_callback_request", json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 7: Send New Patient Form
    print("\n7. 📱 Send New Patient Form")
    try:
        data = {
            "contact_number": "5551234567"
        }
        response = requests.post(f"{BASE_URL}/send_new_patient_form", json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 8: Log Conversation Summary
    print("\n8. 📝 Log Conversation Summary")
    try:
        data = {
            "patient_name": "John Smith",
            "primary_intent": "book new appointment",
            "appointment_details": {
                "service": "cleaning",
                "day": "Monday",
                "time": "10:00 AM"
            },
            "outcome": "Appointment confirmed",
            "call_duration": 180,
            "additional_notes": "New patient, sent forms"
        }
        response = requests.post(f"{BASE_URL}/log_conversation_summary", json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 9: Reschedule Appointment
    print("\n9. 🔄 Reschedule Appointment")
    try:
        data = {
            "name": "John Smith",
            "dob": "1990-01-01",
            "reason": "Conflict with work meeting",
            "new_slot": "Tuesday 2:00 PM"
        }
        response = requests.post(f"{BASE_URL}/reschedule_patient_appointment", json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 All tests completed!")
    
    # Show debug data
    print("\n📊 Debug Data:")
    try:
        appointments = requests.get(f"{BASE_URL}/debug/appointments").json()
        callbacks = requests.get(f"{BASE_URL}/debug/callbacks").json()
        conversations = requests.get(f"{BASE_URL}/debug/conversations").json()
        
        print(f"   Appointments: {appointments['total']}")
        print(f"   Callbacks: {callbacks['total']}")
        print(f"   Conversations: {conversations['total']}")
    except Exception as e:
        print(f"   Error getting debug data: {e}")

if __name__ == "__main__":
    test_api()
