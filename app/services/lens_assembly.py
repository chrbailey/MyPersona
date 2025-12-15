from typing import Union, Optional
import yaml

from app.config import settings
from app.models import (
    TimeContext,
    CalendarContextAvailable,
    CalendarContextUnavailable,
    RoleGuess,
    RoleType,
    Lens,
    ResponsePreferences,
    SituationalContext,
    Tone,
    Verbosity,
    Hedging,
    Urgency,
    Pressure,
    Interruptibility,
)


# Mapping rules from spec section 5.2 - DETERMINISTIC
ROLE_TO_TONE = {
    RoleType.PROFESSIONAL: Tone.PROFESSIONAL,
    RoleType.PERSONAL: Tone.WARM,
    RoleType.CASUAL: Tone.CASUAL,
}

ROLE_TO_VERBOSITY = {
    RoleType.PROFESSIONAL: Verbosity.CONCISE,
    RoleType.PERSONAL: Verbosity.BALANCED,
    RoleType.CASUAL: Verbosity.CONCISE,
}

PRESSURE_TO_URGENCY = {
    Pressure.LOW: Urgency.LOW,
    Pressure.MODERATE: Urgency.MEDIUM,
    Pressure.HIGH: Urgency.HIGH,
}


def _determine_hedging(role_confidence: float) -> Hedging:
    """
    Determine hedging level based on role confidence.
    Higher confidence = less hedging needed.
    """
    if role_confidence >= 0.7:
        return Hedging.LOW
    elif role_confidence >= 0.5:
        return Hedging.MODERATE
    else:
        return Hedging.HIGH


def assemble_lens(
    time_context: TimeContext,
    calendar_context: Union[CalendarContextAvailable, CalendarContextUnavailable],
    role_guess: Optional[RoleGuess],
) -> Lens:
    """
    Assemble the lens from context services.

    This is DETERMINISTIC - no ML, no learning.

    Inclusion logic from spec section 5.3:
    - include_calendar = calendar_confidence >= 0.3
    - include_role = role_confidence >= 0.4
    - Time context is always included

    Args:
        time_context: Time context (always included)
        calendar_context: Calendar context (included if confidence >= 0.3)
        role_guess: Role guess (included if confidence >= 0.4)

    Returns:
        Assembled Lens
    """
    sources_used = ["time_context"]

    # Determine if calendar should be included
    include_calendar = (
        isinstance(calendar_context, CalendarContextAvailable)
        and calendar_context.confidence >= settings.calendar_confidence_threshold
    )

    if include_calendar:
        sources_used.append("calendar_context")

    # Determine if role should be included
    include_role = (
        role_guess is not None
        and role_guess.confidence >= settings.role_confidence_threshold
    )

    if include_role:
        sources_used.append("role_guess")

    # Determine active role
    if include_role and role_guess:
        active_role = role_guess.primary_role
        role_confidence = role_guess.confidence
    else:
        # Default to professional during business hours, casual otherwise
        if time_context.business_hours:
            active_role = RoleType.PROFESSIONAL
        else:
            active_role = RoleType.CASUAL
        role_confidence = 0.5  # Default confidence

    # Build response preferences using mapping rules
    response_preferences = ResponsePreferences(
        tone=ROLE_TO_TONE[active_role],
        verbosity=ROLE_TO_VERBOSITY[active_role],
        hedging=_determine_hedging(role_confidence),
    )

    # Determine urgency and interruptibility
    if include_calendar and isinstance(calendar_context, CalendarContextAvailable):
        urgency = PRESSURE_TO_URGENCY[calendar_context.pressure]
        interruptibility = calendar_context.interruptibility
    else:
        # Default based on time context
        if time_context.urgency_bias >= 0.7:
            urgency = Urgency.HIGH
        elif time_context.urgency_bias >= 0.4:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        # Default interruptibility based on business hours
        if time_context.business_hours:
            interruptibility = Interruptibility.MEDIUM
        else:
            interruptibility = Interruptibility.HIGH

    situational_context = SituationalContext(
        time_of_day=time_context.time_of_day,
        urgency=urgency,
        interruptibility=interruptibility,
    )

    return Lens(
        active_role=active_role,
        role_confidence=role_confidence,
        response_preferences=response_preferences,
        situational_context=situational_context,
        sources_used=sources_used,
    )


def lens_to_yaml(lens: Lens) -> str:
    """
    Convert Lens to YAML string for injection into LLM prompt.
    """
    lens_dict = {
        "lens": {
            "active_role": lens.active_role.value,
            "role_confidence": lens.role_confidence,
            "response_preferences": {
                "tone": lens.response_preferences.tone.value,
                "verbosity": lens.response_preferences.verbosity.value,
                "hedging": lens.response_preferences.hedging.value,
            },
            "situational_context": {
                "time_of_day": lens.situational_context.time_of_day.value,
                "urgency": lens.situational_context.urgency.value,
                "interruptibility": lens.situational_context.interruptibility.value,
            },
            "sources_used": lens.sources_used,
        }
    }

    return yaml.dump(lens_dict, default_flow_style=False, sort_keys=False)
