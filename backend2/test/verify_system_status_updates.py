r"""Verification script for System Status sheet updates.

Runs a series of success and failure updates for each tracked service
and then reads back the rows to confirm they were written.

Services covered:
  - ElevenLabs Voice Agent
  - FASTAPI Backend
  - MongoDB Database Connection
  - OpenAI API
  - Kolla Integration

Prerequisites:
    - Sheet tab "System Status" exists with headers:
             Service Name | Status | Last Check (UTC) | Last Successful Operation | Error Message
  - Environment variables set:
       GOOGLE_SHEETS_CREDENTIALS (JSON string)
       GOOGLE_SPREADSHEET_ID (ID of spreadsheet)

Usage (PowerShell):
  cd F:\Zenfru-Agent\backend2\test
  python .\verify_system_status_updates.py

Output:
  Prints each service's row after success and failure injections.
"""

from __future__ import annotations

import os
import json
import sys
from pathlib import Path
from typing import Callable, Dict
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Ensure root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from services.service_status_sheet import (
    update_voice_agent_call,
    update_fastapi_backend,
    update_mongodb_transcript,
    update_openai_usage,
    update_kolla_integration,
)

SERVICES = {
    "voice": ("ElevenLabs Voice Agent", update_voice_agent_call),
    "backend": ("FASTAPI Backend", update_fastapi_backend),
    "mongodb": ("MongoDB Database Connection", update_mongodb_transcript),
    "openai": ("OpenAI API", update_openai_usage),
    "kolla": ("Kolla Integration", update_kolla_integration),
}

# Realistic success and failure detail messages per service
DETAILS = {
    "ElevenLabs Voice Agent": {
        "success": "Transcript received and stored",
        "failure": "Simulated error: transcript signature invalid"
    },
    "FASTAPI Backend": {
        "success": "Endpoint /api/health responded successfully",
        "failure": "Simulated error: /api/health timeout"
    },
    "MongoDB Database Connection": {
        "success": "Call transcript inserted into raw_webhooks",
        "failure": "Simulated error: insert failed (network)"
    },
    "OpenAI API": {
        "success": "Summarized call transcripts successfully",
        "failure": "Simulated error: OpenAI JSON parse failure"
    },
    "Kolla Integration": {
        "success": "Fetched appointments successfully",
        "failure": "Simulated error: HTTP 502 from Kolla"
    }
}


def _authorize_sheet():
    # Load .env from backend2 root if present (so JSON creds & sheet ID are available)
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    # Allow alternative file-based credential: GOOGLE_SHEETS_CREDENTIALS_FILE
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    creds_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
    if not creds_json and creds_file and Path(creds_file).exists():
        creds_json = Path(creds_file).read_text(encoding="utf-8")
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    sheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    if not creds_json or not sheet_id:
        raise RuntimeError("Missing env vars GOOGLE_SHEETS_CREDENTIALS / GOOGLE_SPREADSHEET_ID")
    creds_dict = json.loads(creds_json)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).worksheet("System Status")


def _find_row(ws, service_name: str):
    rows = ws.get_all_values()
    for idx, row in enumerate(rows[1:], start=2):
        if row and row[0] == service_name:
            return idx, row
    return None, None


FAIL_SERVICES = {"FASTAPI Backend", "OpenAI API"}  # Only these will simulate a failure


def exercise_service(service_name: str, func: Callable[[bool, str], None], ws):
    print(f"\n--- Exercising {service_name} ---")
    success_msg = DETAILS[service_name]["success"]
    # Success case
    func(True, success_msg)
    idx, row = _find_row(ws, service_name)
    print(f"After success -> Row {idx}: {row}")
    if service_name in FAIL_SERVICES:
        failure_msg = DETAILS[service_name]["failure"]
        func(False, failure_msg)
        idx, row = _find_row(ws, service_name)
        print(f"After failure -> Row {idx}: {row}")
    else:
        print("No failure simulated for this service (kept Working status).")


def main():
    try:
        ws = _authorize_sheet()
    except Exception as e:
        print(f"❌ Authorization or worksheet access failed: {e}")
        return
    print(f"✅ Connected to sheet. Timestamp: {datetime.utcnow().isoformat(timespec='seconds')} UTC")
    for key, (name, func) in SERVICES.items():
        exercise_service(name, func, ws)
    print("\nVerification complete. Confirm rows visually in the sheet.")


if __name__ == "__main__":
    main()