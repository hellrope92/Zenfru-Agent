#!/usr/bin/env python3
"""
Test script for the self-contained KollaAPIs class
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up environment variables for testing
os.environ['GETKOLLA_BASE_URL'] = 'https://api.getkolla.com'
os.environ['GETKOLLA_API_KEY'] = 'test_key'
os.environ['GETKOLLA_CLINIC_ID'] = 'test_clinic'

from kolla_apis import KollaAPIs, CheckSlotsRequest

async def test_kolla_apis():
    """Test the self-contained KollaAPIs functionality"""
    print("🧪 Testing Self-Contained KollaAPIs")
    print("=" * 50)
    
    # Initialize the API
    kolla_api = KollaAPIs()
    
    # Test 1: Check availability for a specific date
    print("\n📅 Test 1: Get availability for 2025-06-25")
    date_availability = kolla_api._get_availability_for_date("2025-06-25")
    print(f"Date: {date_availability['date']}")
    print(f"Day: {date_availability['day_name']}")
    print(f"Doctor: {date_availability['doctor']}")
    print(f"Status: {date_availability['status']}")
    print(f"Total slots: {date_availability['total_slots']}")
    print(f"Booked slots: {date_availability['booked_slots']}")
    print(f"Free slots: {date_availability['free_slots']}")
    print(f"Available times: {date_availability['available_times'][:10]}...")
    
    # Test 2: Get availability for next 7 days
    print("\n📅 Test 2: Get availability for next 7 days")
    availability_result = kolla_api._get_availability_next_days(7)
    print(f"Success: {availability_result['success']}")
    print(f"Total days: {availability_result['total_days']}")
    print(f"Dates covered: {availability_result['dates_covered']}")
    
    for date, data in list(availability_result['availability'].items())[:3]:
        print(f"  {date} ({data['day_name']}): {len(data['available_times'])} slots available")
    
    # Test 3: Test the API endpoint
    print("\n📅 Test 3: Test check_available_slots API method")
    request = CheckSlotsRequest(day="Wednesday")
    slots_result = await kolla_api.check_available_slots(request)
    print(f"Total slots found: {slots_result['total_slots']}")
    print(f"Days checked: {len(slots_result['days_checked'])}")
    print(f"Sample slots: {slots_result['available_slots'][:3]}")
    
    # Test 4: Test get_schedule_for_date API method
    print("\n📅 Test 4: Test get_schedule_for_date API method")
    schedule_result = await kolla_api.get_schedule_for_date("2025-06-25")
    print(f"Success: {schedule_result['success']}")
    if schedule_result['success']:
        print(f"Date: {schedule_result['date']}")
        print(f"Doctor: {schedule_result['doctor']}")
        print(f"Available slots: {len(schedule_result['available_slots'])}")
        print(f"Total slots: {schedule_result['total_slots']}")
        print(f"Free slots: {schedule_result['free_slots']}")
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_kolla_apis())
