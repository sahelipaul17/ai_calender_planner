import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found")

client = OpenAI(api_key=API_KEY, base_url="https://openrouter.ai/api/v1")


# Event schema
class CalendarEvent(BaseModel):
    name: str
    start_time: datetime
    participants: list[str]


# In-memory calendar storage
calendar_db: list[CalendarEvent] = []


def extract_event(user_text: str) -> CalendarEvent | None:
    """Ask LLM to extract structured event data with datetime."""
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content":
             "Extract event info and return ONLY valid JSON. "
             "Format must be: {\"name\":..., \"start_time\": \"YYYY-MM-DD HH:MM\", \"participants\": [...]}"},
            {"role": "user", "content": user_text}
        ],
    )

    raw_output = response.choices[0].message.content
    try:
        event = CalendarEvent.model_validate_json(raw_output)
        return event
    except ValidationError as e:
        print("Validation error:", e)
        print("Raw output:", raw_output)
        return None


def is_slot_free(new_event: CalendarEvent, duration: timedelta = timedelta(hours=1)) -> bool:
    """Check if the given event time overlaps with existing ones."""
    new_start = new_event.start_time
    new_end = new_start + duration

    for e in calendar_db:
        existing_start = e.start_time
        existing_end = existing_start + duration

        if not (new_end <= existing_start or new_start >= existing_end):
            return False  # Overlap detected
    return True


def add_event(user_text: str, allow_plan: bool = True):
    """Extract event and schedule if possible."""
    event = extract_event(user_text)
    if not event:
        print("Could not parse event.")
        return

    if is_slot_free(event):
        calendar_db.append(event)
        print(f"✅ Event added: {event.name} at {event.start_time} with {', '.join(event.participants)}")
    else:
        if allow_plan:
            print(f"⚠️ Slot already booked around {event.start_time}.")
            suggest_alternative(event)
        else:
            print(f"Could not add, slot taken at {event.start_time}.")


def suggest_alternative(event: CalendarEvent, duration: timedelta = timedelta(hours=1)):
    """Suggest next free time slots."""
    new_start = event.start_time
    for i in range(1, 5):  # suggest next 5 possible hours
        candidate_start = new_start + timedelta(hours=i)
        candidate_event = CalendarEvent(name=event.name, start_time=candidate_start, participants=event.participants)
        if is_slot_free(candidate_event, duration):
            print(f"👉 Suggested alternative: {candidate_start}")
            break


def view_events():
    """List all events in the calendar."""
    if not calendar_db:
        print("📭 No events scheduled.")
        return
    for e in sorted(calendar_db, key=lambda x: x.start_time):
        print(f"- {e.name} at {e.start_time.strftime('%Y-%m-%d %H:%M')} with {', '.join(e.participants)}")

#test
add_event("Alice and Bob are going to a science fair on 2025-09-19 17:00.")
add_event("Team meeting with Carol on 2025-09-19 17:30.")  # clash
add_event("Dinner with Emma on 2025-09-20 20:00.")
view_events()
