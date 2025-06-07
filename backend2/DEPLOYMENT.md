# 🚀 BrightSmile Dental AI Assistant - Deployment Guide

## Quick Start (Recommended for Testing)

### Option 1: Local + Ngrok (Easiest)

1. **Install dependencies**:
   ```bash
   cd backend2
   pip install -r requirements.txt
   ```

2. **Run local deployment**:
   ```bash
   python deploy_local.py
   ```
   
   This will:
   - Start FastAPI server on localhost:8000
   - Create ngrok tunnel for external access
   - Show you the public URL to use

3. **Access your API**:
   - Local: http://localhost:8000
   - Public: Check ngrok dashboard at http://localhost:4040
   - Docs: http://localhost:8000/docs

---

## Cloud Deployment Options

### Option 2: Railway (Recommended for Production)

1. **Sign up at [railway.app](https://railway.app)**
2. **Connect your GitHub repo**
3. **Deploy**:
   - Railway will auto-detect the Procfile
   - Your API will be live at: `https://your-app.railway.app`

### Option 3: Render

1. **Sign up at [render.com](https://render.com)**
2. **Create new Web Service**
3. **Connect GitHub repo**
4. **Settings**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Option 4: Vercel

1. **Install Vercel CLI**:
   ```bash
   npm i -g vercel
   ```
2. **Deploy**:
   ```bash
   cd backend2
   vercel
   ```

---

## Testing Your Deployed API

### Using the Test Script

```bash
# Update BASE_URL in test_api.py to your deployed URL
# Then run:
python test_api.py
```

### Manual Testing

```bash
# Health check
curl https://your-api-url.com/api/health

# Get current day
curl https://your-api-url.com/api/get_current_day

# Check available slots
curl -X POST https://your-api-url.com/api/check_available_slots \
  -H "Content-Type: application/json" \
  -d '{"day": "Monday", "service_details": "cleaning"}'
```

---

## Integration with AI Voice Assistant

Once deployed, your API endpoints will be:

```
https://your-api-url.com/api/get_current_day
https://your-api-url.com/api/check_available_slots
https://your-api-url.com/api/book_patient_appointment
https://your-api-url.com/api/reschedule_patient_appointment
https://your-api-url.com/api/send_new_patient_form
https://your-api-url.com/api/log_callback_request
https://your-api-url.com/api/answer_faq_query
https://your-api-url.com/api/log_conversation_summary
```

### For ElevenLabs Integration

Configure your AI assistant to make HTTP requests to these endpoints. Each endpoint returns JSON responses that can be easily processed by your voice assistant.

---

## Environment Variables (Optional)

If you need to add API keys later:

```bash
# For Railway/Render/Vercel
ELEVENLABS_API_KEY=your_key_here
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
```

---

## Monitoring & Logs

- **Railway**: Built-in logs and metrics
- **Render**: Logs tab in dashboard
- **Vercel**: Functions tab for logs
- **Local**: Console output with emoji logging

---

## Scaling

For production use:
1. Add authentication middleware
2. Implement rate limiting
3. Add database persistence (replace JSON files)
4. Set up monitoring and alerts
5. Configure CORS for web clients

---

## Support

🦷 Your BrightSmile Dental AI Assistant is ready to help patients 24/7!

**Features working:**
✅ Smart appointment scheduling
✅ FAQ responses from knowledge base  
✅ Callback request logging
✅ New patient form distribution
✅ Conversation tracking
✅ Multi-doctor schedule management
