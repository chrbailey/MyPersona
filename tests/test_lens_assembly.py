import pytest
from app.services.lens_assembly import assemble_lens, lens_to_yaml
from app.models import (
    TimeContext,
    TimeOfDay,
    CalendarContextAvailable,
    CalendarContextUnavailable,
    RoleGuess,
    RoleProbabilities,
    RoleType,
    Pressure,
    Interruptibility,
    RoleSignal,
    Tone,
    Verbosity,
    Urgency,
)


@pytest.fixture
def sample_time_context():
    return TimeContext(
        current_iso="2025-12-15T14:30:00-08:00",
        time_of_day=TimeOfDay.AFTERNOON,
        weekday=True,
        business_hours=True,
        urgency_bias=0.7,
    )


@pytest.fixture
def high_pressure_calendar():
    return CalendarContextAvailable(
        summary="Client meeting in 45 minutes",
        pressure=Pressure.HIGH,
        interruptibility=Interruptibility.LOW,
        role_signal=RoleSignal.PROFESSIONAL,
        confidence=0.88,
    )


@pytest.fixture
def low_confidence_calendar():
    return CalendarContextAvailable(
        summary="Maybe something later",
        pressure=Pressure.LOW,
        interruptibility=Interruptibility.HIGH,
        role_signal=RoleSignal.MIXED,
        confidence=0.2,  # Below threshold
    )


@pytest.fixture
def professional_role_guess():
    return RoleGuess(
        roles=RoleProbabilities(
            professional=0.72,
            personal=0.21,
            casual=0.07,
        ),
        primary_role=RoleType.PROFESSIONAL,
        confidence=0.72,
    )


@pytest.fixture
def low_confidence_role_guess():
    return RoleGuess(
        roles=RoleProbabilities(
            professional=0.35,
            personal=0.33,
            casual=0.32,
        ),
        primary_role=RoleType.PROFESSIONAL,
        confidence=0.35,  # Below threshold
    )


class TestLensAssembly:
    """Test deterministic lens assembly per spec section 5."""

    def test_lens_schema_validation(
        self, sample_time_context, high_pressure_calendar, professional_role_guess
    ):
        """Lens should match schema from spec section 5.1."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=high_pressure_calendar,
            role_guess=professional_role_guess,
        )

        # Check required fields exist
        assert lens.active_role is not None
        assert lens.role_confidence is not None
        assert lens.response_preferences is not None
        assert lens.situational_context is not None
        assert lens.sources_used is not None

        # Check nested structures
        assert lens.response_preferences.tone is not None
        assert lens.response_preferences.verbosity is not None
        assert lens.response_preferences.hedging is not None

        assert lens.situational_context.time_of_day is not None
        assert lens.situational_context.urgency is not None
        assert lens.situational_context.interruptibility is not None

    def test_professional_role_mapping(
        self, sample_time_context, high_pressure_calendar, professional_role_guess
    ):
        """Professional role should map to professional tone, concise verbosity."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=high_pressure_calendar,
            role_guess=professional_role_guess,
        )

        assert lens.active_role == RoleType.PROFESSIONAL
        assert lens.response_preferences.tone == Tone.PROFESSIONAL
        assert lens.response_preferences.verbosity == Verbosity.CONCISE

    def test_high_pressure_urgency(
        self, sample_time_context, high_pressure_calendar, professional_role_guess
    ):
        """High pressure calendar should result in high urgency."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=high_pressure_calendar,
            role_guess=professional_role_guess,
        )

        assert lens.situational_context.urgency == Urgency.HIGH
        assert lens.situational_context.interruptibility == Interruptibility.LOW

    def test_calendar_below_threshold_excluded(
        self, sample_time_context, low_confidence_calendar, professional_role_guess
    ):
        """Calendar with confidence < 0.3 should be excluded."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=low_confidence_calendar,
            role_guess=professional_role_guess,
        )

        assert "calendar_context" not in lens.sources_used

    def test_role_below_threshold_excluded(
        self, sample_time_context, high_pressure_calendar, low_confidence_role_guess
    ):
        """Role with confidence < 0.4 should be excluded."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=high_pressure_calendar,
            role_guess=low_confidence_role_guess,
        )

        assert "role_guess" not in lens.sources_used

    def test_time_context_always_included(self, sample_time_context):
        """Time context should always be included."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=CalendarContextUnavailable(),
            role_guess=None,
        )

        assert "time_context" in lens.sources_used

    def test_calendar_unavailable_continues(self, sample_time_context, professional_role_guess):
        """Should continue when calendar is unavailable."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=CalendarContextUnavailable(),
            role_guess=professional_role_guess,
        )

        assert lens is not None
        assert "calendar_context" not in lens.sources_used

    def test_sources_tracking(
        self, sample_time_context, high_pressure_calendar, professional_role_guess
    ):
        """Sources used should be accurately tracked."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=high_pressure_calendar,
            role_guess=professional_role_guess,
        )

        assert "time_context" in lens.sources_used
        assert "calendar_context" in lens.sources_used
        assert "role_guess" in lens.sources_used


class TestLensToYaml:
    """Test YAML conversion."""

    def test_produces_valid_yaml(
        self, sample_time_context, high_pressure_calendar, professional_role_guess
    ):
        """Should produce valid YAML string."""
        lens = assemble_lens(
            time_context=sample_time_context,
            calendar_context=high_pressure_calendar,
            role_guess=professional_role_guess,
        )

        yaml_str = lens_to_yaml(lens)

        assert isinstance(yaml_str, str)
        assert "lens:" in yaml_str
        assert "active_role:" in yaml_str
        assert "response_preferences:" in yaml_str
        assert "situational_context:" in yaml_str
