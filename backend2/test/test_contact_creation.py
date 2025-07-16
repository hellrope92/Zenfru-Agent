"""
Test script for contact creation functionality
"""
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to import modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from api.models import ContactInfo, BookAppointmentRequest

def test_contact_info_model():
    """Test the ContactInfo model with all new fields"""
    
    # Test with minimal data
    contact_basic = ContactInfo(
        given_name="John",
        family_name="Doe",
        number="908123123",
        email="john@example.com"
    )
    
    print("Basic ContactInfo:")
    print(contact_basic.model_dump(exclude_none=True))
    
    # Test with full data including address
    contact_full = ContactInfo(
        given_name="Jane",
        family_name="Smith", 
        number="908456789",
        email="jane@example.com",
        gender="FEMALE",
        birth_date="1990-05-15",
        street_address="123 Main St",
        city="Basking Ridge",
        state_address="NJ",
        postal_code="07920",
        preferred_hygienist_id="H20",
        preferred_hygienist_name="resources/provider_H20"
    )
    
    print("\nFull ContactInfo:")
    print(contact_full.model_dump(exclude_none=True))

def test_booking_request():
    """Test booking request with contact info"""
    
    contact_info = ContactInfo(
        given_name="Test",
        family_name="Patient",
        number="908999888",
        email="test@example.com",
        gender="MALE",
        birth_date="1985-12-10",
        street_address="456 Oak Ave",
        city="Summit",
        state_address="NJ", 
        postal_code="07901"
    )
    
    booking_request = BookAppointmentRequest(
        name="Test Patient",
        contact="908999888",
        day="Monday",
        date="2025-07-21",
        dob="1985-12-10",
        time="10:00 AM",
        is_new_patient=True,
        service_booked="Cleaning",
        doctor_for_appointment="Dr. Hanna",
        contact_info=contact_info
    )
    
    print("\nBooking Request:")
    print(booking_request.model_dump(exclude_none=True))

if __name__ == "__main__":
    test_contact_info_model()
    test_booking_request()
    print("\n✅ All tests completed successfully!")
