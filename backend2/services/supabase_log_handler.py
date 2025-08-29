import logging
import requests
import os
import json

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

class SupabaseLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        payload = {
            "service_name": "zenfru-agent",
            "log_level": record.levelname,
            "message": log_entry
        }
        headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json"
        }
        try:
            requests.post(
                f"{SUPABASE_URL}/rest/v1/logs",
                headers=headers,
                data=json.dumps(payload),
                timeout=2
            )
        except Exception as e:
            pass
