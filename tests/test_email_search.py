# ABOUTME: Tests for email_search.py - search functionality
# ABOUTME: Tests parse_duration(), date_hint_to_range(), format_date(), strip_html_tags(), format_answer_html()

import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from email_search import (
    parse_duration,
    date_hint_to_range,
    format_date,
    strip_html_tags,
    format_answer_html,
)


class TestParseDuration:
    """Tests for parse_duration() in email_search.py (includes year support)."""

    def test_hours(self):
        """Parse hour durations."""
        assert parse_duration("1h") == timedelta(hours=1)
        assert parse_duration("24h") == timedelta(hours=24)

    def test_days(self):
        """Parse day durations."""
        assert parse_duration("1d") == timedelta(days=1)
        assert parse_duration("30d") == timedelta(days=30)

    def test_weeks(self):
        """Parse week durations."""
        assert parse_duration("1w") == timedelta(weeks=1)
        assert parse_duration("4w") == timedelta(weeks=4)

    def test_months(self):
        """Parse month durations."""
        assert parse_duration("1mo") == timedelta(days=30)
        assert parse_duration("6mo") == timedelta(days=180)

    def test_years(self):
        """Parse year durations (unique to email_search)."""
        assert parse_duration("1y") == timedelta(days=365)
        assert parse_duration("2y") == timedelta(days=730)

    def test_case_insensitive(self):
        """Duration parsing is case-insensitive."""
        assert parse_duration("1Y") == timedelta(days=365)
        assert parse_duration("1MO") == timedelta(days=30)

    def test_invalid_format(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("invalid")

    def test_missing_unit(self):
        """Missing unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("123")


class TestDateHintToRange:
    """Tests for date_hint_to_range() function."""

    def test_last_year(self):
        """'last year' returns past 365 days."""
        result = date_hint_to_range("last year")
        assert result is not None
        since, until = result
        assert until >= since
        diff = (until - since).days
        assert 364 <= diff <= 366  # Account for leap years / now() timing

    def test_past_year(self):
        """'past year' also works."""
        result = date_hint_to_range("past year")
        assert result is not None

    def test_last_month(self):
        """'last month' returns past 30 days."""
        result = date_hint_to_range("last month")
        assert result is not None
        since, until = result
        diff = (until - since).days
        assert 29 <= diff <= 31

    def test_last_week(self):
        """'last week' returns past 7 days."""
        result = date_hint_to_range("last week")
        assert result is not None
        since, until = result
        diff = (until - since).days
        assert 6 <= diff <= 8

    def test_this_year(self):
        """'this year' returns from Jan 1 to now."""
        result = date_hint_to_range("this year")
        assert result is not None
        since, until = result
        assert since.month == 1
        assert since.day == 1
        assert since.year == datetime.now().year

    def test_specific_year(self):
        """Specific year like '2023' returns full year."""
        result = date_hint_to_range("2023")
        assert result is not None
        since, until = result
        assert since == datetime(2023, 1, 1)
        assert until.year == 2023
        assert until.month == 12
        assert until.day == 31

    def test_year_in_phrase(self):
        """Year extracted from phrase."""
        result = date_hint_to_range("emails from 2022")
        assert result is not None
        since, until = result
        assert since.year == 2022

    def test_none_hint(self):
        """None hint returns None."""
        assert date_hint_to_range(None) is None

    def test_empty_hint(self):
        """Empty hint returns None."""
        assert date_hint_to_range("") is None

    def test_unrecognized_hint(self):
        """Unrecognized hint returns None."""
        assert date_hint_to_range("yesterday") is None
        assert date_hint_to_range("random text") is None

    def test_case_insensitive(self):
        """Hint matching is case-insensitive."""
        result1 = date_hint_to_range("LAST YEAR")
        result2 = date_hint_to_range("Last Year")
        assert result1 is not None
        assert result2 is not None


class TestFormatDate:
    """Tests for format_date() function."""

    def test_iso_format(self):
        """ISO date format."""
        result = format_date("2025-12-13 10:30:00")
        assert "Dec" in result
        assert "13" in result
        assert "2025" in result

    def test_iso_format_with_t(self):
        """ISO format with T separator."""
        result = format_date("2025-12-13T10:30:00")
        assert "Dec" in result
        assert "13" in result

    def test_invalid_date_truncated(self):
        """Invalid date is truncated."""
        result = format_date("not a valid date string here")
        assert len(result) <= 16

    def test_empty_date(self):
        """Empty date is truncated to empty."""
        result = format_date("")
        assert result == ""

    def test_output_format(self):
        """Output is in 'Mon DD, YYYY' format."""
        result = format_date("2025-01-15 12:00:00")
        assert result == "Jan 15, 2025"


class TestStripHtmlTags:
    """Tests for strip_html_tags() function."""

    def test_simple_tags(self):
        """Simple HTML tags are removed."""
        assert "Hello" in strip_html_tags("<p>Hello</p>")
        assert "<" not in strip_html_tags("<p>Hello</p>")

    def test_nested_tags(self):
        """Nested tags are removed."""
        html = "<div><p><strong>Bold</strong></p></div>"
        result = strip_html_tags(html)
        assert "Bold" in result
        assert "<" not in result

    def test_whitespace_normalized(self):
        """Multiple spaces are normalized."""
        html = "<p>Word1     Word2</p>"
        result = strip_html_tags(html)
        assert "     " not in result

    def test_empty_string(self):
        """Empty string returns empty."""
        assert strip_html_tags("") == ""

    def test_plain_text(self):
        """Plain text without tags is unchanged."""
        text = "Plain text here"
        result = strip_html_tags(text)
        assert "Plain text here" in result


class TestFormatAnswerHtml:
    """Tests for format_answer_html() function."""

    def test_bold_markdown_to_html(self):
        """**bold** becomes <strong>bold</strong>."""
        result = format_answer_html("This is **bold** text")
        assert "<strong>bold</strong>" in result
        assert "**" not in result

    def test_italic_markdown_to_html(self):
        """*italic* becomes <em>italic</em>."""
        result = format_answer_html("This is *italic* text")
        assert "<em>italic</em>" in result

    def test_url_not_affected(self):
        """URLs with * are not converted to italic."""
        result = format_answer_html("Visit http://example.com/path*here")
        # Should not have em tags around the URL part
        assert "http://example.com" in result

    def test_single_email_reference(self):
        """'Email 1' becomes a link."""
        result = format_answer_html("See Email 1 for details")
        assert 'href="#source-1"' in result
        assert "email-ref" in result

    def test_email_in_parens(self):
        """'(Email 5)' becomes a link."""
        result = format_answer_html("More info (Email 5)")
        assert 'href="#source-5"' in result

    def test_multiple_email_references(self):
        """Multiple email refs are all converted."""
        result = format_answer_html("See Email 1 and Email 2")
        assert 'href="#source-1"' in result
        assert 'href="#source-2"' in result

    def test_emails_plural_reference(self):
        """'Emails 2, 3' both become links."""
        result = format_answer_html("Check Emails 2, 3 for details")
        assert 'href="#source-2"' in result
        assert 'href="#source-3"' in result

    def test_combined_formatting(self):
        """Bold and email refs work together."""
        result = format_answer_html("**Important**: See Email 4")
        assert "<strong>Important</strong>" in result
        assert 'href="#source-4"' in result

    def test_no_formatting_unchanged(self):
        """Text without special formatting is unchanged."""
        text = "Plain text with no formatting"
        result = format_answer_html(text)
        assert result == text

    def test_email_ref_class(self):
        """Email refs have correct CSS class."""
        result = format_answer_html("Email 1")
        assert 'class="email-ref"' in result
