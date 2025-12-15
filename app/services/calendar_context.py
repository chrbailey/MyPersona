from datetime import datetime, timedelta
from typing import Union
import yaml

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.models import (
    CalendarContextAvailable,
    CalendarContextUnavailable,
    CalendarEvent,
    Pressure,
    Interruptibility,
    RoleSignal,
)
from app.services.llm_client import llm_client


# FIXED prompt from spec section 4.2 - DO NOT MODIFY
CALENDAR_SYSTEM_PROMPT = """You summarize calendar pressure and availability.
Return YAML only."""

CALENDAR_USER_PROMPT_TEMPLATE = """Upcoming events:
{event_list}

Return:
summary (1 sentence)
pressure: low|moderate|high
interruptibility: high|medium|low
role_signal: professional|personal|mixed
confidence: 0-1"""


def _categorize_event(title: str) -> str:
    """
    Infer category from event title.
    Strip title to just category - per spec preprocessing rules.
    """
    title_lower = title.lower()

    # Professional indicators
    professional_keywords = [
        "meeting", "call", "sync", "standup", "review", "interview",
        "presentation", "demo", "workshop", "training", "conference",
        "client", "1:1", "1-1", "sprint", "planning", "retrospective"
    ]

    # Personal indicators
    personal_keywords = [
        "doctor", "dentist", "appointment", "lunch", "dinner",
        "birthday", "anniversary", "gym", "workout", "pickup",
        "dropoff", "school", "family", "personal"
    ]

    for keyword in professional_keywords:
        if keyword in title_lower:
            return "professional_meeting"

    for keyword in personal_keywords:
        if keyword in title_lower:
            return "personal_event"

    return "event"


def _preprocess_events(events: list[dict]) -> list[CalendarEvent]:
    """
    Preprocess calendar events according to spec:
    - Strip titles beyond category inference
    - Replace names with counts
    - Remove descriptions
    """
    processed = []

    for event in events[:10]:  # Max 10 events per spec
        start = event.get("start", {})
        end = event.get("end", {})

        # Get times
        start_time = start.get("dateTime", start.get("date", ""))
        end_time = end.get("dateTime", end.get("date", ""))

        # Categorize and strip title
        title = event.get("summary", "Untitled")
        category = _categorize_event(title)

        # Count attendees (replace names with count)
        attendees = event.get("attendees", [])
        attendee_count = len(attendees)

        processed.append(CalendarEvent(
            start_time=start_time,
            end_time=end_time,
            category=category,
            attendee_count=attendee_count,
        ))

    return processed


def _format_events_for_prompt(events: list[CalendarEvent]) -> str:
    """Format preprocessed events for the LLM prompt."""
    if not events:
        return "No upcoming events"

    lines = []
    for event in events:
        line = f"- {event.category} at {event.start_time}"
        if event.attendee_count > 0:
            line += f" ({event.attendee_count} attendees)"
        lines.append(line)

    return "\n".join(lines)


def _parse_calendar_response(response: str) -> CalendarContextAvailable:
    """Parse YAML response from LLM into CalendarContextAvailable."""
    # Clean response - remove markdown code blocks if present
    response = response.strip()
    if response.startswith("```"):
        lines = response.split("\n")
        # Remove first and last lines (code block markers)
        lines = [l for l in lines if not l.startswith("```")]
        response = "\n".join(lines)

    parsed = yaml.safe_load(response)

    # Handle nested structure if present
    if "calendar_context" in parsed:
        parsed = parsed["calendar_context"]

    return CalendarContextAvailable(
        summary=parsed.get("summary", "Calendar context available"),
        pressure=Pressure(parsed.get("pressure", "moderate")),
        interruptibility=Interruptibility(parsed.get("interruptibility", "medium")),
        role_signal=RoleSignal(parsed.get("role_signal", "mixed")),
        confidence=float(parsed.get("confidence", 0.5)),
    )


async def fetch_calendar_events(credentials: Credentials) -> list[dict]:
    """
    Fetch calendar events from Google Calendar API.
    Returns events from now to +24 hours.
    """
    service = build("calendar", "v3", credentials=credentials)

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(hours=24)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=10,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])


async def get_calendar_context(
    access_token: str | None,
) -> Union[CalendarContextAvailable, CalendarContextUnavailable]:
    """
    Get calendar context using LLM micro-call.

    Args:
        access_token: OAuth access token for Google Calendar

    Returns:
        CalendarContextAvailable if successful
        CalendarContextUnavailable if calendar unavailable or error
    """
    if not access_token:
        return CalendarContextUnavailable()

    try:
        # Build credentials from token
        credentials = Credentials(token=access_token)

        # Fetch events
        events = await fetch_calendar_events(credentials)

        if not events:
            return CalendarContextUnavailable()

        # Preprocess events
        processed_events = _preprocess_events(events)

        # Format for prompt
        event_list = _format_events_for_prompt(processed_events)

        # Make LLM micro-call with FIXED prompt
        user_prompt = CALENDAR_USER_PROMPT_TEMPLATE.format(event_list=event_list)

        response = await llm_client.micro_call(
            system_prompt=CALENDAR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        return _parse_calendar_response(response)

    except (HttpError, Exception):
        # Per spec section 9: Calendar API down -> continue without calendar
        return CalendarContextUnavailable()
