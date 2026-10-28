"""
hours.py
========
:class:`WeeklyHours` stores opening or working hours for each day of the week.

It is used both for department operating hours and for the working hours
of individual doctors and staff, so the logic lives in one place.
"""

from datetime import datetime, time
from typing import Dict, List, Optional, Tuple

from .exceptions import ValidationError

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


class WeeklyHours:
    """Opening/working hours keyed by weekday (Monday = 0 ... Sunday = 6)."""

    def __init__(self) -> None:
        # Private dictionary: weekday -> (start time, end time)
        self._hours: Dict[int, Tuple[time, time]] = {}

    # ------------------------------------------------------------------ #
    # Factory helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def weekdays(cls, start: str, end: str) -> "WeeklyHours":
        """Create hours that repeat Monday to Friday, e.g. ``("08:00", "17:00")``."""
        hours = cls()
        for day in range(5):
            hours.set_day(day, start, end)
        return hours

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    def set_day(self, weekday: int, start: str, end: str) -> None:
        """Set hours for one weekday using ``"HH:MM"`` strings."""
        if weekday not in range(7):
            raise ValidationError("Weekday must be between 0 (Mon) and 6 (Sun).")
        start_t = time.fromisoformat(start)
        end_t = time.fromisoformat(end)
        if start_t >= end_t:
            raise ValidationError("Start time must be earlier than end time.")
        self._hours[weekday] = (start_t, end_t)

    def close_day(self, weekday: int) -> None:
        """Mark a weekday as closed / not working."""
        self._hours.pop(weekday, None)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def hours_for(self, weekday: int) -> Optional[Tuple[time, time]]:
        """Return ``(start, end)`` for the weekday or ``None`` if closed."""
        return self._hours.get(weekday)

    def covers(self, start: datetime, end: datetime) -> bool:
        """Return True if the whole period ``start``-``end`` lies within the hours."""
        if start.date() != end.date():
            return False
        day_hours = self.hours_for(start.weekday())
        if day_hours is None:
            return False
        open_t, close_t = day_hours
        return open_t <= start.time() and end.time() <= close_t

    def describe(self) -> List[str]:
        """Return human-readable lines such as ``"Monday: 08:00-17:00"``."""
        lines = []
        for day, name in enumerate(DAY_NAMES):
            span = self._hours.get(day)
            text = f"{span[0]:%H:%M}-{span[1]:%H:%M}" if span else "Closed"
            lines.append(f"{name}: {text}")
        return lines

    def __repr__(self) -> str:
        return f"WeeklyHours({len(self._hours)} working days)"
