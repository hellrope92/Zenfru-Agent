# SMS OTP System Documentation

## Overview

The SMS OTP (One-Time Password) system allows you to send verification codes to phone numbers and verify them securely. This system supports multiple SMS providers and includes rate limiting, expiry management, and comprehensive error handling.

## Features

- 📱 **Multi-Provider Support**: Twilio, TextLocal, and Mock (for testing)
- 🔒 **Security**: Phone number hashing, OTP expiry, attempt limiting
- 🌍 **International**: Automatic phone number normalization
- ⚡ **Rate Limiting**: Prevents spam and abuse
- 🧹 **Auto Cleanup**: Automatic removal of expired OTPs
- 📊 **Status Tracking**: Check OTP status and verification state

## API Endpoints

### 1. Send OTP
**POST** `/api/otp/send`

Send an OTP to a phone number.

```json
{
  "phone_number": "+1234567890"
}
```

**Response:**
```json
{
  "success": true,
  "message": "OTP sent successfully to +1234567890",
  "otp_id": "otp_hash_20241018120000",
  "phone_number": "+1234567890",
  "expires_in_minutes": 5
}
```

### 2. Verify OTP
**POST** `/api/otp/verify`

Verify an OTP code.

```json
{
  "phone_number": "+1234567890",
  "otp": "123456",
  "otp_id": "otp_hash_20241018120000"
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "OTP verified successfully",
  "verified": true,
  "phone_number": "+1234567890"
}
```

**Response (Failure):**
```json
{
  "success": false,
  "message": "Invalid OTP. 2 attempts remaining",
  "verified": false,
  "phone_number": "+1234567890"
}
```

### 3. Check OTP Status
**POST** `/api/otp/status`

Check the current status of an OTP.

```json
{
  "phone_number": "+1234567890"
}
```

**Response:**
```json
{
  "success": true,
  "phone_number": "+1234567890",
  "exists": true,
  "verified": false,
  "expired": false,
  "attempts": 1,
  "max_attempts": 3,
  "expires_at": "2024-10-18T12:05:00",
  "created_at": "2024-10-18T12:00:00"
}
```

### 4. Cleanup Expired OTPs
**POST** `/api/otp/cleanup`

Manually cleanup expired OTPs.

**Response:**
```json
{
  "success": true,
  "message": "Expired OTPs cleaned up successfully"
}
```

### 5. Get Configuration
**GET** `/api/otp/config`

Get current OTP system configuration.

**Response:**
```json
{
  "success": true,
  "config": {
    "otp_length": 6,
    "otp_expiry_minutes": 5,
    "max_attempts": 3,
    "sms_provider": "twilio",
    "twilio_configured": true,
    "textlocal_configured": false,
    "active_otps_count": 5
  }
}
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# SMS Provider Configuration
SMS_PROVIDER=twilio  # Options: twilio, textlocal, mock

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# TextLocal Configuration (Alternative)
TEXTLOCAL_API_KEY=your_api_key
TEXTLOCAL_SENDER=YourBrand
```

### SMS Providers

#### 1. Twilio (Recommended)
- **Pros**: Global coverage, reliable, excellent documentation
- **Setup**: 
  1. Sign up at [twilio.com](https://twilio.com)
  2. Get Account SID, Auth Token, and Phone Number
  3. Add to environment variables

#### 2. TextLocal (India-focused)
- **Pros**: Good for India, cost-effective
- **Setup**:
  1. Sign up at [textlocal.in](https://textlocal.in)
  2. Get API key
  3. Add to environment variables

#### 3. Mock Provider (Testing)
- **Use**: Development and testing
- **Behavior**: Logs OTP to console instead of sending SMS

## Phone Number Formats

The system automatically normalizes phone numbers:

- `+1234567890` ✅ (International format)
- `1234567890` ✅ (Will add +1)
- `(123) 456-7890` ✅ (Will normalize)
- `123-456-7890` ✅ (Will normalize)

## Security Features

### 1. Phone Number Hashing
- Phone numbers are hashed using SHA-256
- Never stored in plain text

### 2. OTP Expiry
- Default: 5 minutes
- Configurable via service settings

### 3. Attempt Limiting
- Default: 3 attempts per OTP
- Account lockout after max attempts

### 4. Rate Limiting
- 1 minute cooldown between OTP requests
- Prevents spam and abuse

## Integration Examples

### Python Client
```python
import requests

API_KEY = "your_api_key"
BASE_URL = "http://localhost:8000"

headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# Send OTP
response = requests.post(
    f"{BASE_URL}/api/otp/send",
    headers=headers,
    json={"phone_number": "+1234567890"}
)

if response.status_code == 200:
    data = response.json()
    otp_id = data["otp_id"]
    
    # Get OTP from user input
    otp_code = input("Enter OTP: ")
    
    # Verify OTP
    verify_response = requests.post(
        f"{BASE_URL}/api/otp/verify",
        headers=headers,
        json={
            "phone_number": "+1234567890",
            "otp": otp_code,
            "otp_id": otp_id
        }
    )
    
    if verify_response.json()["verified"]:
        print("✅ Phone number verified!")
    else:
        print("❌ Invalid OTP")
```

### JavaScript/Frontend
```javascript
const API_KEY = 'your_api_key';
const BASE_URL = 'http://localhost:8000';

const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
};

// Send OTP
async function sendOTP(phoneNumber) {
    const response = await fetch(`${BASE_URL}/api/otp/send`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ phone_number: phoneNumber })
    });
    
    const data = await response.json();
    return data;
}

// Verify OTP
async function verifyOTP(phoneNumber, otpCode, otpId) {
    const response = await fetch(`${BASE_URL}/api/otp/verify`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            phone_number: phoneNumber,
            otp: otpCode,
            otp_id: otpId
        })
    });
    
    const data = await response.json();
    return data.verified;
}

// Usage
sendOTP('+1234567890').then(result => {
    if (result.success) {
        const otpCode = prompt('Enter OTP:');
        verifyOTP('+1234567890', otpCode, result.otp_id).then(verified => {
            if (verified) {
                alert('Phone verified!');
            } else {
                alert('Invalid OTP');
            }
        });
    }
});
```

## Testing

### Run Test Suite
```bash
cd backend2
python test/test_otp_system.py
```

### Manual Testing
1. Set `SMS_PROVIDER=mock` in your `.env`
2. Start the server
3. Send OTP request
4. Check console for OTP code
5. Verify with the displayed code

## Error Handling

### Common Error Responses

#### Rate Limited
```json
{
  "detail": "Please wait before requesting another OTP"
}
```

#### Invalid Phone Number
```json
{
  "detail": "Invalid phone number format"
}
```

#### OTP Expired
```json
{
  "success": false,
  "message": "OTP has expired",
  "verified": false
}
```

#### Max Attempts Exceeded
```json
{
  "success": false,
  "message": "Maximum verification attempts exceeded",
  "verified": false
}
```

## Production Considerations

### 1. Storage
- Current implementation uses in-memory storage
- For production, consider Redis or database storage
- Implement persistence for server restarts

### 2. Monitoring
- Log all OTP operations
- Monitor success/failure rates
- Set up alerts for unusual patterns

### 3. Security
- Use HTTPS in production
- Implement additional rate limiting
- Consider CAPTCHA for additional protection

### 4. Scalability
- Use Redis for distributed systems
- Implement cleanup jobs
- Monitor memory usage

## Troubleshooting

### OTP Not Received
1. Check SMS provider credentials
2. Verify phone number format
3. Check provider account balance
4. Check spam filters

### Verification Failing
1. Check OTP expiry time
2. Verify attempt count
3. Ensure correct phone number format
4. Check for timing issues

### Provider Issues
1. Check API credentials
2. Verify account status
3. Check rate limits
4. Review provider logs

## Support

For issues or questions:
1. Check the logs for error messages
2. Verify configuration settings
3. Test with mock provider first
4. Check SMS provider documentation