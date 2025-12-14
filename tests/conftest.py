# ABOUTME: Shared pytest fixtures for email agent tests
# ABOUTME: Contains common test data and helper functions

import pytest
from datetime import datetime


@pytest.fixture
def sample_email_dict():
    """A basic email dictionary for testing."""
    return {
        "message_num": 1,
        "uid": "19b18f6a1dda4196",
        "gmail_link": "https://mail.google.com/mail/u/0/#all/19b18f6a1dda4196",
        "filename": "2025/12/13/19b18f6a1dda4196.eml",
        "date": "2025-12-13T10:26:14",
        "labels": ["INBOX", "UNREAD"],
        "from_name": "John Doe",
        "from_email": "john@example.com",
        "subject": "Test Subject",
        "body_preview": "This is a test email body.",
    }


@pytest.fixture
def sample_thread_emails():
    """A list of emails forming a thread for testing."""
    return [
        {
            "message_id": "<msg1@example.com>",
            "in_reply_to": None,
            "references": [],
            "subject": "Project Update",
            "from_name": "Alice",
            "from_email": "alice@example.com",
            "date": "2025-12-10T09:00:00",
        },
        {
            "message_id": "<msg2@example.com>",
            "in_reply_to": "<msg1@example.com>",
            "references": ["<msg1@example.com>"],
            "subject": "Re: Project Update",
            "from_name": "Bob",
            "from_email": "bob@example.com",
            "date": "2025-12-10T10:00:00",
        },
        {
            "message_id": "<msg3@example.com>",
            "in_reply_to": "<msg2@example.com>",
            "references": ["<msg1@example.com>", "<msg2@example.com>"],
            "subject": "Re: Project Update",
            "from_name": "Alice",
            "from_email": "alice@example.com",
            "date": "2025-12-10T11:00:00",
        },
    ]


@pytest.fixture
def classified_emails():
    """Sample classified emails for render testing."""
    return [
        {
            "subject": "Urgent: Server Down",
            "from_name": "Ops Team",
            "from_email": "ops@company.com",
            "gmail_link": "https://mail.google.com/mail/u/0/#all/abc123",
            "date": "2025-12-13T08:00:00",
            "category": "URGENT",
            "summary": "Production server is down, immediate action required.",
        },
        {
            "subject": "Weekly Newsletter",
            "from_name": "Newsletter",
            "from_email": "news@example.com",
            "gmail_link": "https://mail.google.com/mail/u/0/#all/def456",
            "date": "2025-12-13T07:00:00",
            "category": "NEWSLETTER",
            "summary": "Weekly tech news roundup.",
        },
    ]
