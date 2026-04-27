"""خوارزمية توزيع التواصلات على أيام الشهر بتباعد متوازن."""

from __future__ import annotations

import calendar
from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleResult:
    days: list[int]
    warning: str | None = None


def compute_schedule(
    allowed_weekdays: set[int],
    count: int,
    year: int,
    month: int,
) -> ScheduleResult:
    """
    Compute the monthly schedule for one relative.

    Args:
        allowed_weekdays: Set of Python weekday numbers (Mon=0 ... Sun=6).
        count: Desired number of contacts in the month.
        year: Calendar year.
        month: Calendar month (1-12).

    Returns:
        ScheduleResult with sorted day numbers and optional warning.
    """
    if count <= 0:
        return ScheduleResult(days=[])

    if not allowed_weekdays:
        return ScheduleResult(
            days=[],
            warning="no_days",
        )

    days_in_month = calendar.monthrange(year, month)[1]

    available_days = [
        day
        for day in range(1, days_in_month + 1)
        if _weekday(year, month, day) in allowed_weekdays
    ]

    if not available_days:
        return ScheduleResult(days=[], warning="no_days")

    if count >= len(available_days):
        return ScheduleResult(
            days=sorted(available_days),
            warning=(
                "count_exceeds_available"
                if count > len(available_days)
                else None
            ),
        )

    targets = [
        (i + 0.5) * days_in_month / count for i in range(count)
    ]

    chosen: set[int] = set()
    schedule: list[int] = []

    for target in targets:
        candidate = _pick_closest_unused(target, available_days, chosen)
        if candidate is not None:
            chosen.add(candidate)
            schedule.append(candidate)

    return ScheduleResult(days=sorted(schedule))


def _pick_closest_unused(
    target: float,
    available: list[int],
    used: set[int],
) -> int | None:
    """Return the closest available day to the target that is not already used."""
    candidates = [d for d in available if d not in used]
    if not candidates:
        return None
    return min(candidates, key=lambda d: (abs(d - target), d))


def _weekday(year: int, month: int, day: int) -> int:
    """Return Python weekday number (Mon=0 ... Sun=6) for a given date."""
    import datetime

    return datetime.date(year, month, day).weekday()
