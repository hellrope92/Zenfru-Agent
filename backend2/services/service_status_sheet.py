"""Service Status Sheet integration.

Columns expected in the Google Sheet 'System Status':
    Service Name | Status | Last Check (UTC) | Last Successful Operation | Error Message

Environment Variables:
    GOOGLE_SHEETS_CREDENTIALS  - JSON string of service account credentials
    GOOGLE_SPREADSHEET_ID      - Target spreadsheet ID

The module exposes helper functions to update status for specific services:
    update_voice_agent_call(success, detail)
    update_fastapi_backend(success, detail)
    update_mongodb_transcript(success, detail)
    update_openai_usage(success, detail)
    update_kolla_integration(success, detail)

Each update overwrites the row for that service with latest timestamp.
- On success: sets Last Successful Operation to provided detail and clears Error Message.
- On failure: preserves prior Last Successful Operation (if present) and sets Error Message.
Success/error counters retained internally (possible future use).
"""

from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone
from typing import Dict

import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_TITLE = "System Status"  # must already exist with correct headers

_client = None
_workbook = None
_stats: Dict[str, Dict[str, float]] = {}

SERVICES = {
    "voice": "ElevenLabs Voice Agent",
    "backend": "FASTAPI Backend",
    "mongodb": "MongoDB Database Connection",
    "openai": "OpenAI API",
    "kolla": "Kolla Integration",
}


def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def _authorize():
    global _client, _workbook
    if _client and _workbook:
        return _workbook
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    sheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    if not creds_json or not sheet_id:
        raise RuntimeError("Missing GOOGLE_SHEETS_CREDENTIALS or GOOGLE_SPREADSHEET_ID")
    creds_dict = json.loads(creds_json)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    _client = gspread.authorize(creds)
    _workbook = _client.open_by_key(sheet_id)
    return _workbook


def _get_sheet():
    wb = _authorize()
    try:
        return wb.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        raise RuntimeError(f"Worksheet '{SHEET_TITLE}' not found. Run init_sheets.py first.")


def _update(service_name: str, success: bool, detail: str):
    """Core row update logic."""
    try:
        ws = _get_sheet()
        bucket = _stats.setdefault(service_name, {"succ": 0.0, "err": 0.0, "first": time.time()})
        if success:
            bucket["succ"] += 1
        else:
            bucket["err"] += 1
        # Reset after 24h
        age_hours = (time.time() - bucket["first"]) / 3600.0
        if age_hours > 24:
            bucket["succ"], bucket["err"], bucket["first"] = 0.0, 0.0, time.time()
        # Uptime no longer displayed; counters retained for potential future logic
        rows = ws.get_all_values()
        row_index = None
        prev_last_success = ""
        for idx, row in enumerate(rows[1:], start=2):
            if row and row[0] == service_name:
                row_index = idx
                # Existing column 4 (index 3) is Last Successful Operation if present
                if len(row) >= 4:
                    prev_last_success = row[3]
                break
        status_text = "Working" if success else "Error Occurred"
        last_success = detail[:140] if success else prev_last_success
        error_msg = "" if success else detail[:140]
        new_row = [
            service_name,
            status_text,
            _now_iso(),
            last_success,
            error_msg,
        ]
        if row_index:
            ws.update(f"A{row_index}:E{row_index}", [new_row])
        else:
            ws.append_row(new_row)
    except Exception as e:
        print(f"[service_status_sheet] update failed for {service_name}: {e}")


# Public helpers -------------------------------------------------------------

def update_voice_agent_call(success: bool, detail: str):
    _update(SERVICES["voice"], success, detail)


def update_fastapi_backend(success: bool, detail: str):
    _update(SERVICES["backend"], success, detail)


def update_mongodb_transcript(success: bool, detail: str):
    _update(SERVICES["mongodb"], success, detail)


def update_openai_usage(success: bool, detail: str):
    _update(SERVICES["openai"], success, detail)


def update_kolla_integration(success: bool, detail: str):
    _update(SERVICES["kolla"], success, detail)


# Convenience aggregation for backend endpoint hits ------------------------

def update_backend_endpoint(path: str, ok: bool):
    detail = f"Endpoint OK: {path}" if ok else f"Endpoint error: {path}"
    update_fastapi_backend(ok, detail)
