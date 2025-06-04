# Zenfru-Agent

Zenfru-Agent is an AI-powered voice assistant for BrightSmile Dental Clinic, designed to handle incoming calls, schedule appointments, answer general inquiries, and assist patients in a natural, human-like manner. The agent is built to integrate with ElevenLabs Conversation AI and uses dynamic data from JSON files for real-time responses.

## Features
- Conversational AI for dental front desk tasks
- Appointment booking, rescheduling, and follow-ups
- Handles general questions using a knowledge base
- Dynamic data injection from JSON files (schedule, bookings, knowledge base)
- Customizable prompt for ElevenLabs Conversation AI
- Client-side tool simulation for integration and testing

## Project Structure
```
Zenfru-Agent/
  bookings.json           # List of all booked appointments
  data.txt                # (Optional) Additional data or notes
  knowledge_base.json     # General clinic info, FAQs, etc.
  LICENSE                 # License file
  prompt.txt              # Main prompt for the AI assistant
  schedule.json           # Weekly calendar of available appointment slots
  tools.txt               # List and description of available tools
```

## How It Works
- The AI assistant uses `prompt.txt` as its main instruction set.
- Dynamic variables like `{{schedule}}`, `{{booked_appointments}}`, and `{{knowledge_base}}` are injected at runtime from their respective JSON files.
- Tool calls (e.g., booking, rescheduling) are simulated client-side but can be connected to backend logic for production use.

## Getting Started
1. Clone the repository.
2. Update `schedule.json`, `bookings.json`, and `knowledge_base.json` with your clinic's data.
3. Integrate with ElevenLabs Conversation AI, ensuring your backend injects the latest data into the prompt.
4. Customize `prompt.txt` as needed for your clinic's workflow.

## Customization
- Edit `prompt.txt` to adjust conversation flow or add new behaviors.
- Expand tool logic in your integration layer for real-time data updates.

## License
See `LICENSE` for details.

---
For questions or support, contact the project maintainer.
