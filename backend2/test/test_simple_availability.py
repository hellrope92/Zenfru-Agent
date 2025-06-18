"""
Simple test script for the simplified GetKolla Availability API
Single endpoint that returns 3 days of availability with doctor info
"""

import requests
import json
from datetime import datetime

# API base URL
BASE_URL = "http://localhost:8000/api"

def test_simple_availability():
    """Test the simplified availability endpoint"""
    
    print("🧪 Testing Simplified GetKolla Availability API")
    print("=" * 60)
    
    # Test with today's date
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n📅 Testing availability for: {today} (+ next 2 days)")
    
    try:
        response = requests.get(f"{BASE_URL}/availability", params={"date": today})
        
        if response.status_code == 200:
            data = response.json()
            
            if data["success"]:
                print("✅ API call successful!")
                print(f"📋 Dates covered: {data['dates_covered']}")
                
                availability = data["availability"]
                
                print(f"\n📊 Daily Breakdown:")
                for date, day_data in availability.items():
                    status = day_data.get("status", "unknown")
                    doctor = day_data.get("doctor", "N/A")
                    free_slots = day_data.get("free_slots", 0)
                    day_name = day_data.get("day_name", "Unknown")
                    
                    print(f"\n   🗓️  {date} ({day_name})")
                    print(f"       👨‍⚕️ Doctor: {doctor}")
                    print(f"       📈 Status: {status}")
                    print(f"       🕐 Free slots: {free_slots}")
                    
                    if status == "open" and free_slots > 0:
                        # Show first few available times
                        available_times = day_data.get("available_times", [])[:5]
                        if available_times:
                            print(f"       ⏰ Sample times: {', '.join(available_times)}")
                    
                    clinic_hours = day_data.get("clinic_hours")
                    if clinic_hours:
                        print(f"       🏥 Clinic hours: {clinic_hours['start']} - {clinic_hours['end']}")
                
                # Summary
                total_free_slots = sum(day.get("free_slots", 0) for day in availability.values())
                open_days = len([day for day in availability.values() if day.get("status") == "open"])
                
                print(f"\n📋 Summary:")
                print(f"   Total free slots across 3 days: {total_free_slots}")
                print(f"   Open days: {open_days}/3")
                
            else:
                print(f"❌ API returned error: {data.get('error')}")
                
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

def show_sample_response():
    """Show what the API response should look like"""
    
    print("\n📋 Expected API Response Format:")
    print("=" * 40)
    
    sample_response = {
        "success": True,
        "requested_date": "2025-06-18",
        "dates_covered": ["2025-06-18", "2025-06-19", "2025-06-20"],
        "availability": {
            "2025-06-18": {
                "date": "2025-06-18",
                "day_name": "Wednesday",
                "doctor": "Dr. Parmar",
                "clinic_hours": {"start": "09:00", "end": "17:00"},
                "total_slots": 16,
                "booked_slots": 3,
                "free_slots": 13,
                "available_times": ["09:00", "09:30", "10:00", "10:30", "11:00"],
                "status": "open"
            },
            "2025-06-19": {
                "date": "2025-06-19",
                "day_name": "Thursday",
                "doctor": "Dr. Hanna",
                "clinic_hours": {"start": "09:00", "end": "18:00"},
                "total_slots": 18,
                "booked_slots": 1,
                "free_slots": 17,
                "available_times": ["09:00", "09:30", "10:00", "10:30", "11:00"],
                "status": "open"
            },
            "2025-06-20": {
                "date": "2025-06-20",
                "day_name": "Friday",
                "doctor": None,
                "clinic_hours": None,
                "total_slots": 0,
                "booked_slots": 0,
                "free_slots": 0,
                "available_times": [],
                "status": "closed"
            }
        },
        "total_days": 3,
        "generated_at": "2025-06-18T10:30:00"
    }
    
    print(json.dumps(sample_response, indent=2))

def show_usage_examples():
    """Show how to use the API"""
    
    print("\n🔧 API Usage Examples:")
    print("=" * 30)
    
    print("\n1. Get availability starting from today:")
    print("GET /api/availability?date=2025-06-18")
    
    print("\n2. Get availability starting from specific date:")
    print("GET /api/availability?date=2025-06-25")
    
    print("\n3. Example with curl:")
    print('curl "http://localhost:8000/api/availability?date=2025-06-18"')
    
    print("\n4. Example with JavaScript fetch:")
    print("""
fetch('http://localhost:8000/api/availability?date=2025-06-18')
  .then(response => response.json())
  .then(data => {
    data.availability.forEach((date, dayData) => {
      console.log(`${date}: ${dayData.doctor} - ${dayData.free_slots} slots`);
    });
  });
""")

if __name__ == "__main__":
    print("🚀 Testing Simplified Availability API")
    print("This API solves the doctor schedule change problem by:")
    print("✅ Getting real-time clinic schedule from GetKolla")
    print("✅ Getting current appointments from GetKolla") 
    print("✅ Using static doctor assignments from local schedule.json")
    print("✅ Calculating free slots = clinic hours - booked appointments")
    print()
    
    show_usage_examples()
    show_sample_response()
    
    # Ask user if they want to run live test
    choice = input("\n🤔 Run live API test? (y/n): ").lower().strip()
    
    if choice == 'y':
        print("\nMake sure the backend server is running on http://localhost:8000")
        test_simple_availability()
    else:
        print("👋 Test skipped. Start the backend and try again!")
    
    print("\n🎯 Key Benefits:")
    print("1. 🔄 Auto-syncs when doctors change schedules in PMS")
    print("2. 👥 Handles doctor substitutions (Dr. Hanna → Dr. Smith)")
    print("3. 📊 Simple: Just clinic hours - appointments = availability")
    print("4. 🎯 Single API call for 3 days of scheduling data")
    print("5. 📱 Easy integration with frontend booking systems")
