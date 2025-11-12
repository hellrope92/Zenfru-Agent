"""
Test script for call analytics system
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.call_analytics_service import get_analytics_service

# Sample payload (based on your MongoDB document)
SAMPLE_PAYLOAD = {
    "type": "post_call_transcription",
    "event_timestamp": 1762781598,
    "data": {
        "agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
        "conversation_id": "conv_test_12345",
        "status": "done",
        "transcript": [
            {"role": "agent", "message": "Hello, how can I help you?"},
            {"role": "user", "message": "I need to book an appointment"},
            {"role": "agent", "message": "Sure, let me help you with that"}
        ],
        "metadata": {
            "start_time_unix_secs": 1762781522,
            "call_duration_secs": 69,
            "termination_reason": "Call ended by remote party"
        },
        "analysis": {
            "call_successful": "success",
            "data_collection_results": {
                "reason": {
                    "value": "booking",
                    "rationale": "Test call for booking"
                }
            }
        }
    }
}

FAILURE_PAYLOAD = {
    "type": "post_call_transcription",
    "data": {
        "agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
        "conversation_id": "conv_test_failure_67890",
        "status": "done",
        "transcript": [
            {"role": "agent", "message": "Hello"},
            {"role": "user", "message": "I need receptionist"}
        ],
        "metadata": {
            "start_time_unix_secs": 1762781522,
            "call_duration_secs": 15,
            "termination_reason": "Call ended by remote party"
        },
        "analysis": {
            "call_successful": "failure",
            "data_collection_results": {
                "reason": {
                    "value": "general query",
                    "rationale": "User wanted receptionist"
                }
            }
        }
    }
}

def test_analytics():
    """Test the analytics service"""
    print("=" * 60)
    print("Testing Call Analytics Service")
    print("=" * 60)
    
    # Get service
    print("\n1. Initializing analytics service...")
    service = get_analytics_service()
    
    if not service.sheet:
        print("❌ Google Sheets not connected!")
        print("Make sure environment variables are set:")
        print("  - GOOGLE_SHEETS_CREDENTIALS")
        print("  - GOOGLE_SPREADSHEET_ID")
        return False
    
    print("✓ Service initialized")
    
    # Analyze success call
    print("\n2. Analyzing sample SUCCESS call...")
    metrics = service.analyze_call(SAMPLE_PAYLOAD)
    
    if not metrics:
        print("❌ Failed to analyze call")
        return False
    
    print("✓ Call analyzed successfully:")
    print(f"   Timestamp: {metrics['timestamp']}")
    print(f"   Conversation ID: {metrics['conversation_id']}")
    print(f"   Call Type: {metrics['call_type']}")
    print(f"   Duration: {metrics['duration_secs']} seconds")
    print(f"   Result: {'Success' if metrics['is_success'] else 'Failure'}")
    if metrics['failure_reason']:
        print(f"   Failure Reason: {metrics['failure_reason']}")
    
    # Push to sheets
    print("\n3. Pushing SUCCESS call to Google Sheets...")
    success = service.push_to_sheets(metrics)
    
    if not success:
        print("❌ Failed to push to Google Sheets")
        return False
    
    print("✓ Successfully pushed to Google Sheets!")
    
    # Test failure case
    print("\n4. Analyzing sample FAILURE call...")
    failure_metrics = service.analyze_call(FAILURE_PAYLOAD)
    
    print("✓ Failure call analyzed:")
    print(f"   Conversation ID: {failure_metrics['conversation_id']}")
    print(f"   Call Type: {failure_metrics['call_type']}")
    print(f"   Duration: {failure_metrics['duration_secs']} seconds")
    print(f"   Result: {'Success' if failure_metrics['is_success'] else 'Failure'}")
    print(f"   Failure Reason: {failure_metrics['failure_reason']}")
    
    print("\n5. Pushing FAILURE call to Google Sheets...")
    service.push_to_sheets(failure_metrics)
    print("✓ Failure case pushed to sheets")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    print(f"📊 View your data: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    print("=" * 60)
    return True

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("\nCall Analytics Test Suite\n")
    
    if not test_analytics():
        print("\n❌ Tests failed. Check configuration.")
        sys.exit(1)
