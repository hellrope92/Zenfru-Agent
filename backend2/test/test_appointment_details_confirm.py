"""
Test script for appointment details and confirmation APIs
"""

import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_appointment_details_by_patient():
    """Test getting appointment details by patient name and DOB"""
    print("🧪 Testing appointment details by patient...")
    
    url = f"{BASE_URL}/appointment_details_by_patient"
    payload = {
        "name": "John Doe",
        "dob": "1990-01-15"
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_appointment_details_by_id():
    """Test getting appointment details by appointment ID"""
    print("\n🧪 Testing appointment details by ID...")
    
    appointment_id = "apt_123"  # Example ID
    url = f"{BASE_URL}/appointment_details/{appointment_id}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_confirm_appointment():
    """Test confirming an appointment"""
    print("\n🧪 Testing appointment confirmation...")
    
    url = f"{BASE_URL}/confirm_appointment"
    payload = {
        "appointment_id": "apt_123",
        "name": "John Doe",
        "confirmed": True,
        "confirmation_type": "confirmationTypes/a)",
        "notes": "Patient confirmed via phone call"
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_confirm_appointment_minimal():
    """Test confirming an appointment with minimal data"""
    print("\n🧪 Testing appointment confirmation (minimal)...")
    
    url = f"{BASE_URL}/confirm_appointment"
    payload = {
        "appointment_id": "apt_456"
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Starting API tests...")
    print("=" * 50)
    
    # Test appointment details by patient
    test_appointment_details_by_patient()
    
    # Test appointment details by ID
    test_appointment_details_by_id()
    
    # Test confirmation with full data
    test_confirm_appointment()
    
    # Test confirmation with minimal data
    test_confirm_appointment_minimal()
    
    print("\n✅ Test script completed!")
