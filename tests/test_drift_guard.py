import pytest
from app.services.drift_guard import detect_drift
from app.models import (
    Lens,
    ResponsePreferences,
    SituationalContext,
    RoleType,
    Tone,
    Verbosity,
    Hedging,
    TimeOfDay,
    Urgency,
    Interruptibility,
)


@pytest.fixture
def high_urgency_lens():
    return Lens(
        active_role=RoleType.PROFESSIONAL,
        role_confidence=0.72,
        response_preferences=ResponsePreferences(
            tone=Tone.PROFESSIONAL,
            verbosity=Verbosity.CONCISE,
            hedging=Hedging.MODERATE,
        ),
        situational_context=SituationalContext(
            time_of_day=TimeOfDay.AFTERNOON,
            urgency=Urgency.HIGH,
            interruptibility=Interruptibility.LOW,
        ),
        sources_used=["time_context", "calendar_context", "role_guess"],
    )


@pytest.fixture
def low_urgency_lens():
    return Lens(
        active_role=RoleType.CASUAL,
        role_confidence=0.5,
        response_preferences=ResponsePreferences(
            tone=Tone.CASUAL,
            verbosity=Verbosity.CONCISE,
            hedging=Hedging.MODERATE,
        ),
        situational_context=SituationalContext(
            time_of_day=TimeOfDay.EVENING,
            urgency=Urgency.LOW,
            interruptibility=Interruptibility.HIGH,
        ),
        sources_used=["time_context"],
    )


class TestOverCertaintyDetection:
    """Test over-certainty detection per spec section 7.1.A."""

    def test_detects_definitely(self, low_urgency_lens):
        response = "You should definitely use this approach."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "over_certainty"

    def test_detects_always(self, low_urgency_lens):
        response = "This always works in every situation."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "over_certainty"

    def test_detects_never(self, low_urgency_lens):
        response = "You should never do that."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "over_certainty"

    def test_detects_100_percent(self, low_urgency_lens):
        response = "This is 100% the right choice."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "over_certainty"

    def test_case_insensitive(self, low_urgency_lens):
        response = "You should DEFINITELY consider this."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True

    def test_no_false_positive_on_normal_text(self, low_urgency_lens):
        response = "This approach might work well for your needs."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is False


class TestSycophancyDetection:
    """Test sycophancy-lite detection per spec section 7.1.B."""

    def test_detects_absolutely_right(self, low_urgency_lens):
        response = "You're absolutely right about this."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "sycophancy"

    def test_detects_great_point(self, low_urgency_lens):
        response = "Great point! Let me explain further."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "sycophancy"

    def test_detects_couldnt_agree_more(self, low_urgency_lens):
        response = "I couldn't agree more with your assessment."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "sycophancy"

    def test_no_false_positive_on_agreement(self, low_urgency_lens):
        response = "I agree that this is a valid approach."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is False


class TestContextIgnoranceDetection:
    """Test context ignorance detection per spec section 7.1.C."""

    def test_detects_ignored_context_high_pressure(self, high_urgency_lens):
        """Should flag when high pressure lens but no context references."""
        response = "Here is a comprehensive overview of all the options you might consider exploring."
        result = detect_drift(response, high_urgency_lens)
        assert result.drift_detected is True
        assert result.drift_type == "ignored_context"

    def test_passes_when_context_referenced(self, high_urgency_lens):
        """Should pass when response references time pressure."""
        response = "Given the time pressure, here's a quick summary."
        result = detect_drift(response, high_urgency_lens)
        assert result.drift_detected is False

    def test_passes_with_urgency_reference(self, high_urgency_lens):
        """Should pass when response references urgency."""
        response = "Since this is urgent, I'll be concise."
        result = detect_drift(response, high_urgency_lens)
        assert result.drift_detected is False

    def test_no_check_for_low_urgency(self, low_urgency_lens):
        """Should not check context ignorance for low urgency."""
        response = "Here is a comprehensive overview of all the options."
        result = detect_drift(response, low_urgency_lens)
        assert result.drift_detected is False


class TestRegenerationModifiers:
    """Test regeneration modifiers per spec section 7.2."""

    def test_over_certainty_modifier(self, low_urgency_lens):
        response = "You should definitely do this."
        result = detect_drift(response, low_urgency_lens)
        assert result.modifier == "Express appropriate uncertainty."

    def test_sycophancy_modifier(self, low_urgency_lens):
        response = "Great point! Here's more info."
        result = detect_drift(response, low_urgency_lens)
        assert result.modifier == "Be objective. Do not mirror assumptions."

    def test_ignored_context_modifier(self, high_urgency_lens):
        response = "Here's a detailed exploration of every possibility."
        result = detect_drift(response, high_urgency_lens)
        assert result.modifier == "Explicitly consider the user's situation."
