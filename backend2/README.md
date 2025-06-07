# BrightSmile Dental AI Assistant - Simple Backend

A lightweight FastAPI backend that implements all the required tools for the dental clinic AI assistant using actual JSON files with console logging.

## Features

- **8 Tool Endpoints**: All tools from `tools.txt` implemented
- **Real Data**: Uses actual `schedule.json`, `bookings.json`, and `knowledge_base.json` files
- **Smart Scheduling**: Shows next 5 days of available slots based on existing bookings
- **Console Logging**: All requests and data are printed to console for debugging
- **Knowledge Base**: FAQ answers come from the actual knowledge base
- **Simplified Logic**: Booking/rescheduling just prints (no actual persistence)

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server:**
   ```bash
   python main.py
   ```

3. **Open your browser:**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/api/health

## API Endpoints

### Core Tools
- `GET /api/get_current_day` - Get current day of week
- `POST /api/check_available_slots` - Check appointment availability (next 5 days)
- `POST /api/book_patient_appointment` - Book new appointment (print only)
- `POST /api/reschedule_patient_appointment` - Reschedule existing appointment (print only)
- `POST /api/send_new_patient_form` - Send patient forms via SMS
- `POST /api/log_callback_request` - Log callback requests (name, contact, preferred_time)
- `POST /api/answer_faq_query` - Answer FAQ questions (uses knowledge_base.json)
- `POST /api/log_conversation_summary` - Log conversation summaries

### Debug Endpoints
- `GET /api/debug/schedule` - View clinic schedule and existing bookings
- `GET /api/debug/callbacks` - View all callbacks
- `GET /api/debug/conversations` - View all conversation logs
- `GET /api/debug/knowledge_base` - View knowledge base info

## Key Features

### Smart Slot Checking
When you call `check_available_slots`, it:
1. Gets the current day
2. Checks the next 5 days
3. For each day, generates time slots based on clinic hours
4. Removes slots that are already booked in `bookings.json`
5. Returns only free slots with doctor assignments

### Real Knowledge Base
FAQ queries search the actual `knowledge_base.json` for:
- Clinic address and location
- Office hours and schedule
- Services offered and pricing
- Doctor information and specialties
- Parking information

### Simplified Callback
Callback requests only need:
- `name`: Patient name
- `contact_number`: Phone number
- `preferred_callback_time`: When they want to be called back

## Sample Requests

### Check Available Slots (Next 5 Days)
```json
POST /api/check_available_slots
{
  "day": "Monday",
  "service_details": "routine cleaning and check-up"
}
```

### Log Callback Request
```json
POST /api/log_callback_request
{
  "name": "John Smith",
  "contact_number": "5551234567",
  "preferred_callback_time": "Tomorrow morning"
}
```

### FAQ Query
```json
POST /api/answer_faq_query
{
  "query": "What are your office hours?"
}
```

## Console Output

All tool calls are logged to the console with emojis:
- 🗓️ Current Day
- 🔍 Check Slots (shows next 5 days)
- 📅 Book Appointment (simulation only)
- 🔄 Reschedule (simulation only)
- 📱 Send Forms
- 📞 Callback Request
- ❓ FAQ Query (real knowledge base search)
- 📝 Conversation Summary

## Data Files Used

- `../schedule.json` - Clinic schedule and doctor assignments
- `../bookings.json` - Existing appointments (removes from available slots)
- `../knowledge_base.json` - Clinic information for FAQ responses

Perfect for testing AI assistant integration!
