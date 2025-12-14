#!/usr/bin/env python3
# ABOUTME: Classify emails by calling claude CLI with haiku model
# ABOUTME: Usage: uv run scripts/classify_with_claude.py --parsed emails_parsed.json --raw emails_raw.json --output emails_classified.json

import argparse
import json
import subprocess
import sys
from pathlib import Path


def classify_by_labels(email: dict) -> tuple[str, str] | None:
    """Pre-classify emails based on Gmail labels. Returns (category, summary) or None."""
    labels = email.get("labels", "")
    from_name = email.get("from_name", "Unknown")
    subject = email.get("subject", "")

    if "CATEGORY_PROMOTIONS" in labels:
        return ("NEWSLETTER", f"Marketing email from {from_name} about {subject}")
    if "CATEGORY_UPDATES" in labels:
        return ("AUTOMATED", f"Notification from {from_name}: {subject}")
    return None


def classify_with_claude(email: dict) -> dict:
    """Call claude CLI to classify and summarize a single email."""
    from_name = email.get("from_name", "Unknown")
    from_email = email.get("from_email", "")
    subject = email.get("subject", "")
    body = email.get("body_preview", "")[:2000]  # Truncate long bodies

    prompt = f"""Classify this email and provide a JSON response.

EMAIL:
From: {from_name} <{from_email}>
Subject: {subject}
Body:
{body}

CLASSIFICATION RULES:
- URGENT: Contains "urgent", "ASAP", "deadline", "by EOD", "action required", time-sensitive
- NEEDS_RESPONSE: Direct questions to recipient, "please respond", "let me know", "what do you think"
- CALENDAR: Calendar invitations, event updates, meeting requests, from Google Calendar
- FINANCIAL: From banks/brokerages (Chase, Ally, Vanguard, Fidelity, etc.), bills, statements, balance alerts
- FYI: Everything else - informational, no action needed

Respond with ONLY this JSON (no markdown, no explanation):
{{"category": "CATEGORY", "summary": "1-2 sentence summary of actual content", "action_items": "any actions needed or null"}}"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "haiku", "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(f"  Warning: claude returned {result.returncode} for '{subject[:40]}...'", file=sys.stderr)
            return {
                "category": "FYI",
                "summary": f"{from_name}: {subject}",
                "action_items": None
            }

        # Parse the JSON response
        response_text = result.stdout.strip()

        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        response_text = response_text.strip()
        parsed = json.loads(response_text)

        return {
            "category": parsed.get("category", "FYI").upper(),
            "summary": parsed.get("summary", f"{from_name}: {subject}"),
            "action_items": parsed.get("action_items")
        }

    except subprocess.TimeoutExpired:
        print(f"  Warning: timeout for '{subject[:40]}...'", file=sys.stderr)
        return {
            "category": "FYI",
            "summary": f"{from_name}: {subject}",
            "action_items": None
        }
    except json.JSONDecodeError as e:
        print(f"  Warning: JSON parse error for '{subject[:40]}...': {e}", file=sys.stderr)
        return {
            "category": "FYI",
            "summary": f"{from_name}: {subject}",
            "action_items": None
        }
    except Exception as e:
        print(f"  Warning: error for '{subject[:40]}...': {e}", file=sys.stderr)
        return {
            "category": "FYI",
            "summary": f"{from_name}: {subject}",
            "action_items": None
        }


def main():
    parser = argparse.ArgumentParser(description="Classify emails using claude CLI with haiku")
    parser.add_argument("--parsed", required=True, help="Parsed emails JSON file")
    parser.add_argument("--raw", required=True, help="Raw emails JSON file (for labels and gmail links)")
    parser.add_argument("--output", required=True, help="Output classified JSON file")
    args = parser.parse_args()

    # Load parsed emails
    with open(args.parsed) as f:
        parsed_emails = json.load(f)

    # Load raw emails for labels and gmail links
    with open(args.raw) as f:
        raw_data = json.load(f)
        raw_emails = raw_data.get("emails", raw_data) if isinstance(raw_data, dict) else raw_data

    # Create lookup by message_num
    raw_lookup = {e["message_num"]: e for e in raw_emails}

    # Merge and classify
    classified = []
    total = len(parsed_emails)
    needs_claude = 0
    pre_classified = 0

    print(f"🏷️ Classifying {total} emails...", file=sys.stderr)

    for i, parsed in enumerate(parsed_emails):
        msg_num = parsed.get("message_num")
        raw = raw_lookup.get(msg_num, {})

        # Build base email object
        email = {
            "message_num": msg_num,
            "uid": raw.get("uid", ""),
            "gmail_link": raw.get("gmail_link", ""),
            "from_name": parsed.get("from_name", ""),
            "from_email": parsed.get("from_email", ""),
            "subject": parsed.get("subject", ""),
            "date": raw.get("date", parsed.get("date", "")),
            "labels": raw.get("labels", ""),
            "body_preview": parsed.get("body_preview", ""),
        }

        # Try pre-classification by labels first
        pre_result = classify_by_labels(email)

        if pre_result:
            email["category"] = pre_result[0]
            email["summary"] = pre_result[1]
            email["action_items"] = None
            pre_classified += 1
        else:
            # Use claude CLI for classification
            needs_claude += 1
            print(f"  [{needs_claude}] Classifying: {email['from_name'][:20]} - {email['subject'][:40]}...", file=sys.stderr)
            result = classify_with_claude(email)
            email["category"] = result["category"]
            email["summary"] = result["summary"]
            email["action_items"] = result["action_items"]

        # Remove fields we don't need in output
        email.pop("labels", None)
        email.pop("body_preview", None)

        classified.append(email)

    # Sort by date descending
    classified.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Write output
    with open(args.output, "w") as f:
        json.dump({"emails": classified}, f, indent=2)

    # Print stats
    categories = {}
    for email in classified:
        cat = email.get("category", "FYI")
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n📊 Classified {total} emails ({pre_classified} by labels, {needs_claude} by Haiku):", file=sys.stderr)
    for cat in ["URGENT", "NEEDS_RESPONSE", "CALENDAR", "FINANCIAL", "FYI", "NEWSLETTER", "AUTOMATED"]:
        if cat in categories:
            print(f"   {cat}: {categories[cat]}", file=sys.stderr)

    print(f"\n✅ Output written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
