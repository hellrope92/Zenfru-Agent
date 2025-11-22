from pymongo import MongoClient
from datetime import datetime
from zoneinfo import ZoneInfo
import os

# Connect to MongoDB
mongo_uri = os.getenv('MONGODB_CONNECTION_STRING')
client = MongoClient(mongo_uri)
db = client['calls']

# Correct payload structure matching webhook format
payload = {
    "type": "post_call_transcription",
    "event_timestamp": 1763759979,
    "data": {
        "agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
        "conversation_id": "conv_1301kam4jyjeeqs8gwzmt62k2e3e",
        "status": "done",
        "user_id": None,
        "branch_id": None,
        "transcript": [
            {
                "role": "agent",
                "agent_metadata": {
                    "agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
                    "branch_id": None,
                    "workflow_node_id": None
                },
                "message": "Hey there, thanks for calling Dental Associates of Jersey City. I'm Alexis, How can I help you today?",
                "multivoice_message": None,
                "tool_calls": [],
                "tool_results": [],
                "feedback": None,
                "llm_override": None,
                "time_in_call_secs": 0,
                "conversation_turn_metrics": {
                    "metrics": {
                        "convai_tts_service_ttfb": {
                            "elapsed_time": 0.3345111159997032
                        }
                    }
                },
                "rag_retrieval_info": None,
                "llm_usage": None,
                "interrupted": False,
                "original_message": None,
                "source_medium": None
            }
        ],
        "metadata": {
            "start_time_unix_secs": 1763759979,
            "accepted_time_unix_secs": 1763759979,
            "call_duration_secs": 12,
            "cost": 84,
            "deletion_settings": {
                "deletion_time_unix_secs": None,
                "deleted_logs_at_time_unix_secs": None,
                "deleted_audio_at_time_unix_secs": None,
                "deleted_transcript_at_time_unix_secs": None,
                "delete_transcript_and_pii": False,
                "delete_audio": False
            },
            "feedback": {
                "type": None,
                "overall_score": None,
                "likes": 0,
                "dislikes": 0,
                "rating": None,
                "comment": None
            },
            "authorization_method": "signed_url",
            "charging": {
                "dev_discount": False,
                "is_burst": False,
                "tier": "creator",
                "llm_usage": {
                    "irreversible_generation": {"model_usage": {}},
                    "initiated_generation": {"model_usage": {}}
                },
                "llm_price": 0.0,
                "llm_charge": 0,
                "call_charge": 84,
                "free_minutes_consumed": 0.0,
                "free_llm_dollars_consumed": 0.0
            },
            "phone_call": {
                "direction": "inbound",
                "phone_number_id": "phnum_01k0h6rdwqf5vbetjwew6ka32b",
                "agent_number": "+12018774358",
                "external_number": "+12523960448",
                "type": "twilio",
                "stream_sid": "MZ056ece2b26b9446185a99b74f7572277",
                "call_sid": "CA15884136fed840d807968d7c83b21ba4"
            },
            "batch_call": None,
            "termination_reason": "Call ended by remote party",
            "error": None,
            "warnings": ["Evaluation could not determine if conversation goals were met."],
            "main_language": "en",
            "rag_usage": {
                "usage_count": 0,
                "embedding_model": "e5_mistral_7b_instruct"
            },
            "text_only": False,
            "features_usage": {
                "language_detection": {"enabled": True, "used": False},
                "transfer_to_agent": {"enabled": False, "used": False},
                "transfer_to_number": {"enabled": False, "used": False},
                "multivoice": {"enabled": False, "used": False},
                "dtmf_tones": {"enabled": True, "used": False},
                "external_mcp_servers": {"enabled": False, "used": False},
                "pii_zrm_workspace": False,
                "pii_zrm_agent": False,
                "tool_dynamic_variable_updates": {"enabled": False, "used": False},
                "is_livekit": False,
                "voicemail_detection": {"enabled": False, "used": False},
                "workflow": {
                    "enabled": False,
                    "tool_node": {"enabled": False, "used": False},
                    "standalone_agent_node": {"enabled": False, "used": False},
                    "phone_number_node": {"enabled": False, "used": False},
                    "end_node": {"enabled": False, "used": False}
                },
                "agent_testing": {
                    "enabled": False,
                    "tests_ran_after_last_modification": False,
                    "tests_ran_in_last_7_days": False
                }
            },
            "eleven_assistant": {"is_eleven_assistant": False},
            "initiator_id": None,
            "conversation_initiation_source": "twilio",
            "conversation_initiation_source_version": None,
            "timezone": "America/New_York",
            "initiation_trigger": {"trigger_type": "default"},
            "async_metadata": None,
            "whatsapp": None,
            "agent_created_from": "unknown",
            "agent_last_updated_from": "ui"
        },
        "analysis": {
            "evaluation_criteria_results": {
                "zenfrueval": {
                    "criteria_id": "zenfrueval",
                    "result": "unknown",
                    "rationale": "The transcript is too short to determine if the AI assistant achieved the caller's goal, as it only contains the initial greeting."
                }
            },
            "data_collection_results": {
                "number": {
                    "data_collection_id": "number",
                    "value": None,
                    "json_schema": {
                        "type": "string",
                        "description": "phone number of the patient if provided",
                        "enum": None,
                        "is_system_provided": False,
                        "dynamic_variable": "",
                        "constant_value": ""
                    },
                    "rationale": "The conversation does not contain any phone number for the patient. Therefore, it is not possible to extract the data."
                },
                "reason": {
                    "data_collection_id": "reason",
                    "value": None,
                    "json_schema": {
                        "type": "string",
                        "description": "reason for the patient to call(booking,rescheduling,confirmation,general query)",
                        "enum": None,
                        "is_system_provided": False,
                        "dynamic_variable": "",
                        "constant_value": ""
                    },
                    "rationale": "The user's reason for calling is not explicitly stated in the provided conversation. The agent asks 'How can I help you today?', which is an open-ended question that doesn't reveal the purpose of the call."
                },
                "name": {
                    "data_collection_id": "name",
                    "value": None,
                    "json_schema": {
                        "type": "string",
                        "description": "name of the patient if given.",
                        "enum": None,
                        "is_system_provided": False,
                        "dynamic_variable": "",
                        "constant_value": ""
                    },
                    "rationale": "The transcript does not contain the name of a patient. The agent introduces themselves, but no patient name is mentioned."
                }
            },
            "call_successful": "unknown",
            "transcript_summary": "Alexis, representing Dental Associates of Jersey City, greeted the caller and offered assistance.\n",
            "call_summary_title": "Dental Associates greeting"
        },
        "conversation_initiation_client_data": {
            "conversation_config_override": {
                "turn": None,
                "tts": None,
                "conversation": None,
                "agent": None
            },
            "custom_llm_extra_body": {},
            "user_id": None,
            "source_info": {"source": None, "version": None},
            "dynamic_variables": {
                "system__agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
                "system__current_agent_id": "agent_3101k1e6xrv2f4eb0xz6nbbrz035",
                "system__conversation_id": "conv_1301kam4jyjeeqs8gwzmt62k2e3e",
                "system__caller_id": "+12523960448",
                "system__called_number": "+12018774358",
                "system__call_duration_secs": 12,
                "system__time_utc": "2025-11-21T21:19:51.877690+00:00",
                "system__time": "Friday, 16:19 21 November 2025",
                "system__timezone": "America/New_York",
                "system__call_sid": "CA15884136fed840d807968d7c83b21ba4"
            }
        }
    }
}

# Use timestamp from the call
call_time = datetime.fromtimestamp(1763759979, tz=ZoneInfo("UTC"))

# Insert into MongoDB
result = db.raw_webhooks.insert_one({
    "received_at_utc": call_time,
    "payload": payload
})

print(f"✅ Transcript inserted successfully!")
print(f"Document ID: {result.inserted_id}")
print(f"Call time (UTC): {call_time}")
print(f"Call time (EST): {call_time.astimezone(ZoneInfo('America/New_York'))}")
print(f"Phone number: +12523960448")
