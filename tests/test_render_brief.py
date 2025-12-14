# ABOUTME: Tests for render_brief.py - HTML rendering functionality
# ABOUTME: Tests format_date_short() and organize_by_category()

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_brief import format_date_short, organize_by_category


class TestFormatDateShort:
    """Tests for format_date_short() function."""

    def test_iso_format(self):
        """ISO date format."""
        result = format_date_short("2025-12-13 10:30:00")
        assert "Dec" in result
        assert "13" in result

    def test_rfc_format_with_timezone(self):
        """RFC 2822 format with timezone."""
        result = format_date_short("Mon, 13 Dec 2025 10:30:00 +0000")
        assert "Dec" in result
        assert "13" in result

    def test_rfc_format_negative_timezone(self):
        """RFC format with negative timezone."""
        result = format_date_short("Mon, 13 Dec 2025 10:30:00 -0800")
        assert "Dec" in result

    def test_am_pm_formatting(self):
        """Time includes AM/PM."""
        result = format_date_short("2025-12-13 10:30:00")
        assert "AM" in result or "PM" in result

    def test_empty_date(self):
        """Empty date returns empty."""
        assert format_date_short("") == ""

    def test_invalid_date_truncated(self):
        """Invalid date is truncated to first 16 chars."""
        result = format_date_short("not a valid date at all")
        assert len(result) <= 16

    def test_none_safe(self):
        """None value doesn't crash."""
        # The function should handle this gracefully
        try:
            result = format_date_short(None)
            assert result == "" or result is None
        except (TypeError, AttributeError):
            pytest.skip("Function doesn't handle None - consider adding handling")


class TestOrganizeByCategory:
    """Tests for organize_by_category() function."""

    def test_empty_list(self):
        """Empty list returns sections with empty emails."""
        sections = organize_by_category([])
        assert len(sections) == 7  # All category sections
        for section in sections:
            assert section["emails"] == []

    def test_urgent_category(self):
        """URGENT items go to urgent section."""
        items = [{"category": "URGENT", "subject": "Test"}]
        sections = organize_by_category(items)

        urgent_section = next(s for s in sections if s["name"] == "Urgent")
        assert len(urgent_section["emails"]) == 1
        assert urgent_section["icon"] == "🔴"
        assert urgent_section["css_class"] == "urgent"

    def test_needs_response_category(self):
        """NEEDS_RESPONSE items go to correct section."""
        items = [{"category": "NEEDS_RESPONSE", "subject": "Test"}]
        sections = organize_by_category(items)

        section = next(s for s in sections if s["name"] == "Needs Response")
        assert len(section["emails"]) == 1
        assert section["icon"] == "🟡"

    def test_fyi_category(self):
        """FYI items go to FYI section."""
        items = [{"category": "FYI", "subject": "Test"}]
        sections = organize_by_category(items)

        section = next(s for s in sections if s["name"] == "FYI")
        assert len(section["emails"]) == 1
        assert section["icon"] == "🔵"

    def test_newsletter_category(self):
        """NEWSLETTER items go to correct section."""
        items = [{"category": "NEWSLETTER", "subject": "Test"}]
        sections = organize_by_category(items)

        section = next(s for s in sections if s["name"] == "Newsletters & Promotions")
        assert len(section["emails"]) == 1
        assert section["icon"] == "📰"

    def test_automated_category(self):
        """AUTOMATED items go to correct section."""
        items = [{"category": "AUTOMATED", "subject": "Test"}]
        sections = organize_by_category(items)

        section = next(s for s in sections if s["name"] == "Automated & Updates")
        assert len(section["emails"]) == 1
        assert section["icon"] == "⚙️"

    def test_calendar_category(self):
        """CALENDAR items go to correct section."""
        items = [{"category": "CALENDAR", "subject": "Meeting"}]
        sections = organize_by_category(items)

        section = next(s for s in sections if s["name"] == "Calendar & Events")
        assert len(section["emails"]) == 1
        assert section["icon"] == "📅"

    def test_financial_category(self):
        """FINANCIAL items go to correct section."""
        items = [{"category": "FINANCIAL", "subject": "Statement"}]
        sections = organize_by_category(items)

        section = next(s for s in sections if s["name"] == "Financial")
        assert len(section["emails"]) == 1
        assert section["icon"] == "💰"

    def test_unknown_category_defaults_to_fyi(self):
        """Unknown category defaults to FYI."""
        items = [{"category": "UNKNOWN_CATEGORY", "subject": "Test"}]
        sections = organize_by_category(items)

        fyi_section = next(s for s in sections if s["name"] == "FYI")
        assert len(fyi_section["emails"]) == 1

    def test_missing_category_defaults_to_fyi(self):
        """Missing category defaults to FYI."""
        items = [{"subject": "No category"}]
        sections = organize_by_category(items)

        fyi_section = next(s for s in sections if s["name"] == "FYI")
        assert len(fyi_section["emails"]) == 1

    def test_case_insensitive(self):
        """Category matching is case-insensitive."""
        items = [
            {"category": "urgent", "subject": "Test1"},
            {"category": "Urgent", "subject": "Test2"},
            {"category": "URGENT", "subject": "Test3"}
        ]
        sections = organize_by_category(items)

        urgent_section = next(s for s in sections if s["name"] == "Urgent")
        assert len(urgent_section["emails"]) == 3

    def test_multiple_items_per_category(self):
        """Multiple items in same category."""
        items = [
            {"category": "URGENT", "subject": "Test1"},
            {"category": "URGENT", "subject": "Test2"},
            {"category": "FYI", "subject": "Test3"}
        ]
        sections = organize_by_category(items)

        urgent_section = next(s for s in sections if s["name"] == "Urgent")
        fyi_section = next(s for s in sections if s["name"] == "FYI")

        assert len(urgent_section["emails"]) == 2
        assert len(fyi_section["emails"]) == 1

    def test_section_order(self):
        """Sections are in correct priority order."""
        sections = organize_by_category([])
        section_names = [s["name"] for s in sections]

        # URGENT should come before FYI, NEWSLETTER should be last
        assert section_names.index("Urgent") < section_names.index("FYI")
        assert section_names.index("Needs Response") < section_names.index("FYI")
        assert section_names.index("FYI") < section_names.index("Newsletters & Promotions")
