import json, time, hmac, os
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Depends, Request
from services.auth_service import require_api_key
from services.call_analytics_service import get_analytics_service
from pymongo import MongoClient


secret = os.getenv("WEBHOOK_SECRET")

_mongo_uri = os.getenv("MONGODB_CONNECTION_STRING")
# Use certifi CA bundle for TLS in hosted environments
try:
    import certifi
    client = MongoClient(_mongo_uri, tls=True, tlsCAFile=certifi.where())
except Exception:
    # Fallback to default behavior if certifi isn't available
    client = MongoClient(_mongo_uri)

db = client["calls"]

router = APIRouter(prefix="/api", tags=["webhook"])

# POST: Receive webhook from ElevenLabs
@router.post("/get_transcript")
async def get_transcript(request: Request):
    payload = await request.body()

    # Get signature header
    headers = request.headers.get("elevenlabs-signature")
    if not headers:
        return {"error": "Missing signature header"}

    try:
        timestamp = headers.split(",")[0].split("=")[1]
        hmac_signature = headers.split(",")[1]
    except Exception:
        return {"error": "Malformed signature header"}

    # Timestamp check (30 min tolerance)
    tolerance = int(time.time()) - 30 * 60
    if int(timestamp) < tolerance:
        return {"error": "Timestamp expired"}

    # Signature check
    full_payload_to_sign = f"{timestamp}.{payload.decode('utf-8')}"
    mac = hmac.new(
        key=secret.encode("utf-8"),
        msg=full_payload_to_sign.encode("utf-8"),
        digestmod=sha256,
    )
    digest = "v0=" + mac.hexdigest()
    if hmac_signature != digest:
        return {"error": "Invalid signature"}

    # Parse JSON body
    try:
        data = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        return {"error": "Invalid JSON"}

    # Save raw payload to Mongo in UTC
    now_utc = datetime.now(ZoneInfo("UTC"))
    
    if data.get("data").get("agent_id")=='agent_3101k1e6xrv2f4eb0xz6nbbrz035':
        db.raw_webhooks.insert_one({
            "received_at_utc": now_utc,
            "payload": data
        })
        
        # Process analytics and push to Google Sheets
        try:
            analytics_service = get_analytics_service()
            analytics_service.process_call(data)
        except Exception as e:
            print(f"Analytics processing error: {e}")
            # Don't fail the webhook if analytics fails

    return {"status": "received"}


# GET: Fetch the latest saved webhook payload
@router.get("/latest_transcript")
def get_latest_transcript(authenticated: bool = Depends(require_api_key)):
    latest_doc = db.raw_webhooks.find_one(sort=[("_id", -1)])
    if not latest_doc:
        return {"error": "No transcripts found"}

    return {
        "received_at_utc": latest_doc["received_at_utc"],
        "payload": latest_doc["payload"]
    }