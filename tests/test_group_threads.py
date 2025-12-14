# ABOUTME: Tests for group_threads.py - email threading functionality
# ABOUTME: Tests normalize_subject(), parse_date(), find_thread_root(), group_emails_by_thread()

import pytest
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from group_threads import normalize_subject, parse_date, find_thread_root, group_emails_by_thread


class TestNormalizeSubject:
    """Tests for normalize_subject() function."""

    def test_remove_re_prefix(self):
        """Remove Re: prefix."""
        assert normalize_subject("Re: Hello") == "Hello"
        assert normalize_subject("RE: Hello") == "Hello"
        assert normalize_subject("re: Hello") == "Hello"

    def test_remove_fwd_prefix(self):
        """Remove Fwd: prefix."""
        assert normalize_subject("Fwd: Hello") == "Hello"
        assert normalize_subject("FWD: Hello") == "Hello"
        assert normalize_subject("fwd: Hello") == "Hello"

    def test_remove_fw_prefix(self):
        """Remove Fw: prefix."""
        assert normalize_subject("Fw: Hello") == "Hello"
        assert normalize_subject("FW: Hello") == "Hello"

    def test_remove_multiple_prefixes(self):
        """Remove multiple nested prefixes."""
        assert normalize_subject("Re: Re: Re: Hello") == "Hello"
        assert normalize_subject("Fwd: Re: Hello") == "Hello"
        assert normalize_subject("Re: Fwd: Re: Hello") == "Hello"

    def test_preserve_subject_content(self):
        """Subject content is preserved."""
        assert normalize_subject("Meeting Tomorrow") == "Meeting Tomorrow"
        assert normalize_subject("Project Update: Q4 Results") == "Project Update: Q4 Results"

    def test_trim_whitespace(self):
        """Whitespace is trimmed."""
        assert normalize_subject("  Re: Hello  ") == "Hello"
        assert normalize_subject("Re:   Hello") == "Hello"

    def test_empty_subject(self):
        """Empty subject returns empty."""
        assert normalize_subject("") == ""
        assert normalize_subject("Re: ") == ""

    def test_re_in_subject(self):
        """Re: within subject is preserved."""
        # "Re:" at the start is removed, but "regarding" or similar is kept
        assert normalize_subject("Meeting Re: Budget") == "Meeting Re: Budget"


class TestParseDate:
    """Tests for parse_date() function."""

    def test_rfc_2822_format(self):
        """Standard email date format."""
        date_str = "Mon, 13 Dec 2025 10:30:00 +0000"
        result = parse_date(date_str)
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 13

    def test_without_timezone_name(self):
        """Date without timezone name in parens."""
        date_str = "Mon, 13 Dec 2025 10:30:00 -0800"
        result = parse_date(date_str)
        assert result.year == 2025

    def test_with_timezone_name_in_parens(self):
        """Date with timezone name like (PST) is handled."""
        date_str = "Mon, 13 Dec 2025 10:30:00 -0800 (PST)"
        result = parse_date(date_str)
        assert result.year == 2025

    def test_iso_format(self):
        """ISO-style format."""
        date_str = "2025-12-13 10:30:00"
        result = parse_date(date_str)
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 13

    def test_empty_date(self):
        """Empty date returns datetime.min."""
        assert parse_date("") == datetime.min
        assert parse_date(None) == datetime.min

    def test_invalid_date(self):
        """Invalid date returns datetime.min."""
        assert parse_date("not a date") == datetime.min
        assert parse_date("12345") == datetime.min

    def test_short_format_without_day_name(self):
        """Date without day name."""
        date_str = "13 Dec 2025 10:30:00 +0000"
        result = parse_date(date_str)
        assert result.year == 2025


class TestFindThreadRoot:
    """Tests for find_thread_root() function."""

    def test_single_email_no_parent(self):
        """Email with no parent is its own root."""
        email = {"message_id": "msg1", "in_reply_to": ""}
        message_id_map = {"msg1": email}
        assert find_thread_root(email, message_id_map) == "msg1"

    def test_reply_chain(self):
        """Follow reply chain to find root."""
        root = {"message_id": "root", "in_reply_to": ""}
        reply1 = {"message_id": "reply1", "in_reply_to": "root"}
        reply2 = {"message_id": "reply2", "in_reply_to": "reply1"}

        message_id_map = {
            "root": root,
            "reply1": reply1,
            "reply2": reply2
        }

        assert find_thread_root(reply2, message_id_map) == "root"
        assert find_thread_root(reply1, message_id_map) == "root"
        assert find_thread_root(root, message_id_map) == "root"

    def test_external_parent(self):
        """Parent not in our set - returns external ID."""
        email = {"message_id": "msg1", "in_reply_to": "external_parent"}
        message_id_map = {"msg1": email}
        # external_parent is not in map, so it's returned as root
        assert find_thread_root(email, message_id_map) == "external_parent"

    def test_no_message_id(self):
        """Email without message_id returns empty."""
        email = {"in_reply_to": "parent"}
        message_id_map = {}
        assert find_thread_root(email, message_id_map) == ""

    def test_cycle_detection(self):
        """Cycle in reply chain doesn't cause infinite loop."""
        # Create a cycle: msg1 -> msg2 -> msg1
        msg1 = {"message_id": "msg1", "in_reply_to": "msg2"}
        msg2 = {"message_id": "msg2", "in_reply_to": "msg1"}

        message_id_map = {"msg1": msg1, "msg2": msg2}

        # Should not hang - returns one of the IDs in the cycle
        result = find_thread_root(msg1, message_id_map)
        assert result in ["msg1", "msg2"]


class TestGroupEmailsByThread:
    """Tests for group_emails_by_thread() function - Phase 2."""

    def test_single_emails_not_threaded(self):
        """Single emails are not marked as threads."""
        parsed = [
            {"message_num": 1, "message_id": "msg1", "in_reply_to": "", "references": "", "subject": "Hello", "from_name": "Alice", "date": "2025-12-13 10:00:00"}
        ]
        raw = [{"message_num": 1, "uid": "abc", "gmail_link": "http://...", "labels": []}]

        items = group_emails_by_thread(parsed, raw)

        assert len(items) == 1
        assert items[0]["is_thread"] is False
        assert len(items[0]["messages"]) == 1

    def test_two_email_thread(self):
        """Two emails in a thread are grouped."""
        parsed = [
            {"message_num": 1, "message_id": "msg1", "in_reply_to": "", "references": "", "subject": "Project", "from_name": "Alice", "date": "2025-12-13 10:00:00"},
            {"message_num": 2, "message_id": "msg2", "in_reply_to": "msg1", "references": "msg1", "subject": "Re: Project", "from_name": "Bob", "date": "2025-12-13 11:00:00"}
        ]
        raw = [
            {"message_num": 1, "uid": "abc", "gmail_link": "http://1", "labels": []},
            {"message_num": 2, "uid": "def", "gmail_link": "http://2", "labels": []}
        ]

        items = group_emails_by_thread(parsed, raw)

        assert len(items) == 1
        assert items[0]["is_thread"] is True
        assert items[0]["message_count"] == 2
        assert "Alice" in items[0]["participants"]
        assert "Bob" in items[0]["participants"]

    def test_multiple_separate_threads(self):
        """Multiple separate conversations stay separate."""
        parsed = [
            {"message_num": 1, "message_id": "thread1_msg1", "in_reply_to": "", "references": "", "subject": "Topic A", "from_name": "Alice", "date": "2025-12-13 10:00:00"},
            {"message_num": 2, "message_id": "thread2_msg1", "in_reply_to": "", "references": "", "subject": "Topic B", "from_name": "Bob", "date": "2025-12-13 11:00:00"}
        ]
        raw = [
            {"message_num": 1, "uid": "abc", "gmail_link": "http://1", "labels": []},
            {"message_num": 2, "uid": "def", "gmail_link": "http://2", "labels": []}
        ]

        items = group_emails_by_thread(parsed, raw)

        assert len(items) == 2
        assert all(item["is_thread"] is False for item in items)

    def test_thread_sorted_chronologically(self):
        """Messages within thread are sorted by date."""
        parsed = [
            {"message_num": 2, "message_id": "msg2", "in_reply_to": "msg1", "references": "msg1", "subject": "Re: Test", "from_name": "Bob", "date": "2025-12-13 12:00:00"},
            {"message_num": 1, "message_id": "msg1", "in_reply_to": "", "references": "", "subject": "Test", "from_name": "Alice", "date": "2025-12-13 10:00:00"},
            {"message_num": 3, "message_id": "msg3", "in_reply_to": "msg2", "references": "msg1 msg2", "subject": "Re: Test", "from_name": "Alice", "date": "2025-12-13 14:00:00"}
        ]
        raw = [
            {"message_num": 1, "uid": "a", "gmail_link": "http://1", "labels": []},
            {"message_num": 2, "uid": "b", "gmail_link": "http://2", "labels": []},
            {"message_num": 3, "uid": "c", "gmail_link": "http://3", "labels": []}
        ]

        items = group_emails_by_thread(parsed, raw)

        assert len(items) == 1
        assert items[0]["is_thread"] is True
        messages = items[0]["messages"]
        # Should be chronological: msg1, msg2, msg3
        assert messages[0]["message_id"] == "msg1"
        assert messages[1]["message_id"] == "msg2"
        assert messages[2]["message_id"] == "msg3"

    def test_orphan_emails_grouped_by_subject(self):
        """Emails without message_id are grouped by subject."""
        parsed = [
            {"message_num": 1, "message_id": "", "in_reply_to": "", "references": "", "subject": "Meeting Notes", "from_name": "Alice", "date": "2025-12-13 10:00:00"},
            {"message_num": 2, "message_id": "", "in_reply_to": "", "references": "", "subject": "Re: Meeting Notes", "from_name": "Bob", "date": "2025-12-13 11:00:00"}
        ]
        raw = [
            {"message_num": 1, "uid": "a", "gmail_link": "http://1", "labels": []},
            {"message_num": 2, "uid": "b", "gmail_link": "http://2", "labels": []}
        ]

        items = group_emails_by_thread(parsed, raw)

        # Both emails should be grouped together since subjects match after normalization
        total_messages = sum(len(item["messages"]) for item in items)
        assert total_messages == 2

    def test_thread_uses_base_subject(self):
        """Thread subject is the base subject without Re:/Fwd:."""
        parsed = [
            {"message_num": 1, "message_id": "msg1", "in_reply_to": "", "references": "", "subject": "Budget Review", "from_name": "Alice", "date": "2025-12-13 10:00:00"},
            {"message_num": 2, "message_id": "msg2", "in_reply_to": "msg1", "references": "msg1", "subject": "Re: Budget Review", "from_name": "Bob", "date": "2025-12-13 11:00:00"}
        ]
        raw = [
            {"message_num": 1, "uid": "a", "gmail_link": "http://1", "labels": []},
            {"message_num": 2, "uid": "b", "gmail_link": "http://2", "labels": []}
        ]

        items = group_emails_by_thread(parsed, raw)

        assert items[0]["subject"] == "Budget Review"

    def test_gmail_link_from_most_recent(self):
        """Thread gmail_link comes from most recent message."""
        parsed = [
            {"message_num": 1, "message_id": "msg1", "in_reply_to": "", "references": "", "subject": "Test", "from_name": "Alice", "date": "2025-12-13 10:00:00"},
            {"message_num": 2, "message_id": "msg2", "in_reply_to": "msg1", "references": "msg1", "subject": "Re: Test", "from_name": "Bob", "date": "2025-12-13 11:00:00"}
        ]
        raw = [
            {"message_num": 1, "uid": "old", "gmail_link": "http://old", "labels": []},
            {"message_num": 2, "uid": "new", "gmail_link": "http://new", "labels": []}
        ]

        items = group_emails_by_thread(parsed, raw)

        assert items[0]["gmail_link"] == "http://new"
