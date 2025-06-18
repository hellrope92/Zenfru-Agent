"""
Test script for GetKolla service
"""

import sys
sys.path.append('.')

from services.getkolla_service import GetKollaService
from datetime import datetime, timedelta
import json

def test_getkolla_service():
    """Test the GetKolla service functionality"""
    
    print("Testing GetKolla Service...")
    
    # Initialize service
    service = GetKollaService()
    
    # Test 1: Health check
    print("\n1. Testing API connectivity...")
    if service.health_check():
        print("✅ Kolla API is accessible")
    else:
        print("❌ Kolla API is not accessible")
    
    # Test 2: Fetch booked appointments
    print("\n2. Testing booked appointments fetch...")
    start_date = datetime.now()
    end_date = start_date + timedelta(days=7)
    
    booked_appointments = service.get_booked_appointments(start_date, end_date)
    print(f"📅 Found {len(booked_appointments)} booked appointments")
    
    if booked_appointments:
        print("Sample appointment:")
        print(json.dumps(booked_appointments[0], indent=2, default=str)[:500] + "...")
    
    # Test 3: Get available slots for next 7 days
    print("\n3. Testing available slots calculation...")
    available_slots = service.get_available_slots_next_7_days()
    
    print(f"🕐 Available slots for next 7 days:")
    for day, slots in available_slots.items():
        print(f"  {day}: {len(slots)} slots")
        if slots:
            print(f"    First few slots: {slots[:3]}")
    
    # Test 4: Get available slots for specific date
    print("\n4. Testing available slots for specific date...")
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_slots = service.get_available_slots_for_date(tomorrow)
    print(f"📆 Available slots for {tomorrow.strftime('%Y-%m-%d')}: {len(tomorrow_slots)}")
    if tomorrow_slots:
        print(f"    Slots: {tomorrow_slots}")
    
    print("\n✅ Testing completed!")

if __name__ == "__main__":
    test_getkolla_service()
