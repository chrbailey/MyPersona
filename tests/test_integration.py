import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
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
)


client = TestClient(app)


class TestHealthCheck:
    """Test health endpoint."""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestCalendarAvailability:
    """Test calendar available vs unavailable scenarios per spec section 10.2."""

    @pytest.mark.asyncio
    async def test_lens_preview_without_calendar(self):
        """Should work when calendar is unavailable."""
        with patch("app.routers.api.get_time_context") as mock_time, \
             patch("app.routers.api.get_calendar_context") as mock_cal, \
             patch("app.routers.api.get_role_guess") as mock_role:

            mock_time.return_value = TimeContext(
                current_iso="2025-12-15T14:30:00-08:00",
                time_of_day=TimeOfDay.AFTERNOON,
                weekday=True,
                business_hours=True,
                urgency_bias=0.7,
            )

            mock_cal.return_value = CalendarContextUnavailable()

            mock_role.return_value = RoleGuess(
                roles=RoleProbabilities(
                    professional=0.6,
                    personal=0.3,
                    casual=0.1,
                ),
                primary_role=RoleType.PROFESSIONAL,
                confidence=0.6,
            )

            response = client.post(
                "/lens/preview",
                json={"query": "How should I prepare for my meeting?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "calendar_context" not in data["sources_used"]
            assert "time_context" in data["sources_used"]

    @pytest.mark.asyncio
    async def test_lens_preview_with_calendar(self):
        """Should include calendar when available and above threshold."""
        with patch("app.routers.api.get_time_context") as mock_time, \
             patch("app.routers.api.get_calendar_context") as mock_cal, \
             patch("app.routers.api.get_role_guess") as mock_role:

            mock_time.return_value = TimeContext(
                current_iso="2025-12-15T14:30:00-08:00",
                time_of_day=TimeOfDay.AFTERNOON,
                weekday=True,
                business_hours=True,
                urgency_bias=0.7,
            )

            mock_cal.return_value = CalendarContextAvailable(
                summary="Client meeting in 45 minutes",
                pressure=Pressure.HIGH,
                interruptibility=Interruptibility.LOW,
                role_signal=RoleSignal.PROFESSIONAL,
                confidence=0.88,
            )

            mock_role.return_value = RoleGuess(
                roles=RoleProbabilities(
                    professional=0.72,
                    personal=0.21,
                    casual=0.07,
                ),
                primary_role=RoleType.PROFESSIONAL,
                confidence=0.72,
            )

            response = client.post(
                "/lens/preview",
                json={"query": "How should I prepare for my meeting?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "calendar_context" in data["sources_used"]


class TestPressureScenarios:
    """Test high pressure vs low pressure scenarios per spec section 10.2."""

    @pytest.mark.asyncio
    async def test_high_pressure_lens(self):
        """High pressure calendar should result in high urgency lens."""
        with patch("app.routers.api.get_time_context") as mock_time, \
             patch("app.routers.api.get_calendar_context") as mock_cal, \
             patch("app.routers.api.get_role_guess") as mock_role:

            mock_time.return_value = TimeContext(
                current_iso="2025-12-15T14:30:00-08:00",
                time_of_day=TimeOfDay.AFTERNOON,
                weekday=True,
                business_hours=True,
                urgency_bias=0.7,
            )

            mock_cal.return_value = CalendarContextAvailable(
                summary="Client meeting in 15 minutes",
                pressure=Pressure.HIGH,
                interruptibility=Interruptibility.LOW,
                role_signal=RoleSignal.PROFESSIONAL,
                confidence=0.9,
            )

            mock_role.return_value = RoleGuess(
                roles=RoleProbabilities(
                    professional=0.8,
                    personal=0.15,
                    casual=0.05,
                ),
                primary_role=RoleType.PROFESSIONAL,
                confidence=0.8,
            )

            response = client.post(
                "/lens/preview",
                json={"query": "Quick summary of best practices?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["lens"]["situational_context"]["urgency"] == "high"
            assert data["lens"]["situational_context"]["interruptibility"] == "low"

    @pytest.mark.asyncio
    async def test_low_pressure_lens(self):
        """Low pressure calendar should result in low urgency lens."""
        with patch("app.routers.api.get_time_context") as mock_time, \
             patch("app.routers.api.get_calendar_context") as mock_cal, \
             patch("app.routers.api.get_role_guess") as mock_role:

            mock_time.return_value = TimeContext(
                current_iso="2025-12-15T20:30:00-08:00",
                time_of_day=TimeOfDay.EVENING,
                weekday=False,
                business_hours=False,
                urgency_bias=0.3,
            )

            mock_cal.return_value = CalendarContextAvailable(
                summary="Casual dinner with friends tomorrow",
                pressure=Pressure.LOW,
                interruptibility=Interruptibility.HIGH,
                role_signal=RoleSignal.PERSONAL,
                confidence=0.7,
            )

            mock_role.return_value = RoleGuess(
                roles=RoleProbabilities(
                    professional=0.1,
                    personal=0.6,
                    casual=0.3,
                ),
                primary_role=RoleType.PERSONAL,
                confidence=0.6,
            )

            response = client.post(
                "/lens/preview",
                json={"query": "What should I bring to a dinner party?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["lens"]["situational_context"]["urgency"] == "low"


class TestRegenerationTriggers:
    """Test regeneration scenarios per spec sections 7 and 10.2."""

    @pytest.mark.asyncio
    async def test_over_certainty_triggers_regeneration(self):
        """Over-certainty in response should trigger regeneration."""
        with patch("app.routers.api.get_time_context") as mock_time, \
             patch("app.routers.api.get_calendar_context") as mock_cal, \
             patch("app.routers.api.get_role_guess") as mock_role, \
             patch("app.routers.api.llm_client") as mock_llm:

            mock_time.return_value = TimeContext(
                current_iso="2025-12-15T14:30:00-08:00",
                time_of_day=TimeOfDay.AFTERNOON,
                weekday=True,
                business_hours=True,
                urgency_bias=0.7,
            )

            mock_cal.return_value = CalendarContextUnavailable()

            mock_role.return_value = RoleGuess(
                roles=RoleProbabilities(
                    professional=0.6,
                    personal=0.3,
                    casual=0.1,
                ),
                primary_role=RoleType.PROFESSIONAL,
                confidence=0.6,
            )

            # First response has over-certainty, second is clean
            mock_llm.primary_call = AsyncMock(
                side_effect=[
                    "You should definitely use this approach.",
                    "This approach is generally recommended.",
                ]
            )
            mock_llm.get_model_name.return_value = "claude-3-5-sonnet"

            response = client.post(
                "/query",
                json={"query": "What approach should I use?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["regenerated"] is True
            assert "definitely" not in data["response"].lower()

    @pytest.mark.asyncio
    async def test_max_one_regeneration(self):
        """Should only regenerate maximum once per spec."""
        with patch("app.routers.api.get_time_context") as mock_time, \
             patch("app.routers.api.get_calendar_context") as mock_cal, \
             patch("app.routers.api.get_role_guess") as mock_role, \
             patch("app.routers.api.llm_client") as mock_llm:

            mock_time.return_value = TimeContext(
                current_iso="2025-12-15T14:30:00-08:00",
                time_of_day=TimeOfDay.AFTERNOON,
                weekday=True,
                business_hours=True,
                urgency_bias=0.7,
            )

            mock_cal.return_value = CalendarContextUnavailable()

            mock_role.return_value = RoleGuess(
                roles=RoleProbabilities(
                    professional=0.6,
                    personal=0.3,
                    casual=0.1,
                ),
                primary_role=RoleType.PROFESSIONAL,
                confidence=0.6,
            )

            # Both responses have drift
            mock_llm.primary_call = AsyncMock(
                side_effect=[
                    "You should definitely do this.",
                    "You're absolutely right, definitely do it.",
                ]
            )
            mock_llm.get_model_name.return_value = "claude-3-5-sonnet"

            response = client.post(
                "/query",
                json={"query": "What should I do?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["regenerated"] is True
            # Should have warning since second attempt also failed
            assert data["warning"] is not None
            # Should only have called primary_call twice (original + 1 regeneration)
            assert mock_llm.primary_call.call_count == 2
