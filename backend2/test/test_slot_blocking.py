#!/usr/bin/env python3
"""
Test script to validate the GetKolla service appointment slot blocking logic
"""

import sys
import os
from datetime import datetime, timedelta
import json

# Add the parent directory to the path so we can import our service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.getkolla_service import GetKollaService

def test_slot_blocking():
    """Test that appointments properly block multiple slots"""
    
    # Create a service instance
    service = GetKollaService()
    
    # Test the new availability method
    result = service.get_availability_with_schedule_data("2025-06-25", 1)
    
    print("Availability Result:")
    print(json.dumps(result, indent=2))
    
    # Test parsing appointment times
    sample_appointment = {
        "wall_start_time": "2025-06-25 09:00:00",
        "wall_end_time": "2025-06-25 10:00:00"
    }
    
    start_time = service._parse_appointment_time(sample_appointment, "wall_start_time")
    end_time = service._parse_appointment_time(sample_appointment, "wall_end_time")
    
    print(f"\nParsed appointment times:")
    print(f"Start: {start_time}")
    print(f"End: {end_time}")
    print(f"Duration: {(end_time - start_time).total_seconds() / 60} minutes")
    
    # Test 24-hour slot generation
    slots = service._generate_time_slots_24h("09:00", "17:00", 30)
    print(f"\nGenerated 30-minute slots from 09:00 to 17:00:")
    print(f"Total slots: {len(slots)}")
    print(f"First 10 slots: {slots[:10]}")

if __name__ == "__main__":
    test_slot_blocking()
