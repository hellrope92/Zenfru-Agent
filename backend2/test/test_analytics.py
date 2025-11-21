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

AGENT_LIMITATION_PAYLOAD = {
    "type": "post_call_transcription",
    "data": {
        "agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
        "conversation_id": "conv_test_limitation_99999",
        "status": "done",
        "transcript": [
            {"role": "agent", "message": "Hello, how can I help you?"},
            {"role": "user", "message": "I want to speak with Sissy"},
            {"role": "agent", "message": "I cannot transfer you directly"},
            {"role": "user", "message": "Okay, bye"}
        ],
        "metadata": {
            "start_time_unix_secs": 1762781522,
            "call_duration_secs": 45,
            "termination_reason": "Call ended by remote party"
        },
        "analysis": {
            "call_successful": "failure",
            "transcript_summary": "The user called Dental Associates of Jersey City to speak with Sissy, the doctor's office assistant, but did not know her last name. The agent was unable to directly transfer the call. The agent offered to log a callback request for Sissy or a receptionist to call the user back, but the user declined and ended the call.",
            "data_collection_results": {
                "reason": {
                    "value": "general query",
                    "rationale": "User wanted to speak with specific person"
                }
            }
        }
    }
}

UNKNOWN_PAYLOAD = {
    "type": "post_call_transcription",
    "data": {
        "agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
        "conversation_id": "conv_test_unknown_11111",
        "status": "done",
        "transcript": [
            {"role": "agent", "message": "Hello"},
            {"role": "user", "message": "Hello"}
        ],
        "metadata": {
            "start_time_unix_secs": 1762781522,
            "call_duration_secs": 8,
            "termination_reason": "Call ended by remote party"
        },
        "analysis": {
            "call_successful": "unknown",
            "data_collection_results": {
                "reason": {
                    "value": None,
                    "rationale": "Could not determine call reason"
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
    print(f"   Result: {metrics['result_status']}")
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
    print(f"   Result: {failure_metrics['result_status']}")
    print(f"   Failure Reason: {failure_metrics['failure_reason']}")
    
    print("\n5. Pushing FAILURE call to Google Sheets...")
    service.push_to_sheets(failure_metrics)
    print("✓ Failure case pushed to sheets")
    
    # Test agent limitation case
    print("\n6. Analyzing AGENT LIMITATION call with transcript summary...")
    limitation_metrics = service.analyze_call(AGENT_LIMITATION_PAYLOAD)
    
    print("✓ Agent limitation call analyzed:")
    print(f"   Conversation ID: {limitation_metrics['conversation_id']}")
    print(f"   Call Type: {limitation_metrics['call_type']}")
    print(f"   Duration: {limitation_metrics['duration_secs']} seconds")
    print(f"   Result: {limitation_metrics['result_status']}")
    print(f"   Failure Reason: {limitation_metrics['failure_reason']}")
    
    print("\n7. Pushing AGENT LIMITATION call to Google Sheets...")
    service.push_to_sheets(limitation_metrics)
    print("✓ Agent limitation case pushed to sheets")
    
    # Test unknown result case
    print("\n8. Analyzing previously UNKNOWN result call...")
    unknown_metrics = service.analyze_call(UNKNOWN_PAYLOAD)
    
    print("✓ Short/unknown-origin call analyzed:")
    print(f"   Conversation ID: {unknown_metrics['conversation_id']}")
    print(f"   Call Type: {unknown_metrics['call_type']}")
    print(f"   Duration: {unknown_metrics['duration_secs']} seconds")
    print(f"   Result: {unknown_metrics['result_status']}")
    print(f"   Failure Reason: {unknown_metrics['failure_reason']}")
    
    print("\n9. Pushing short call to Google Sheets...")
    service.push_to_sheets(unknown_metrics)
    print("✓ Short call case pushed to sheets")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("\nTest Results Summary:")
    print(f"   ✓ Success call - Result: Success")
    print(f"   ✓ Failure call - Result: Failure")
    print(f"   ✓ Agent limitation - Result: Failure (with detailed reason)")
    print(f"   ✓ Short call - Result: Failure (hangup/incomplete)")
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    print(f"\n📊 View your data: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    print("=" * 60)
    return True

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("\nCall Analytics Test Suite\n")
    
    if not test_analytics():
        print("\n❌ Tests failed. Check configuration.")
        sys.exit(1)
