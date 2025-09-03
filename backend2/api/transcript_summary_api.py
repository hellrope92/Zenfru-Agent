import os, json
from datetime import datetime, timedelta
from pymongo import MongoClient
from fastapi import APIRouter
from zoneinfo import ZoneInfo
from datetime import timezone
from openai import OpenAI

# env + db setup
secret = os.getenv("WEBHOOK_SECRET")
client = MongoClient(os.getenv("MONGODB_CONNECTION_STRING"))
db = client["calls"]

router = APIRouter(prefix="/api", tags=["transcripts"])

# OpenAI client
gpt_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def format_us_phone_number(number: str | None) -> str | None:
    if not number:
        return None
    number = number.strip()
    if number.lower() == "null" or number == "":
        return None
    if number.startswith('+1') and len(number) == 12:
        area = number[2:5]
        mid = number[5:8]
        last = number[8:12]
        return f"{area}-{mid}-{last}"
    return number


@router.get("/transcripts/last_24h")
async def get_cleaned_transcripts_last_24h():
    """
    Fetch transcripts from the last 24 hours (UTC), 
    clean them, and return relevant fields (i.e., name, phone number, time in EST, conversation).
    """
    now_utc = datetime.now(ZoneInfo("UTC"))
    since_utc = now_utc - timedelta(hours=24)

    transcripts = db.raw_webhooks.find({
        "received_at_utc": {"$gte": since_utc, "$lte": now_utc}
    })

    cleaned = []
    for t in transcripts:
        payload = t.get("payload", {})
        data = payload.get("data", {})
        analysis = data.get("analysis", {})
        metadata = data.get("metadata", {})
        transcript_raw = data.get("transcript", [])

        # conversation back and forth only
        conversation = []
        for turn in transcript_raw:
            if turn.get("role") in ("agent", "user") and turn.get("message"):
                conversation.append(f"{turn['role'].capitalize()}: {turn['message']}")

        # extract metadata
        name = (
            analysis.get("data_collection_results", {})
            .get("name", {})
            .get("value")
        )

        phone_number = format_us_phone_number(
            analysis.get("data_collection_results", {})
            .get("number", {})
            .get("value")
            or 
            metadata.get("phone_call", {})
            .get("external_number") 
            )

        utc_time = t.get("received_at_utc")
        # Convert UTC time to EST for output
        if utc_time:
            if utc_time.tzinfo is None:
                utc_time = utc_time.replace(tzinfo=timezone.utc)
            est_time = utc_time.astimezone(ZoneInfo("America/New_York"))
        else:
            est_time = None

        cleaned.append({
            "name": name,
            "phone_number": phone_number,
            "est_time": est_time,
            "conversation": "\n".join(conversation)
        })

    # Sort by est_time (oldest first)
    cleaned.sort(key=lambda x: x["est_time"] if x["est_time"] is not None else datetime.max)

    return cleaned

@router.get("/daily_summary")
async def generate_summary_email():
    """
    Use GPT to classify calls into 2 sections and count booking types.
    Then format a summary email accordingly.
    """

    calls = await get_cleaned_transcripts_last_24h()

    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")

    # Prepare context for GPT
    calls_text = ""
    for c in calls:
        calls_text += f"""
Caller Name: {c.get('name', 'Unknown')}
Caller Number: {c.get('phone_number', 'Unknown')}
Call Time: {c.get('est_time')}
Transcript:
{c.get('conversation')}
---
"""

    prompt = f"""
You are an assistant that writes structured call summaries for calls received by a dental clinic AI agent. You have the transcripts for each day and must summarise every call into 1-2 sentences that will tell the human receptionist what happened in the call and what they need to do.

Classify each call into one of two categories:
1. "Action/Call Back Required" (for something that needs follow-up).
2. "Key Booking Interactions" (for something the agent handled successfully, no call back needed).

Also count: 
- Appointment Bookings 
- Appointment Confirmations 

⚠️ VERY IMPORTANT: 
Do not add any commentary, notes, explanations, or sections outside of this template. Give objective summaries, not emotions.
Output ONLY valid JSON in this exact structure:
{{
  "appointment_bookings": <int>,
  "appointment_confirmations": <int>,
  "action_call_back_required": [
    {{
      "name": "<string or null>",
      "phone": "<string or null>",
      "date": "<MMM DD YYYY>",
      "time": "<HH:MM AM/PM>",
      "summary": "<string>"
    }}
  ],
  "key_booking_interactions": [
    {{
      "name": "<string or null>",
      "phone": "<string or null>",
      "date": "<MMM DD YYYY>",
      "time": "<HH:MM AM/PM>",
      "summary": "<string>"
    }}
  ]
}}

Rules for entries:
- Always include date and time.
- If name is missing, set "name": null.
- If phone is missing, set "phone": null.
- If the caller did not speak, summary must be: "Caller did not speak at all. Call back needed."
- Otherwise, summary should be a concise description of the call (max 1-2 sentences).

If there are no calls, output this instead:
{{ "note": "No calls were received between 9am yesterday and 9am today." }}

Here is a sample for reference:

{{
  "appointment_bookings": 0,
  "appointment_confirmations": 1,
  "action_call_back_required": [
    {{
      "name": "Trudy Alston",
      "phone": "(201) 725-8734",
      "date": "Aug 12 2025",
      "time": "09:34 AM",
      "summary": "Wants a call back to speak to someone about scheduling an appointment. Call back needed."
    }},
    {{
      "name": null,
      "phone": "(973) 889-0030",
      "date": "Aug 12 2025",
      "time": "09:36 AM",
      "summary": "Wanted to speak to someone, did not specify name or reason. Call back to understand need."
    }},
    {{
      "name": null,
      "phone": "(646) 377-6926",
      "date": "Aug 12 2025",
      "time": "09:49 AM",
      "summary": "Wanted to communicate in Spanish and mentioned they were injured but it was not an emergency. Call back to understand need."
    }},
    {{
      "name": "Deborah from Wolfston Equity",
      "phone": "(214) 347-9701",
      "date": "Aug 12 2025",
      "time": "10:08 AM",
      "summary": "Asked to pass a message for Dr. Hanna that they want to speak about an important business matter about the practice. Call back needed."
    }},
    {{
      "name": "Jill from Darby Dental",
      "phone": "877-573-3200 ext 1261",
      "date": "Aug 12 2025",
      "time": "11:24 AM",
      "summary": "Called to see if Dr. needed any supplies. Call back needed."
    }},
    {{
      "name": null,
      "phone": "(201) 238-4103",
      "date": "Aug 12 2025",
      "time": "12:23 PM",
      "summary": "Asked about Medicaid, price of fillings, payment plans. Agent answered queries and they disconnected abruptly, call back to understand requirements."
    }},
    {{
      "name": "Janetta",
      "phone": "(504) 910-6372",
      "date": "Aug 12 2025",
      "time": "03:59 PM",
      "summary": "IT provider wanting to speak about on-site installation of PCs. Call back accordingly."
    }},
    {{
      "name": "Clarice on behalf of Temple University",
      "phone": "855-303-9233",
      "date": "Aug 12 2025",
      "time": "06:06 PM",
      "summary": "Calling to update your information for the upcoming 2025 Temple University Oral History Project. If you wish to have your number removed from future call attempts, please call 800-201-4771."
    }}
  ],
  "key_booking_interactions": [
    {{
      "name": null,
      "phone": "(347) 585-0758",
      "date": "Aug 12 2025",
      "time": "12:00 PM",
      "summary": "Called to get clinic address, successful interaction."
    }},
    {{
      "name": "Jane Shellhammer",
      "phone": "(201) 963-4879",
      "date": "Aug 12 2025",
      "time": "01:25 PM",
      "summary": "Confirmed six month recall with Imelda Soledad on 11:30 am Aug 28. Wants a call back to know if the antibiotics to take before any cleaning are available in the office."
    }}
  ]
}}

Here are the calls to analyze:
{calls_text}
"""

    response = gpt_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional assistant that prepares call summaries for a dental clinic receptionist to read every morning. Always follow the required template strictly. Never say the agent could not do something."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    raw_output = response.choices[0].message.content
    
    try:
        parsed_json = json.loads(raw_output)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON from summary", "raw_output": raw_output}

    return parsed_json