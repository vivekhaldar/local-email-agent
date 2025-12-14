#!/usr/bin/env python3
# ABOUTME: Group emails by thread using Message-ID, In-Reply-To, and References headers
# ABOUTME: Usage: uv run scripts/group_threads.py --input parsed.json --raw raw.json --output grouped.json

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime


def normalize_subject(subject: str) -> str:
    """Remove Re:, Fwd:, etc. prefixes to get base subject for fallback matching."""
    # Remove common prefixes (case-insensitive)
    normalized = re.sub(r'^(re|fwd|fw):\s*', '', subject.strip(), flags=re.IGNORECASE)
    # Remove multiple prefixes
    while re.match(r'^(re|fwd|fw):\s*', normalized, flags=re.IGNORECASE):
        normalized = re.sub(r'^(re|fwd|fw):\s*', '', normalized, flags=re.IGNORECASE)
    return normalized.strip()


def parse_date(date_str: str) -> datetime:
    """Parse email date string to datetime for sorting."""
    if not date_str:
        return datetime.min

    # Common email date formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
    ]

    # Remove timezone name in parentheses like "(PST)"
    date_str = re.sub(r'\s*\([A-Z]{3,4}\)\s*$', '', date_str)

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    return datetime.min


def find_thread_root(email: dict, message_id_map: dict) -> str:
    """Find the root message ID of a thread by walking up In-Reply-To chain."""
    visited = set()
    current_id = email.get("message_id", "")

    if not current_id:
        return ""

    while current_id and current_id not in visited:
        visited.add(current_id)

        current_email = message_id_map.get(current_id)
        if not current_email:
            # This message ID is not in our set, it's the root (or external)
            break

        parent_id = current_email.get("in_reply_to", "")
        if not parent_id:
            # No parent, this is the root
            break

        current_id = parent_id

    return current_id


def group_emails_by_thread(parsed_emails: list, raw_emails: list) -> list:
    """Group emails into threads based on Message-ID relationships."""
    # Create lookup by message_num for raw emails (contains labels, gmail_link)
    raw_lookup = {e["message_num"]: e for e in raw_emails}

    # Merge raw data into parsed emails
    for email in parsed_emails:
        msg_num = email.get("message_num")
        if msg_num and msg_num in raw_lookup:
            raw = raw_lookup[msg_num]
            email["uid"] = raw.get("uid", "")
            email["gmail_link"] = raw.get("gmail_link", "")
            email["labels"] = raw.get("labels", "")

    # Build message_id → email map
    message_id_map = {}
    for email in parsed_emails:
        msg_id = email.get("message_id", "")
        if msg_id:
            message_id_map[msg_id] = email

    # Group by thread root
    thread_groups = defaultdict(list)
    orphans = []  # Emails without message_id

    for email in parsed_emails:
        msg_id = email.get("message_id", "")

        if not msg_id:
            # No message ID, can't thread - try subject-based fallback
            orphans.append(email)
            continue

        # Find thread root
        root_id = find_thread_root(email, message_id_map)

        # If root_id is not in our set, use references to find earliest known ancestor
        if root_id not in message_id_map:
            references = email.get("references", "")
            if references:
                ref_ids = [r.strip().strip("<>") for r in references.split()]
                for ref_id in ref_ids:
                    if ref_id in message_id_map:
                        root_id = ref_id
                        break

        # If still not found, use own message_id as root
        if root_id not in message_id_map:
            root_id = msg_id

        thread_groups[root_id].append(email)

    # Fallback: group orphans by normalized subject
    subject_groups = defaultdict(list)
    for email in orphans:
        norm_subj = normalize_subject(email.get("subject", ""))
        if norm_subj:
            subject_groups[norm_subj].append(email)
        else:
            # Can't group, treat as single
            subject_groups[f"_orphan_{id(email)}"] = [email]

    # Merge subject groups into thread groups if they match existing threads
    for norm_subj, emails in subject_groups.items():
        matched = False
        for root_id, thread_emails in thread_groups.items():
            thread_norm_subj = normalize_subject(thread_emails[0].get("subject", ""))
            if thread_norm_subj == norm_subj:
                thread_groups[root_id].extend(emails)
                matched = True
                break
        if not matched:
            # Create new group with fake root ID
            thread_groups[f"_subject_{norm_subj}"] = emails

    # Build output items
    items = []

    for root_id, messages in thread_groups.items():
        # Sort messages chronologically
        messages.sort(key=lambda e: parse_date(e.get("date", "")))

        if len(messages) == 1:
            # Single email - not a thread
            items.append({
                "is_thread": False,
                "messages": messages
            })
        else:
            # Multi-message thread
            participants = list(dict.fromkeys(m.get("from_name", "") for m in messages))
            # Use subject from first message (oldest)
            base_subject = normalize_subject(messages[0].get("subject", ""))
            # Use gmail_link from most recent message
            gmail_link = messages[-1].get("gmail_link", "")
            # Date range
            first_date = messages[0].get("date", "")
            last_date = messages[-1].get("date", "")

            items.append({
                "is_thread": True,
                "thread_id": root_id,
                "message_count": len(messages),
                "participants": participants,
                "subject": base_subject,
                "gmail_link": gmail_link,
                "first_date": first_date,
                "last_date": last_date,
                "messages": messages
            })

    # Sort items by most recent message date (descending)
    items.sort(key=lambda item: parse_date(item["messages"][-1].get("date", "")), reverse=True)

    return items


def main():
    parser = argparse.ArgumentParser(description="Group emails by thread")
    parser.add_argument("--input", required=True, help="Parsed emails JSON file")
    parser.add_argument("--raw", required=True, help="Raw emails JSON file (for labels and gmail links)")
    parser.add_argument("--output", required=True, help="Output grouped JSON file")
    args = parser.parse_args()

    # Load parsed emails
    with open(args.input) as f:
        parsed_data = json.load(f)

    # Handle list or dict format
    if isinstance(parsed_data, list):
        parsed_emails = parsed_data
    else:
        parsed_emails = parsed_data.get("emails", [])

    # Load raw emails
    with open(args.raw) as f:
        raw_data = json.load(f)

    if isinstance(raw_data, list):
        raw_emails = raw_data
    else:
        raw_emails = raw_data.get("emails", raw_data)

    # Group into threads
    items = group_emails_by_thread(parsed_emails, raw_emails)

    # Count stats
    thread_count = sum(1 for i in items if i["is_thread"])
    single_count = sum(1 for i in items if not i["is_thread"])
    total_messages = sum(len(i["messages"]) for i in items)

    print(f"📧 Grouped {total_messages} emails into:", file=sys.stderr)
    print(f"   {thread_count} threads (2+ messages)", file=sys.stderr)
    print(f"   {single_count} single emails", file=sys.stderr)

    # Write output
    with open(args.output, "w") as f:
        json.dump({"items": items}, f, indent=2)

    print(f"✅ Output written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
