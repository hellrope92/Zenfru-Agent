"""
Script to initialize Google Sheets with headers
Run this once to set up your spreadsheet
"""
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def init_sheets():
    """Initialize Google Sheets with proper headers"""
    try:
        # Get credentials
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        if not creds_json:
            print("❌ GOOGLE_SHEETS_CREDENTIALS environment variable not set")
            return False
        
        creds_dict = json.loads(creds_json)
        
        # Authenticate
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Open spreadsheet
        spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
        if not spreadsheet_id:
            print("❌ GOOGLE_SPREADSHEET_ID environment variable not set")
            return False
        
        sheet = client.open_by_key(spreadsheet_id).sheet1
        
        # Check if headers already exist
        existing = sheet.row_values(1)
        if existing:
            print(f"⚠️  Sheet already has data in row 1: {existing}")
            response = input("Do you want to overwrite? (yes/no): ")
            if response.lower() != "yes":
                print("Cancelled")
                return False
        
        # Set headers
        headers = [
            "Timestamp",
            "Conversation ID", 
            "Call Type",
            "Call Status",
            "Duration (sec)",
            "Result",
            "Failure Reason",
            "Call Summary"
        ]
        
        sheet.update('A1:H1', [headers])
        
        # Format header row (bold)
        sheet.format('A1:H1', {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
        })
        
        print("✅ Google Sheets initialized successfully!")
        print(f"📊 Spreadsheet URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    init_sheets()
