# Patient Interaction Reporting System

## Overview

The Patient Interaction Reporting System automatically logs and analyzes all patient interactions with the BrightSmile Dental AI Assistant. It provides comprehensive daily reports, statistics, and email notifications to help clinic staff monitor the AI assistant's performance and patient engagement.

## Features

### 🔄 Automatic Logging
- **Real-time logging** of all patient interactions
- **Categorized interactions**: Booking, Rescheduling, Confirmation, Callback, FAQ, New Patient Forms, Misc
- **Success/failure tracking** with detailed error messages
- **Privacy protection**: Contact numbers are sanitized in logs
- **Structured data storage** in JSON format

### 📊 Daily Reports
- **Professional HTML reports** with modern styling
- **Comprehensive statistics**: Success rates, call volumes, peak hours
- **Categorized breakdowns** by interaction type
- **Patient details** (configurable for privacy)
- **Error tracking** and failure analysis

### 📧 Email Automation
- **Automated daily emails** at configurable times
- **Multiple recipients** support
- **SMTP configuration** for various email providers
- **Fallback notifications** for system errors
- **Test email functionality** to verify configuration

### 📈 Analytics & Statistics
- **Multi-day summaries** (configurable period)
- **Success rate trends** by interaction type
- **Peak hour analysis** for optimal staffing
- **Daily interaction counts** and patterns
- **API endpoints** for real-time statistics

## Installation & Setup

### 1. Dependencies
The system is already integrated into the main application. Required dependencies are listed in `requirements.txt`:

```bash
pip install schedule
```

### 2. Configuration
Configure the reporting system via the API or by editing `reporting_config.json`:

```json
{
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": true,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "recipients": ["manager@brightsmile-dental.com", "admin@brightsmile-dental.com"],
    "sender_name": "BrightSmile Dental AI Assistant"
  },
  "reporting": {
    "daily_email_time": "17:00",
    "timezone": "UTC",
    "include_patient_details": true,
    "include_statistics": true,
    "max_retries": 3
  },
  "fallback": {
    "backup_email": "backup@brightsmile-dental.com",
    "log_to_file_only": false
  }
}
```

## API Endpoints

### Configuration Management

#### POST /api/configure_reporting
Update reporting system configuration.

**Request:**
```json
{
  "email_username": "your-email@gmail.com",
  "email_password": "your-app-password",
  "recipients": ["manager@clinic.com"],
  "daily_email_time": "17:00",
  "include_patient_details": true,
  "backup_email": "backup@clinic.com"
}
```

#### GET /api/reporting_config
Get current configuration (sensitive data masked).

### Report Generation

#### POST /api/generate_report
Generate manual report for any date.

**Request:**
```json
{
  "target_date": "2025-07-04",
  "send_email": true
}
```

#### GET /api/interaction_statistics?days=7
Get interaction statistics for specified period.

### Data Access

#### GET /api/daily_interactions/{YYYY-MM-DD}
Get all interactions for a specific date.

#### GET /api/interaction_summary
Get today's interaction summary.

#### GET /api/log_files
List all available log files.

### Testing

#### POST /api/test_email
Test email configuration by sending a test email.

## Data Storage

### Log Files
- **Location**: `interaction_logs/` directory
- **Format**: `interactions_YYYY_MM_DD.json`
- **Structure**: Structured JSON with interaction details
- **Retention**: Configurable (files are not automatically deleted)

### Log Entry Structure
```json
{
  "interaction_id": "uuid-string",
  "timestamp": "2025-07-04T15:30:00",
  "date": "2025-07-04",
  "time": "15:30:00",
  "interaction_type": "booking",
  "patient_name": "John Doe",
  "contact_number": "****1234",
  "success": true,
  "appointment_id": "APT-12345",
  "service_type": "Cleaning",
  "doctor": "Dr. Smith",
  "error_message": null,
  "details": {
    "date": "2025-07-05",
    "time": "10:00",
    "is_new_patient": false
  }
}
```

## Email Configuration

### Gmail Setup
1. Enable 2-factor authentication
2. Generate an App Password
3. Use the App Password in the configuration

### Other SMTP Providers
- **Outlook**: smtp-mail.outlook.com:587
- **Yahoo**: smtp.mail.yahoo.com:587
- **Custom SMTP**: Configure server and port as needed

## Report Features

### Statistics Include:
- Total calls and success rates
- Interaction type breakdowns
- Peak hour analysis
- Failed interaction analysis
- Patient engagement metrics

### Report Sections:
1. **Daily Statistics**: Overview metrics and success rates
2. **Interactions by Category**: Detailed breakdowns
3. **Patient Details**: Individual interaction logs (optional)
4. **Error Analysis**: Failed interactions with reasons

## Security & Privacy

### Data Protection:
- Contact numbers are sanitized (only last 4 digits shown)
- Patient details can be excluded from reports
- Sensitive configuration data is masked in API responses
- All data stored locally (no external services)

### Access Control:
- API endpoints can be restricted by authentication
- Configuration requires appropriate permissions
- Log files stored in protected directory

## Monitoring & Maintenance

### Health Checks:
- Daily report generation status
- Email delivery monitoring
- Log file integrity checks
- Configuration validation

### Troubleshooting:
1. Check email configuration with test endpoint
2. Verify log file permissions
3. Monitor error messages in console output
4. Check fallback email notifications

## Integration Points

The system automatically logs interactions from:
- `booking_api.py`: New appointment bookings
- `reschedule_api.py`: Appointment rescheduling
- `confirm_api.py`: Appointment confirmations
- `patient_services_api.py`: Forms, callbacks, FAQ queries

## Customization

### Adding New Interaction Types:
1. Add to `InteractionType` enum in `patient_interaction_logger.py`
2. Add logging calls in relevant API endpoints
3. Update HTML report templates if needed

### Custom Report Templates:
Modify the `_generate_html_report` method to customize report appearance and content.

### Additional Statistics:
Extend the `_calculate_statistics` method to include custom metrics.

## Performance Considerations

- Log files are rotated daily
- JSON files are efficient for the expected data volume
- In-memory operations for statistics calculation
- Asynchronous email sending doesn't block API responses

## Future Enhancements

- Weekly/monthly report aggregation
- Dashboard interface for real-time monitoring
- Integration with external analytics platforms
- Advanced filtering and search capabilities
- Export functionality (CSV, PDF)
- Multi-tenant support for multiple clinics
