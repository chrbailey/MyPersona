import pytest
from app.services.time_context import (
    get_time_of_day,
    is_business_hours,
    calculate_urgency_bias,
    get_time_context,
)
from app.models import TimeOfDay


class TestGetTimeOfDay:
    """Test time bucket correctness per spec section 4.1."""

    def test_morning_5am(self):
        assert get_time_of_day(5) == TimeOfDay.MORNING

    def test_morning_10am(self):
        assert get_time_of_day(10) == TimeOfDay.MORNING

    def test_afternoon_11am(self):
        assert get_time_of_day(11) == TimeOfDay.AFTERNOON

    def test_afternoon_4pm(self):
        assert get_time_of_day(16) == TimeOfDay.AFTERNOON

    def test_evening_5pm(self):
        assert get_time_of_day(17) == TimeOfDay.EVENING

    def test_evening_9pm(self):
        assert get_time_of_day(21) == TimeOfDay.EVENING

    def test_night_10pm(self):
        assert get_time_of_day(22) == TimeOfDay.NIGHT

    def test_night_midnight(self):
        assert get_time_of_day(0) == TimeOfDay.NIGHT

    def test_night_4am(self):
        assert get_time_of_day(4) == TimeOfDay.NIGHT


class TestIsBusinessHours:
    """Test business hours detection."""

    def test_weekday_9am(self):
        assert is_business_hours(9, is_weekday=True) is True

    def test_weekday_4pm(self):
        assert is_business_hours(16, is_weekday=True) is True

    def test_weekday_5pm(self):
        assert is_business_hours(17, is_weekday=True) is False

    def test_weekday_8am(self):
        assert is_business_hours(8, is_weekday=True) is False

    def test_weekend_noon(self):
        assert is_business_hours(12, is_weekday=False) is False


class TestUrgencyBias:
    """Test urgency bias calculation."""

    def test_urgency_in_range(self):
        """Urgency bias should always be between 0 and 1."""
        for hour in range(24):
            for is_weekday in [True, False]:
                for is_bh in [True, False]:
                    bias = calculate_urgency_bias(hour, is_weekday, is_bh)
                    assert 0.0 <= bias <= 1.0

    def test_business_hours_higher_urgency(self):
        """Business hours should have higher urgency than non-business hours."""
        bh_urgency = calculate_urgency_bias(12, is_weekday=True, is_business_hours=True)
        non_bh_urgency = calculate_urgency_bias(12, is_weekday=True, is_business_hours=False)
        assert bh_urgency > non_bh_urgency


class TestGetTimeContext:
    """Test full time context generation."""

    def test_returns_valid_time_context(self):
        context = get_time_context()

        assert context.current_iso is not None
        assert context.time_of_day in TimeOfDay
        assert isinstance(context.weekday, bool)
        assert isinstance(context.business_hours, bool)
        assert 0.0 <= context.urgency_bias <= 1.0

    def test_with_timezone(self):
        context = get_time_context("America/Los_Angeles")
        assert context.current_iso is not None

    def test_with_invalid_timezone_falls_back(self):
        """Invalid timezone should fall back to UTC."""
        context = get_time_context("Invalid/Timezone")
        assert context.current_iso is not None
