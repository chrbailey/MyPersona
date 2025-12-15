import re
from typing import Optional

from app.models import Lens, DriftResult, Urgency


# Detection rules from spec section 7.1

# A. Over-Certainty regex
OVER_CERTAINTY_PATTERN = re.compile(r"\b(definitely|always|never|100%)\b", re.IGNORECASE)

# B. Sycophancy-Lite phrases
SYCOPHANCY_PHRASES = [
    "you're absolutely right",
    "great point",
    "couldn't agree more",
]

# C. Context keywords to check for high-pressure situations
CONTEXT_KEYWORDS = [
    "time",
    "pressure",
    "urgent",
    "urgency",
    "soon",
    "quickly",
    "brief",
    "concise",
    "busy",
    "meeting",
    "deadline",
]


def _check_over_certainty(response: str) -> bool:
    """Check for over-certainty phrases."""
    return bool(OVER_CERTAINTY_PATTERN.search(response))


def _check_sycophancy(response: str) -> bool:
    """Check for sycophancy-lite phrases."""
    response_lower = response.lower()
    return any(phrase in response_lower for phrase in SYCOPHANCY_PHRASES)


def _check_context_ignorance(response: str, lens: Lens) -> bool:
    """
    Check if response ignores context when lens indicates high pressure.

    Per spec: Response does not reference time pressure, role, or urgency
    when lens indicates high pressure.
    """
    # Only check if lens indicates high urgency
    if lens.situational_context.urgency != Urgency.HIGH:
        return False

    response_lower = response.lower()

    # Check if any context keywords are present
    has_context_reference = any(
        keyword in response_lower for keyword in CONTEXT_KEYWORDS
    )

    # If high pressure but no context references, flag as ignored
    return not has_context_reference


def detect_drift(response: str, lens: Lens) -> DriftResult:
    """
    Detect drift/quality issues in LLM response.

    Only checks the three rules from spec section 7.1:
    A. Over-Certainty
    B. Sycophancy-Lite
    C. Context Ignorance (only when high pressure)

    Args:
        response: LLM response to check
        lens: The lens used for context

    Returns:
        DriftResult indicating if drift was detected and what type
    """
    # Check A: Over-Certainty
    if _check_over_certainty(response):
        return DriftResult(
            drift_detected=True,
            drift_type="over_certainty",
            modifier="Express appropriate uncertainty.",
        )

    # Check B: Sycophancy-Lite
    if _check_sycophancy(response):
        return DriftResult(
            drift_detected=True,
            drift_type="sycophancy",
            modifier="Be objective. Do not mirror assumptions.",
        )

    # Check C: Context Ignorance
    if _check_context_ignorance(response, lens):
        return DriftResult(
            drift_detected=True,
            drift_type="ignored_context",
            modifier="Explicitly consider the user's situation.",
        )

    return DriftResult(drift_detected=False)


def get_regeneration_prompt_modifier(drift_result: DriftResult) -> Optional[str]:
    """
    Get the prompt modifier for regeneration based on drift type.

    From spec section 7.2 - regeneration modifiers.

    Returns:
        Modifier string to append to system prompt, or None if no drift
    """
    return drift_result.modifier
