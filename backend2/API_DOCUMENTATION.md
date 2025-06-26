# BrightSmile Dental AI Assistant - API Documentation

## Overview
Complete backend API implementation for dental clinic AI assistant with local caching and Kolla API integration.

## Core APIs for Agent Integration

### 1. GET /api/availability?date={{DATE}}
**Purpose**: Fetches real-time availability for the next 3 days from the requested date
**Caching**: 8-hour refresh cycle for schedule data
**Usage**: Checking available appointment slots

**Request**:
```
GET /api/availability?date=2024-01-15
```

**Response**:
```json
{
  "success": true,
  "requested_date": "2024-01-15",
  "availability": {
    "2024-01-15": {
      "available_slots": [
        {
          "start_time": "09:00",
          "end_time": "09:30",
          "datetime": "2024-01-15T09:00:00Z",
          "duration_minutes": 30,
          "available": true
        }
      ]
    }
  },
  "total_days": 3
}
```

### 2. POST /api/get_appointment
**Purpose**: Retrieves existing appointment information for a patient
**Caching**: 24-hour refresh cycle
**Usage**: Rescheduling and confirming appointments

**Request**:
```json
{
  "name": "John Doe",
  "dob": "1990-01-15"
}
```

**Response**:
```json
{
  "success": true,
  "patient_name": "John Doe",
  "patient_dob": "1990-01-15",
  "appointments": [
    {
      "id": "apt_123",
      "start_time": "2024-01-20T10:00:00Z",
      "end_time": "2024-01-20T10:30:00Z",
      "status": "confirmed",
      "duration_minutes": 30
    }
  ],
  "total_appointments": 1,
  "source": "cache"
}
```

### 3. POST /api/get_contact
**Purpose**: Retrieves existing patient contact information
**Caching**: 24-hour refresh cycle
**Usage**: Booking appointments with existing patients

**Request**:
```json
{
  "name": "John Doe",
  "dob": "1990-01-15"
}
```

**Response**:
```json
{
  "success": true,
  "patient_name": "John Doe",
  "patient_dob": "1990-01-15",
  "contact_info": {
    "patient_id": "patient_123",
    "name": "John Doe",
    "email": "john@email.com",
    "phone": "555-1234",
    "address": {...},
    "preferences": {...}
  },
  "source": "cache"
}
```

### 4. POST /api/book_patient_appointment
**Purpose**: Books a new appointment with comprehensive patient data
**Usage**: Both new and existing patient bookings

**Request**:
```json
{
  "name": "John Doe",
  "contact": "555-1234",
  "day": "Monday",
  "date": "2024-01-22",
  "dob": "1990-01-15",
  "time": "10:00 AM",
  "is_new_patient": false,
  "service_booked": "Cleaning",
  "doctor_for_appointment": "Dr. Smith"
}
```

### 5. POST /api/reschedule_patient_appointment (Flexible Agent Format)
**Purpose**: Modifies an existing appointment
**Usage**: Accepts flexible agent data format and maps to Kolla API

**Request** (Agent can send any combination of these fields):
```json
{
  "appointment_id": "apt_123",
  "start_time": "2024-01-25T14:00:00Z",
  "end_time": "2024-01-25T14:30:00Z",
  "wall_start_time": "2024-01-25 14:00:00",
  "wall_end_time": "2024-01-25 14:30:00",
  "new_date": "2024-01-25",
  "new_time": "2:00 PM",
  "contact_id": "contacts/abc123",
  "contact": {...},
  "providers": [...],
  "scheduler": {...},
  "appointment_type_id": "appointmenttypes/123",
  "operatory": "resources/room1",
  "short_description": "Rescheduled appointment",
  "notes": "Patient requested later time",
  "additional_data": {...}
}
```

**Response**:
```json
{
  "success": true,
  "message": "Appointment apt_123 rescheduled successfully",
  "appointment_id": "apt_123",
  "updated_fields": {
    "start_time": "2024-01-25T14:00:00Z",
    "end_time": "2024-01-25T14:30:00Z",
    "notes": "Patient requested later time"
  },
  "status": "rescheduled"
}
```

## Supporting APIs

### 6. POST /api/appointment_details_by_patient
**Purpose**: Retrieves appointment details from cache based on patient information
**Caching**: 24-hour refresh cycle
**Usage**: Getting detailed appointment information for confirmation or rescheduling

**Request**:
```json
{
  "name": "John Doe",
  "dob": "1990-01-15"
}
```

**Response**:
```json
{
  "success": true,
  "patient_name": "John Doe",
  "patient_dob": "1990-01-15",
  "appointments": [
    {
      "id": "apt_123",
      "start_time": "2024-01-20T10:00:00Z",
      "end_time": "2024-01-20T10:30:00Z",
      "status": "confirmed",
      "duration_minutes": 30
    }
  ],
  "total_appointments": 1,
  "source": "cache"
}
```

### 7. POST /api/confirm_appointment
**Purpose**: Confirms an existing appointment using Kolla API format
**Usage**: Agent sends flexible confirmation data, backend maps to Kolla format

**Request**:
```json
{
  "appointment_id": "apt_123",
  "name": "John Doe",
  "confirmed": true,
  "confirmation_type": "confirmationTypes/a)",
  "notes": "Patient confirmed via phone call"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Appointment apt_123 confirmed successfully.",
  "appointment_id": "apt_123",
  "confirmed": true,
  "status": "confirmed"
}
```

### 8. POST /api/send_new_patient_form
**Purpose**: Sends new patient forms to a phone number
**Usage**: New patient onboarding process

**Request**:
```json
{
  "phone_number": "555-1234"
}
```

### 8. POST /api/send_new_patient_form
**Purpose**: Sends new patient forms to a phone number
**Usage**: New patient onboarding process

**Request**:
```json
{
  "phone_number": "555-1234"
}
```

### 9. POST /api/log_callback_request
**Purpose**: Records callback requests when clinic is closed or tools fail
**Usage**: Follow-up management

**Request**:
```json
{
  "name": "John Doe",
  "contact": "555-1234",
  "reason": "Schedule cleaning appointment",
  "preferred_callback_time": "Tomorrow morning"
}
```

### 10. POST /api/log_conversation_summary
**Purpose**: Creates conversation logs at the end of each call
**Usage**: Tracking patient interactions and outcomes

**Request**:
```json
{
  "patient_name": "John Doe",
  "conversation_summary": "Patient called to schedule cleaning, appointment booked for next week",
  "call_outcome": "Appointment successfully scheduled",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Additional Endpoints

### Appointment Details
- `GET /api/appointment_details/{appointment_id}` - Fetch specific appointment details from Kolla API
- `POST /api/appointment_details_by_patient` - Fetch appointment details from cache based on patient name and DOB

**Request for appointment details by patient**:
```json
{
  "name": "John Doe",
  "dob": "1990-01-15"
}
```

**Response**:
```json
{
  "success": true,
  "patient_name": "John Doe",
  "patient_dob": "1990-01-15",
  "appointments": [
    {
      "id": "apt_123",
      "start_time": "2024-01-20T10:00:00Z",
      "end_time": "2024-01-20T10:30:00Z",
      "status": "confirmed",
      "duration_minutes": 30
    }
  ],
  "total_appointments": 1,
  "source": "cache"
}
```

### Appointment Confirmation
- `POST /api/confirm_appointment` - Confirm an appointment using the Kolla API format

**Request**:
```json
{
  "appointment_id": "apt_123",
  "name": "John Doe",
  "confirmed": true,
  "confirmation_type": "confirmationTypes/a)",
  "notes": "Patient confirmed via phone call"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Appointment apt_123 confirmed successfully.",
  "appointment_id": "apt_123",
  "confirmed": true,
  "status": "confirmed"
}
```

### Cache Management
- `GET /api/availability/refresh` - Manually refresh availability cache
- `POST /api/get_appointment/refresh` - Refresh appointment cache for specific patient
- `POST /api/get_contact/refresh` - Refresh contact cache for specific patient

### Analytics & Management
- `GET /api/callback_requests` - List all callback requests
- `PUT /api/callback_requests/{id}/status` - Update callback status
- `GET /api/conversation_logs` - Retrieve conversation logs
- `GET /api/conversation_logs/analytics` - Get conversation analytics

## Caching Strategy

### Schedule Data
- **Refresh**: Every 8 hours
- **Storage**: SQLite local cache
- **Purpose**: Reduce API calls for frequently requested availability data

### Patient Data (Appointments & Contacts)
- **Refresh**: Every 24 hours
- **Storage**: SQLite local cache with patient name/DOB indexing
- **Purpose**: Fast patient lookup without hitting Kolla API repeatedly

### Cache Cleanup
- Automatic cleanup of old data to prevent database bloat
- Configurable retention periods

## Agent Integration Flow

### Appointment Management Flow
1. **Agent hits**: `POST /api/appointment_details_by_patient` with patient name and DOB
2. **Backend retrieves**: Appointment details from local cache (24-hour refresh cycle)
3. **Agent gets**: List of appointments for the patient
4. **For confirmation**: Agent hits `POST /api/confirm_appointment` with appointment_id
5. **Backend processes**: Maps agent fields to Kolla API format
6. **Backend calls**: Kolla API POST endpoint `appointments/{id}:confirm`
7. **Backend returns**: Success/failure response to agent

### Rescheduling Flow
1. **Agent hits**: `POST /api/reschedule_patient_appointment`
2. **Backend receives**: Flexible request format with appointment_id and time fields
3. **Backend processes**: Maps agent fields to Kolla API format
4. **Backend calls**: Kolla API PATCH endpoint
5. **Backend returns**: Success/failure response to agent

The system is designed to be flexible and accept various field formats from the agent while maintaining compatibility with the Kolla API structure.
