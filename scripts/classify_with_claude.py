#!/usr/bin/env python3
# ABOUTME: Classify emails/threads using Claude Agent SDK with haiku model
# ABOUTME: Usage: uv run scripts/classify_with_claude.py --grouped emails_grouped.json --output emails_classified.json

import argparse
import json
import sys
from pathlib import Path

from claude_client import query_claude_sync, parse_json_response, ClaudeQueryError


def classify_by_labels(item: dict) -> str | None:
    """Pre-classify category based on Gmail labels. Returns category or None.

    Note: Only returns the category, not the summary. Claude is always used
    for summaries to ensure quality.
    """
    messages = item.get("messages", [])
    if not messages:
        return None

    # Use most recent message for label check
    email = messages[-1]
    labels = email.get("labels", "")

    if "CATEGORY_PROMOTIONS" in labels:
        return "NEWSLETTER"
    if "CATEGORY_UPDATES" in labels:
        return "AUTOMATED"
    return None


def summarize_email(email: dict) -> dict:
    """Generate a summary for a single email using Claude."""
    from_name = email.get("from_name", "Unknown")
    subject = email.get("subject", "")
    body = email.get("body_preview", "")[:1500]

    prompt = f"""Summarize this email in ONE sentence. Focus on the key information or action.

From: {from_name}
Subject: {subject}
Body:
{body}

Respond with ONLY the summary sentence, no quotes or prefix."""

    try:
        response_text, cost = query_claude_sync(prompt, timeout_seconds=60)
        return {
            "summary": response_text.strip(),
            "cost_usd": cost
        }
    except (TimeoutError, ClaudeQueryError) as e:
        print(f"  Warning: summary failed for '{subject[:30]}': {e}", file=sys.stderr)
        return {
            "summary": f"{from_name}: {subject}",
            "cost_usd": 0.0
        }


def summarize_thread(item: dict) -> dict:
    """Generate a summary for an email thread using Claude."""
    messages = item.get("messages", [])
    subject = item.get("subject", "")
    participants = item.get("participants", [])

    # Build thread content
    thread_content = []
    for msg in messages[-3:]:  # Last 3 messages for context
        from_name = msg.get("from_name", "Unknown")
        body = msg.get("body_preview", "")[:500]
        thread_content.append(f"[{from_name}]: {body}")

    combined = "\n---\n".join(thread_content)
    if len(combined) > 2000:
        combined = combined[:2000] + "..."

    prompt = f"""Summarize this email thread in ONE sentence. Focus on the key topic and outcome.

Subject: {subject}
Participants: {', '.join(participants)}

{combined}

Respond with ONLY the summary sentence, no quotes or prefix."""

    try:
        response_text, cost = query_claude_sync(prompt, timeout_seconds=60)
        return {
            "summary": response_text.strip(),
            "cost_usd": cost
        }
    except (TimeoutError, ClaudeQueryError) as e:
        print(f"  Warning: summary failed for thread '{subject[:30]}': {e}", file=sys.stderr)
        return {
            "summary": f"{participants[0] if participants else 'Thread'}: {subject}",
            "cost_usd": 0.0
        }


def classify_single_email(email: dict) -> dict:
    """Call claude CLI to classify and summarize a single email."""
    from_name = email.get("from_name", "Unknown")
    from_email = email.get("from_email", "")
    subject = email.get("subject", "")
    body = email.get("body_preview", "")[:2000]

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

    return _call_claude(prompt, subject, from_name)


def classify_thread(item: dict) -> dict:
    """Call claude CLI to classify and summarize an email thread."""
    messages = item.get("messages", [])
    subject = item.get("subject", "")
    participants = item.get("participants", [])
    message_count = len(messages)

    # Build thread content (chronological order, truncate each message)
    thread_content = []
    for i, msg in enumerate(messages):
        from_name = msg.get("from_name", "Unknown")
        date = msg.get("date", "")[:20]  # Truncate date for brevity
        body = msg.get("body_preview", "")[:800]  # Shorter per message in thread
        thread_content.append(f"[Message {i+1} - From: {from_name}, Date: {date}]\n{body}")

    # Limit total thread content
    combined = "\n\n---\n\n".join(thread_content)
    if len(combined) > 4000:
        combined = combined[:4000] + "\n...[truncated]"

    prompt = f"""Classify this email thread and provide a JSON response.

EMAIL THREAD: "{subject}"
Participants: {', '.join(participants)}
Messages: {message_count}

{combined}

CLASSIFICATION RULES:
- URGENT: Contains "urgent", "ASAP", "deadline", "by EOD", "action required", time-sensitive
- NEEDS_RESPONSE: Direct questions to recipient, "please respond", "let me know", "what do you think"
- CALENDAR: Calendar invitations, event updates, meeting requests, from Google Calendar
- FINANCIAL: From banks/brokerages (Chase, Ally, Vanguard, Fidelity, etc.), bills, statements, balance alerts
- FYI: Everything else - informational, no action needed

Summarize the ENTIRE conversation (not just the last message). What is this thread about?

Respond with ONLY this JSON (no markdown, no explanation):
{{"category": "CATEGORY", "summary": "1-2 sentence summary of the conversation", "action_items": "any actions needed or null"}}"""

    return _call_claude(prompt, subject, participants[0] if participants else "Unknown")


def _call_claude(prompt: str, subject: str, fallback_name: str, max_retries: int = 2) -> dict:
    """Call Claude Agent SDK with the given prompt and return parsed result.

    Retries on transient failures (empty responses, parse errors) up to max_retries times.
    """
    last_error = None
    total_cost = 0.0

    for attempt in range(max_retries):
        try:
            response_text, cost = query_claude_sync(prompt, timeout_seconds=90)
            total_cost += cost
            parsed = parse_json_response(response_text)

            return {
                "category": parsed.get("category", "FYI").upper(),
                "summary": parsed.get("summary", f"{fallback_name}: {subject}"),
                "action_items": parsed.get("action_items"),
                "cost_usd": total_cost
            }

        except TimeoutError:
            print(f"  Warning: timeout for '{subject[:40]}...'", file=sys.stderr)
            return {
                "category": "FYI",
                "summary": f"{fallback_name}: {subject}",
                "action_items": None,
                "cost_usd": total_cost
            }
        except ValueError as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries - 1} for '{subject[:30]}...' ({e})", file=sys.stderr)
                continue
        except ClaudeQueryError as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries - 1} for '{subject[:30]}...' ({e})", file=sys.stderr)
                continue

    # All retries exhausted
    print(f"  Warning: failed after {max_retries} attempts for '{subject[:40]}...': {last_error}", file=sys.stderr)
    return {
        "category": "FYI",
        "summary": f"{fallback_name}: {subject}",
        "action_items": None,
        "cost_usd": total_cost
    }


def main():
    parser = argparse.ArgumentParser(description="Classify emails/threads using Claude Agent SDK")
    parser.add_argument("--grouped", required=True, help="Grouped emails JSON file (from group_threads.py)")
    parser.add_argument("--output", required=True, help="Output classified JSON file")
    args = parser.parse_args()

    # Load grouped items
    with open(args.grouped) as f:
        grouped_data = json.load(f)

    items = grouped_data.get("items", [])
    total = len(items)
    needs_claude = 0
    pre_classified = 0
    total_cost = 0.0

    print(f"🏷️ Classifying {total} items (threads + single emails)...", file=sys.stderr, flush=True)

    classified_items = []

    for i, item in enumerate(items):
        is_thread = item.get("is_thread", False)
        messages = item.get("messages", [])

        if not messages:
            continue

        # Build display info
        if is_thread:
            subject = item.get("subject", "")
            participants = item.get("participants", [])
            display = f"Thread: {participants[0] if participants else 'Unknown'} - {subject[:30]}..."
        else:
            email = messages[0]
            subject = email.get("subject", "")
            display = f"{email.get('from_name', 'Unknown')[:20]} - {subject[:30]}..."

        # Try pre-classification by labels first (category only)
        pre_category = classify_by_labels(item)

        if pre_category:
            # Category from labels, but still need Claude for summary
            pre_classified += 1
            needs_claude += 1
            print(f"  [{needs_claude}] {display} (summarizing)", file=sys.stderr, flush=True)

            item["category"] = pre_category
            item["action_items"] = None

            # Get summary from Claude
            if is_thread:
                summary_result = summarize_thread(item)
            else:
                summary_result = summarize_email(messages[0])

            item["summary"] = summary_result["summary"]
            total_cost += summary_result.get("cost_usd", 0.0)
        else:
            # Need Claude for both classification and summary
            needs_claude += 1
            print(f"  [{needs_claude}] {display} (classifying)", file=sys.stderr, flush=True)

            if is_thread:
                result = classify_thread(item)
            else:
                result = classify_single_email(messages[0])

            item["category"] = result["category"]
            item["summary"] = result["summary"]
            item["action_items"] = result["action_items"]
            total_cost += result.get("cost_usd", 0.0)

        # Clean up messages (remove body_preview, labels from output)
        for msg in messages:
            msg.pop("body_preview", None)
            msg.pop("labels", None)
            msg.pop("references", None)
            msg.pop("filepath", None)
            msg.pop("body_length", None)

        classified_items.append(item)

    # Write output
    with open(args.output, "w") as f:
        json.dump({"items": classified_items}, f, indent=2)

    # Print stats
    categories = {}
    for item in classified_items:
        cat = item.get("category", "FYI")
        categories[cat] = categories.get(cat, 0) + 1

    thread_count = sum(1 for i in classified_items if i.get("is_thread"))
    single_count = sum(1 for i in classified_items if not i.get("is_thread"))

    print(f"\n📊 Classified {total} items ({thread_count} threads, {single_count} singles):", file=sys.stderr)
    print(f"   Category from labels: {pre_classified}, Full classification: {needs_claude - pre_classified}", file=sys.stderr)
    print(f"   Claude SDK calls: {needs_claude}", file=sys.stderr)
    if total_cost > 0:
        print(f"   💰 Total cost: ${total_cost:.4f}", file=sys.stderr)
    for cat in ["URGENT", "NEEDS_RESPONSE", "CALENDAR", "FINANCIAL", "FYI", "NEWSLETTER", "AUTOMATED"]:
        if cat in categories:
            print(f"   {cat}: {categories[cat]}", file=sys.stderr)

    print(f"\n✅ Output written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
