"""Unit tests for the interval arithmetic."""
from __future__ import annotations

from datetime import date

import pytest

from custom_components.routine_calendar.recurrence import add_interval


class TestDays:
    def test_single_day(self):
        assert add_interval(date(2026, 5, 17), 1, "days") == date(2026, 5, 18)

    def test_many_days_crossing_month(self):
        assert add_interval(date(2026, 1, 30), 5, "days") == date(2026, 2, 4)


class TestWeeks:
    def test_one_week(self):
        assert add_interval(date(2026, 5, 17), 1, "weeks") == date(2026, 5, 24)

    def test_user_scenario_saturday_to_sunday(self):
        """User example: due Saturday but completed Sunday — next due is the following Sunday."""
        completed_sunday = date(2026, 5, 17)
        assert add_interval(completed_sunday, 1, "weeks") == date(2026, 5, 24)


class TestMonths:
    def test_simple(self):
        assert add_interval(date(2026, 1, 15), 1, "months") == date(2026, 2, 15)

    def test_year_wrap(self):
        assert add_interval(date(2026, 12, 1), 1, "months") == date(2027, 1, 1)

    def test_clamps_to_end_of_short_month(self):
        # Jan 31 + 1 month → Feb 28 (non-leap year)
        assert add_interval(date(2026, 1, 31), 1, "months") == date(2026, 2, 28)

    def test_clamps_to_end_of_short_month_leap(self):
        # Jan 31 + 1 month → Feb 29 (leap year)
        assert add_interval(date(2028, 1, 31), 1, "months") == date(2028, 2, 29)

    def test_multi_month(self):
        assert add_interval(date(2026, 5, 17), 6, "months") == date(2026, 11, 17)


class TestYears:
    def test_simple(self):
        assert add_interval(date(2026, 5, 17), 1, "years") == date(2027, 5, 17)

    def test_leap_day_to_non_leap_year(self):
        # 2024 is leap; 2025 is not. Feb 29 → Feb 28.
        assert add_interval(date(2024, 2, 29), 1, "years") == date(2025, 2, 28)


class TestValidation:
    def test_rejects_zero(self):
        with pytest.raises(ValueError):
            add_interval(date(2026, 5, 17), 0, "days")

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            add_interval(date(2026, 5, 17), -1, "weeks")

    def test_rejects_unknown_unit(self):
        with pytest.raises(ValueError):
            add_interval(date(2026, 5, 17), 1, "fortnights")
