#!/usr/bin/env python3

from datetime import datetime, timedelta

# Test the overlap logic
def test_overlap():
    # Simulate the appointment: 09:00-10:00
    apt_start = datetime(2025, 6, 25, 9, 0, 0)
    apt_end = datetime(2025, 6, 25, 10, 0, 0)
    
    # Test slots
    slots = [
        ("09:00 AM", datetime(2025, 6, 25, 9, 0, 0), datetime(2025, 6, 25, 9, 30, 0)),
        ("09:30 AM", datetime(2025, 6, 25, 9, 30, 0), datetime(2025, 6, 25, 10, 0, 0)),
        ("10:00 AM", datetime(2025, 6, 25, 10, 0, 0), datetime(2025, 6, 25, 10, 30, 0)),
    ]
    
    print(f"Appointment: {apt_start.strftime('%H:%M')}-{apt_end.strftime('%H:%M')}")
    print()
    
    for slot_name, slot_start, slot_end in slots:
        # Check overlap: not (slot_end <= apt_start or slot_start >= apt_end)
        overlap = not (slot_end <= apt_start or slot_start >= apt_end)
        
        print(f"Slot {slot_name} ({slot_start.strftime('%H:%M')}-{slot_end.strftime('%H:%M')})")
        print(f"  slot_end <= apt_start: {slot_end} <= {apt_start} = {slot_end <= apt_start}")
        print(f"  slot_start >= apt_end: {slot_start} >= {apt_end} = {slot_start >= apt_end}")
        print(f"  Overlap: {overlap}")
        print(f"  Result: {'BLOCKED' if overlap else 'AVAILABLE'}")
        print()

if __name__ == "__main__":
    test_overlap()
