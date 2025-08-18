import json, time, hmac, os
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import Request, APIRouter
from pymongo import MongoClient


secret = os.getenv("WEBHOOK_SECRET")

client = MongoClient(os.getenv("MONGODB_CONNECTION_STRING"))
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

    # Save raw payload to Mongo in EST
    now_est = datetime.now(ZoneInfo("America/New_York"))
    db.raw_webhooks.insert_one({
        "received_at_est": now_est,
        "payload": data
    })

    return {"status": "received"}


# GET: Fetch the latest saved webhook payload
@router.get("/latest_transcript")
def get_latest_transcript():
    latest_doc = db.raw_webhooks.find_one(sort=[("_id", -1)])
    if not latest_doc:
        return {"error": "No transcripts found"}

    return {
        "received_at_est": latest_doc["received_at_est"],
        "payload": latest_doc["payload"]
    }