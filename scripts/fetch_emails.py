#!/usr/bin/env python3
# ABOUTME: Query SQLite database for recent emails and output as JSON
# ABOUTME: Usage: uv run scripts/fetch_emails.py --since 1d

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Gmail base URL for message links
GMAIL_BASE_URL = "https://mail.google.com/mail/u/0/#all"

# Database path
DB_PATH = Path.home() / "MAIL" / "gmail" / "msg-db.sqlite"


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '1d', '12h', '1w', '1mo' into timedelta."""
    match = re.match(r"^(\d+)(h|d|w|mo)$", duration_str.lower())
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}. Use: 1d, 12h, 1w, 1mo")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    elif unit == "mo":
        return timedelta(days=value * 30)  # Approximate
    else:
        raise ValueError(f"Unknown unit: {unit}")


def fetch_emails(since: datetime) -> list[dict]:
    """Fetch emails from SQLite database since the given datetime."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query messages with their labels and UIDs
    query = """
    SELECT
        m.message_num,
        m.message_filename,
        m.message_internaldate,
        u.uid,
        GROUP_CONCAT(l.label, '|') as labels
    FROM messages m
    LEFT JOIN uids u ON m.message_num = u.message_num
    LEFT JOIN labels l ON m.message_num = l.message_num
    WHERE m.message_internaldate >= ?
    GROUP BY m.message_num
    ORDER BY m.message_internaldate DESC
    """

    cursor.execute(query, (since.strftime("%Y-%m-%d %H:%M:%S"),))
    rows = cursor.fetchall()
    conn.close()

    emails = []
    for row in rows:
        labels = row["labels"].split("|") if row["labels"] else []
        uid = row["uid"] or ""

        emails.append({
            "message_num": row["message_num"],
            "uid": uid,
            "gmail_link": f"{GMAIL_BASE_URL}/{uid}" if uid else "",
            "filename": row["message_filename"],
            "date": row["message_internaldate"],
            "labels": labels
        })

    return emails


def main():
    parser = argparse.ArgumentParser(description="Fetch recent emails from GYB database")
    parser.add_argument(
        "--since",
        default="1d",
        help="Duration to look back (e.g., 1d, 12h, 1w, 1mo). Default: 1d"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout)"
    )
    args = parser.parse_args()

    # Calculate since datetime
    try:
        delta = parse_duration(args.since)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    since_dt = datetime.now() - delta

    # Fetch emails
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    emails = fetch_emails(since_dt)

    # Output
    result = {
        "since": since_dt.isoformat(),
        "count": len(emails),
        "emails": emails
    }

    output = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Wrote {len(emails)} emails to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
