"""اختبارات خوارزمية التوزيع."""

from __future__ import annotations

from bot.distribute import compute_schedule

SUNDAY = 6
MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5


def test_zero_count_returns_empty():
    result = compute_schedule({SUNDAY, MONDAY}, 0, 2026, 5)
    assert result.days == []
    assert result.warning is None


def test_no_allowed_days_returns_empty_with_warning():
    result = compute_schedule(set(), 3, 2026, 5)
    assert result.days == []
    assert result.warning == "no_days"


def test_three_times_sunday_monday_may_2026():
    """Scenario from spec: Sunday + Monday allowed, 3 times in May 2026.

    May 2026: Sundays = 3,10,17,24,31 ; Mondays = 4,11,18,25.
    Available pool: [3,4,10,11,17,18,24,25,31] (9 days).
    Targets for 3 contacts in 31-day month: 5.17, 15.5, 25.83.
    Closest to 5.17 → 4 (diff 1.17)
    Closest to 15.5 → 17 (diff 1.5; 18 ties on 2.5 but 17 is closer)
    Closest to 25.83 → 25 (diff 0.83)
    """
    result = compute_schedule({SUNDAY, MONDAY}, 3, 2026, 5)
    assert result.days == [4, 17, 25]
    assert result.warning is None


def test_four_times_sunday_only_may_2026():
    """5 Sundays in May 2026 (3,10,17,24,31), pick 4 distributed evenly."""
    result = compute_schedule({SUNDAY}, 4, 2026, 5)
    assert len(result.days) == 4
    assert all(d in {3, 10, 17, 24, 31} for d in result.days)
    assert result.days == sorted(result.days)


def test_count_equals_available_uses_all():
    """5 times, only Sunday allowed in May 2026 (5 Sundays) → all of them."""
    result = compute_schedule({SUNDAY}, 5, 2026, 5)
    assert result.days == [3, 10, 17, 24, 31]
    assert result.warning is None


def test_count_exceeds_available_warns_and_uses_all():
    """6 times, only Sunday in May 2026 (5 Sundays) → all 5 + warning."""
    result = compute_schedule({SUNDAY}, 6, 2026, 5)
    assert result.days == [3, 10, 17, 24, 31]
    assert result.warning == "count_exceeds_available"


def test_one_time_all_days_allowed_picks_middle():
    """1 contact across the whole month → should land near mid-month."""
    result = compute_schedule(
        {MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY},
        1,
        2026,
        5,
    )
    assert len(result.days) == 1
    # Target = 0.5 * 31 = 15.5 → closest available day is 15 or 16
    assert result.days[0] in {15, 16}


def test_two_times_friday_only_april_2026():
    """April 2026 has 4 Fridays (3, 10, 17, 24). 2 contacts → first half + second half."""
    result = compute_schedule({FRIDAY}, 2, 2026, 4)
    assert len(result.days) == 2
    # April has 30 days. Targets: 7.5, 22.5.
    # Closest to 7.5 → 10 (diff 2.5) ; 3 is diff 4.5
    # Closest to 22.5 → 24 (diff 1.5)
    assert result.days == [10, 24]


def test_no_duplicates_when_targets_collide():
    """If targets pick the same day, the algorithm should pick distinct days."""
    # Use 3 contacts but limit available days to force collision.
    # Saturday only in May 2026: 2, 9, 16, 23, 30
    result = compute_schedule({SATURDAY}, 3, 2026, 5)
    assert len(result.days) == 3
    assert len(set(result.days)) == 3
    assert all(d in {2, 9, 16, 23, 30} for d in result.days)


def test_schedule_is_sorted():
    result = compute_schedule({SUNDAY, MONDAY, FRIDAY}, 4, 2026, 5)
    assert result.days == sorted(result.days)


def test_february_handles_short_month():
    """February 2026 has 28 days."""
    result = compute_schedule({SUNDAY}, 2, 2026, 2)
    # Sundays in Feb 2026: 1, 8, 15, 22 (4 Sundays).
    # Targets: 7, 21. Closest: 8, 22.
    assert result.days == [8, 22]


def test_february_2024_leap_year():
    """February 2024 has 29 days (leap)."""
    result = compute_schedule({MONDAY}, 1, 2024, 2)
    # Mondays in Feb 2024: 5, 12, 19, 26. Target: 14.5. Closest: 12 (diff 2.5) vs 19 (diff 4.5) → 12.
    assert result.days == [12]
