import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from fastapi import APIRouter
from zoneinfo import ZoneInfo
from openai import OpenAI

# env + db setup
secret = os.getenv("WEBHOOK_SECRET")
client = MongoClient(os.getenv("MONGODB_CONNECTION_STRING"))
db = client["calls"]

router = APIRouter(prefix="/api", tags=["transcripts"])

# OpenAI client
gpt_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@router.get("/transcripts/last_24h")
async def get_cleaned_transcripts_last_24h():
    """
    Fetch transcripts from the last 24 hours (EST), 
    clean them, and return relevant fields.
    """
    est = ZoneInfo("America/New_York")
    now_est = datetime.now(est)
    since_est = now_est - timedelta(hours=24)

    transcripts = db.transcripts.find({
        "received_at_est": {"$gte": since_est.isoformat()}
    })

    cleaned = []
    for t in transcripts:
        payload = t.get("payload", {})
        data = payload.get("data", {})
        analysis = data.get("analysis", {})
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
        phone_number = (
            analysis.get("data_collection_results", {})
            .get("number", {})
            .get("value")
        )
        est_time = t.get("received_at_est")

        cleaned.append({
            "name": name,
            "phone_number": phone_number,
            "est_time": est_time,
            "conversation": "\n".join(conversation)
        })

    return cleaned


def generate_summary_email(calls):
    """
    Use GPT to classify calls into 2 sections and count booking types.
    Then format a summary email accordingly.
    """
    if not calls:
        return "No calls found in the last 24 hours."

    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%B %d, %Y")

    # Prepare context for GPT
    calls_text = ""
    for c in calls:
        calls_text += f"""
Caller Name: {c.get('name', 'Unknown')}
Caller Number: {c.get('phone_number', 'Unknown')}
Call Time (EST): {c.get('est_time')}
Transcript:
{c.get('conversation')}
---
"""

    prompt = f"""
You are an assistant that writes structured call summaries for calls received by a dental clinic ai agent. You have the transcripts for each day and must summarise every call into 1-2 sentences that will tell the human receptionist what happened in the call and what they need to do.

Classify each call into one of two categories:
1. "Action/Call Back Required" (for something that needs follow-up).
2. "Key Booking Interactions" (for something the agent handled successfully, no call back needed).

Also count: Appointment Bookings, Appointment Confirmations.

⚠️ VERY IMPORTANT: Output the email in *this exact format*. 
Do not add any commentary, notes, explanations, or sections outside of this template. 
If there is no data for a section, don't include the section header.
If there are no calls, put a note that says "No calls were received between 9am yesterday and 9am today."

For every <entry> in the Action/Call Back Required and Key Booking Interactions sections, use this format:
(Name) calling from (Phone) on (Date), (Time): [Summary/Action].
If the name is missing, use "Call from (Phone) on (Date), (Time): ...". If the phone is missing, use "(Name) calling on (Date), (Time): ...". If both are missing, use "Call on (Date), (Time): ...". Always include the date and time in the entry.

Hi Cesi and Dr. Andriy,

Sharing a quick summary of calls received and actions required based on interactions from {today_str}.

Total Calls: <count>

Appointment Bookings: <count>
Appointment Confirmations: <count>

Action/Call Back Required:
- <entries>

Key Booking Interactions:
- <entries>

Thanks,
Zenfru Team

Here are the calls to analyze:
{calls_text}
"""

    response = gpt_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional assistant that prepares call summaries for a dental clinic receptionist to read every morning. Always follow the required template strictly."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    cleaned = get_cleaned_transcripts_last_24h()
    # summary_email = generate_summary_email(cleaned)
    print(cleaned)