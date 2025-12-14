# ABOUTME: Tests for fetch_emails.py - duration parsing functionality
# ABOUTME: Tests parse_duration() with various time units

import pytest
from datetime import timedelta
import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fetch_emails import parse_duration


class TestParseDuration:
    """Tests for parse_duration() function."""

    def test_hours(self):
        """Parse hour durations."""
        assert parse_duration("1h") == timedelta(hours=1)
        assert parse_duration("12h") == timedelta(hours=12)
        assert parse_duration("24h") == timedelta(hours=24)

    def test_days(self):
        """Parse day durations."""
        assert parse_duration("1d") == timedelta(days=1)
        assert parse_duration("7d") == timedelta(days=7)
        assert parse_duration("30d") == timedelta(days=30)

    def test_weeks(self):
        """Parse week durations."""
        assert parse_duration("1w") == timedelta(weeks=1)
        assert parse_duration("2w") == timedelta(weeks=2)
        assert parse_duration("4w") == timedelta(weeks=4)

    def test_months(self):
        """Parse month durations (approximated as 30 days)."""
        assert parse_duration("1mo") == timedelta(days=30)
        assert parse_duration("2mo") == timedelta(days=60)
        assert parse_duration("12mo") == timedelta(days=360)

    def test_case_insensitive(self):
        """Duration parsing is case-insensitive."""
        assert parse_duration("1D") == timedelta(days=1)
        assert parse_duration("1H") == timedelta(hours=1)
        assert parse_duration("1W") == timedelta(weeks=1)
        assert parse_duration("1MO") == timedelta(days=30)

    def test_invalid_format_no_unit(self):
        """Invalid format without unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("123")

    def test_invalid_format_bad_unit(self):
        """Invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("1x")

    def test_invalid_format_empty(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("")

    def test_invalid_format_letters_first(self):
        """Letters before numbers raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("d1")

    def test_zero_duration(self):
        """Zero duration is valid."""
        assert parse_duration("0d") == timedelta(days=0)
        assert parse_duration("0h") == timedelta(hours=0)
