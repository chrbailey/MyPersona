from typing import Union, Optional
import yaml

from app.models import (
    TimeContext,
    CalendarContextAvailable,
    CalendarContextUnavailable,
    RoleGuess,
    RoleProbabilities,
    RoleType,
)
from app.services.llm_client import llm_client


# FIXED prompt from spec section 4.3 - DO NOT MODIFY
ROLE_SYSTEM_PROMPT = """You infer which role best fits the user's current query and situation.
Return YAML only."""

ROLE_USER_PROMPT_TEMPLATE = """Query: {query}
Time context: {time_context}
Calendar context: {calendar_context}

Return probabilities that sum to 1."""


def _format_time_context(time_context: TimeContext) -> str:
    """Format time context for prompt."""
    return yaml.dump({
        "current_iso": time_context.current_iso,
        "time_of_day": time_context.time_of_day.value,
        "weekday": time_context.weekday,
        "business_hours": time_context.business_hours,
        "urgency_bias": time_context.urgency_bias,
    }, default_flow_style=False)


def _format_calendar_context(
    calendar_context: Union[CalendarContextAvailable, CalendarContextUnavailable]
) -> str:
    """Format calendar context for prompt."""
    if isinstance(calendar_context, CalendarContextUnavailable):
        return "unavailable"

    return yaml.dump({
        "summary": calendar_context.summary,
        "pressure": calendar_context.pressure.value,
        "interruptibility": calendar_context.interruptibility.value,
        "role_signal": calendar_context.role_signal.value,
        "confidence": calendar_context.confidence,
    }, default_flow_style=False)


def _parse_role_response(response: str) -> RoleGuess:
    """Parse YAML response from LLM into RoleGuess."""
    # Clean response - remove markdown code blocks if present
    response = response.strip()
    if response.startswith("```"):
        lines = response.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        response = "\n".join(lines)

    parsed = yaml.safe_load(response)

    # Handle nested structure if present
    if "role_guess" in parsed:
        parsed = parsed["role_guess"]

    roles_data = parsed.get("roles", {})

    # Ensure all three roles are present (per spec)
    professional = float(roles_data.get("professional", 0.33))
    personal = float(roles_data.get("personal", 0.33))
    casual = float(roles_data.get("casual", 0.34))

    # Normalize to ensure sum = 1
    total = professional + personal + casual
    if total > 0:
        professional /= total
        personal /= total
        casual /= total

    roles = RoleProbabilities(
        professional=round(professional, 2),
        personal=round(personal, 2),
        casual=round(casual, 2),
    )

    primary_role_str = parsed.get("primary_role", "professional")
    primary_role = RoleType(primary_role_str)

    confidence = float(parsed.get("confidence", 0.5))

    return RoleGuess(
        roles=roles,
        primary_role=primary_role,
        confidence=confidence,
    )


async def get_role_guess(
    query: str,
    time_context: TimeContext,
    calendar_context: Union[CalendarContextAvailable, CalendarContextUnavailable],
) -> Optional[RoleGuess]:
    """
    Get role guess using LLM micro-call.

    Args:
        query: User's query
        time_context: Time context
        calendar_context: Calendar context (available or unavailable)

    Returns:
        RoleGuess if successful, None on failure

    Per spec:
    - Must always return all 3 roles
    - No memory
    - No learning
    """
    try:
        time_ctx_str = _format_time_context(time_context)
        calendar_ctx_str = _format_calendar_context(calendar_context)

        user_prompt = ROLE_USER_PROMPT_TEMPLATE.format(
            query=query,
            time_context=time_ctx_str,
            calendar_context=calendar_ctx_str,
        )

        response = await llm_client.micro_call(
            system_prompt=ROLE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        return _parse_role_response(response)

    except Exception:
        # Per spec section 9: LLM micro-call fails -> exclude that context
        return None
