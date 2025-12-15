from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import TimeContext, TimeOfDay


def get_time_of_day(hour: int) -> TimeOfDay:
    """
    Determine time of day bucket from hour.

    Rules from spec section 4.1:
    - morning: 05-11
    - afternoon: 11-17
    - evening: 17-22
    - night: 22-05
    """
    if 5 <= hour < 11:
        return TimeOfDay.MORNING
    elif 11 <= hour < 17:
        return TimeOfDay.AFTERNOON
    elif 17 <= hour < 22:
        return TimeOfDay.EVENING
    else:
        return TimeOfDay.NIGHT


def is_business_hours(hour: int, is_weekday: bool) -> bool:
    """Check if current time is during business hours (9-17 on weekdays)."""
    return is_weekday and 9 <= hour < 17


def calculate_urgency_bias(hour: int, is_weekday: bool, is_business_hours: bool) -> float:
    """
    Calculate urgency bias based on time context.

    Higher bias during business hours and afternoon peak.
    Lower bias during night/early morning and weekends.
    """
    base_bias = 0.5

    # Weekday adjustment
    if not is_weekday:
        base_bias -= 0.2

    # Business hours adjustment
    if is_business_hours:
        base_bias += 0.2

    # Time of day adjustment
    time_of_day = get_time_of_day(hour)
    if time_of_day == TimeOfDay.AFTERNOON:
        base_bias += 0.1
    elif time_of_day == TimeOfDay.NIGHT:
        base_bias -= 0.2
    elif time_of_day == TimeOfDay.MORNING:
        base_bias += 0.05

    # Clamp to 0-1
    return max(0.0, min(1.0, base_bias))


def get_time_context(tz_name: str = "UTC") -> TimeContext:
    """
    Get time context from system time.

    This is a zero-cost, always-available, deterministic function.
    No LLM usage, no I/O.

    Args:
        tz_name: Timezone name (e.g., "America/Los_Angeles", "UTC")

    Returns:
        TimeContext with current time information
    """
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    now = datetime.now(tz)

    hour = now.hour
    # Monday = 0, Sunday = 6
    is_weekday = now.weekday() < 5

    time_of_day = get_time_of_day(hour)
    business_hours = is_business_hours(hour, is_weekday)
    urgency_bias = calculate_urgency_bias(hour, is_weekday, business_hours)

    return TimeContext(
        current_iso=now.isoformat(),
        time_of_day=time_of_day,
        weekday=is_weekday,
        business_hours=business_hours,
        urgency_bias=round(urgency_bias, 2),
    )
