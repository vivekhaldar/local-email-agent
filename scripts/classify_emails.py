#!/usr/bin/env python3
# ABOUTME: Classify and summarize emails using Claude Haiku for efficiency
# ABOUTME: Usage: uv run scripts/classify_emails.py --input parsed.json --output classified.json

import argparse
import json
import os
import subprocess
import sys
from anthropic import Anthropic


def get_api_key() -> str:
    """Get Anthropic API key from environment or pass."""
    # First try environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return api_key

    # Try pass (check multiple common paths)
    pass_paths = ["dev/ANTHROPIC_API_KEY", "API_KEYS/anthropic", "em/ANTHROPIC_API_KEY"]
    for pass_path in pass_paths:
        try:
            result = subprocess.run(
                ["pass", "show", pass_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    print("Error: ANTHROPIC_API_KEY not found in environment or pass", file=sys.stderr)
    print("Set ANTHROPIC_API_KEY or store in: pass API_KEYS/anthropic", file=sys.stderr)
    sys.exit(1)

def classify_by_labels(email: dict) -> str | None:
    """Pre-classify emails based on Gmail labels."""
    labels = email.get("labels", "")
    if "CATEGORY_PROMOTIONS" in labels:
        return "NEWSLETTER"
    if "CATEGORY_UPDATES" in labels:
        return "AUTOMATED"
    return None

def generate_template_summary(email: dict, category: str) -> str:
    """Generate template summary for NEWSLETTER/AUTOMATED emails."""
    from_name = email.get("from_name", "Unknown")
    subject = email.get("subject", "")

    if category == "NEWSLETTER":
        return f"Marketing email from {from_name} about {subject}"
    else:  # AUTOMATED
        return f"Notification from {from_name}: {subject}"

def summarize_with_llm(emails: list[dict], client: Anthropic) -> list[dict]:
    """Use Claude Haiku to classify and summarize emails."""
    if not emails:
        return []

    # Build prompt with all emails
    email_texts = []
    for i, email in enumerate(emails):
        body = email.get("body_preview", "")[:2000]  # Truncate long bodies
        email_texts.append(f"""
---EMAIL {i+1}---
From: {email.get('from_name', 'Unknown')} <{email.get('from_email', '')}>
Subject: {email.get('subject', '')}
Body:
{body}
""")

    prompt = f"""Analyze each email and provide classification and summary.

For each email, respond with a JSON array where each element has:
- "index": the email number (1-based)
- "category": one of URGENT | NEEDS_RESPONSE | FYI
- "summary": 1-2 sentences describing the actual content (NOT just the subject line)
- "action_items": any requests, deadlines, or required actions (or null)

Classification rules:
- URGENT: Contains "urgent", "ASAP", "deadline", "by EOD", "action required", or time-sensitive requests
- NEEDS_RESPONSE: Direct questions to recipient, "please respond", "let me know", "what do you think"
- FYI: Everything else - informational, announcements, updates

EMAILS:
{''.join(email_texts)}

Respond with ONLY valid JSON array, no other text."""

    response = client.messages.create(
        model="claude-haiku-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse response
    try:
        text = response.content[0].text
        # Handle potential markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        results = json.loads(text)

        # Merge results back into emails
        result_map = {r["index"]: r for r in results}
        for i, email in enumerate(emails):
            r = result_map.get(i + 1, {})
            email["category"] = r.get("category", "FYI")
            email["summary"] = r.get("summary", f"{email.get('from_name', 'Unknown')}: {email.get('subject', '')}")
            email["action_items"] = r.get("action_items")

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Warning: Failed to parse LLM response: {e}", file=sys.stderr)
        # Fallback to template summaries
        for email in emails:
            email["category"] = "FYI"
            email["summary"] = f"{email.get('from_name', 'Unknown')}: {email.get('subject', '')}"
            email["action_items"] = None

    return emails

def main():
    parser = argparse.ArgumentParser(description="Classify and summarize emails")
    parser.add_argument("--input", required=True, help="Input JSON file with parsed emails")
    parser.add_argument("--output", required=True, help="Output JSON file for classified emails")
    parser.add_argument("--raw", required=True, help="Raw emails JSON with Gmail links and labels")
    args = parser.parse_args()

    # Load parsed emails
    with open(args.input) as f:
        parsed = json.load(f)

    # Load raw emails for labels and Gmail links
    with open(args.raw) as f:
        raw = json.load(f)

    # Create lookup by message_num
    raw_lookup = {e["message_num"]: e for e in raw["emails"]}

    # Merge parsed data with raw data
    emails = []
    for p in parsed:
        msg_num = p.get("message_num")
        raw_email = raw_lookup.get(msg_num, {})
        emails.append({
            "message_num": msg_num,
            "uid": raw_email.get("uid", ""),
            "gmail_link": raw_email.get("gmail_link", ""),
            "from_name": p.get("from_name", ""),
            "from_email": p.get("from_email", ""),
            "subject": p.get("subject", ""),
            "date": raw_email.get("date", p.get("date", "")),
            "labels": raw_email.get("labels", ""),
            "body_preview": p.get("body_preview", ""),
        })

    # Classify emails
    needs_llm = []
    classified = []

    for email in emails:
        category = classify_by_labels(email)
        if category:
            email["category"] = category
            email["summary"] = generate_template_summary(email, category)
            email["action_items"] = None
            classified.append(email)
        else:
            needs_llm.append(email)

    # Use LLM for remaining emails (batch them)
    if needs_llm:
        print(f"🤖 Classifying {len(needs_llm)} emails with Haiku...", file=sys.stderr)
        api_key = get_api_key()
        client = Anthropic(api_key=api_key)

        # Process in batches of 10
        batch_size = 10
        for i in range(0, len(needs_llm), batch_size):
            batch = needs_llm[i:i+batch_size]
            summarize_with_llm(batch, client)
            print(f"   Processed {min(i+batch_size, len(needs_llm))}/{len(needs_llm)}", file=sys.stderr)

        classified.extend(needs_llm)

    # Sort by date descending
    classified.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Remove body_preview and labels from output
    for email in classified:
        email.pop("body_preview", None)
        email.pop("labels", None)

    # Write output
    with open(args.output, "w") as f:
        json.dump({"emails": classified}, f, indent=2)

    # Print stats
    categories = {}
    for email in classified:
        cat = email.get("category", "FYI")
        categories[cat] = categories.get(cat, 0) + 1

    print(f"📊 Classified {len(classified)} emails:", file=sys.stderr)
    for cat in ["URGENT", "NEEDS_RESPONSE", "FYI", "NEWSLETTER", "AUTOMATED"]:
        if cat in categories:
            print(f"   {cat}: {categories[cat]}", file=sys.stderr)

if __name__ == "__main__":
    main()
