#!/usr/bin/env python3
# ABOUTME: Classify emails/threads using Claude Agent SDK with haiku model
# ABOUTME: Supports caching and parallel processing for performance

import argparse
import asyncio
import json
import sys
from pathlib import Path

from claude_client import (
    query_claude_batch,
    parse_json_response,
    ClaudeQueryError,
    DEFAULT_MODEL,
)
from cache_manager import get_cache_key, lookup_cache, save_to_cache, init_cache_db


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


def build_summarize_prompt(item: dict) -> str:
    """Build a summary-only prompt for an item (when category is known from labels)."""
    is_thread = item.get("is_thread", False)
    messages = item.get("messages", [])

    if is_thread:
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

        return f"""Summarize this email thread in ONE sentence. Focus on the key topic and outcome.

Subject: {subject}
Participants: {', '.join(participants)}

{combined}

Respond with ONLY the summary sentence, no quotes or prefix."""
    else:
        email = messages[0]
        from_name = email.get("from_name", "Unknown")
        subject = email.get("subject", "")
        body = email.get("body_preview", "")[:1500]

        return f"""Summarize this email in ONE sentence. Focus on the key information or action.

From: {from_name}
Subject: {subject}
Body:
{body}

Respond with ONLY the summary sentence, no quotes or prefix."""


def build_classify_prompt(item: dict) -> str:
    """Build a full classification prompt for an item."""
    is_thread = item.get("is_thread", False)
    messages = item.get("messages", [])

    if is_thread:
        subject = item.get("subject", "")
        participants = item.get("participants", [])
        message_count = len(messages)

        # Build thread content (chronological order, truncate each message)
        thread_content = []
        for i, msg in enumerate(messages):
            from_name = msg.get("from_name", "Unknown")
            date = msg.get("date", "")[:20]
            body = msg.get("body_preview", "")[:800]
            thread_content.append(f"[Message {i+1} - From: {from_name}, Date: {date}]\n{body}")

        combined = "\n\n---\n\n".join(thread_content)
        if len(combined) > 4000:
            combined = combined[:4000] + "\n...[truncated]"

        return f"""Classify this email thread and provide a JSON response.

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
    else:
        email = messages[0]
        from_name = email.get("from_name", "Unknown")
        from_email = email.get("from_email", "")
        subject = email.get("subject", "")
        body = email.get("body_preview", "")[:2000]

        return f"""Classify this email and provide a JSON response.

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


def get_fallback_info(item: dict) -> tuple[str, str]:
    """Get fallback name and subject for an item."""
    is_thread = item.get("is_thread", False)
    messages = item.get("messages", [])

    if is_thread:
        subject = item.get("subject", "")
        participants = item.get("participants", [])
        fallback_name = participants[0] if participants else "Thread"
    else:
        email = messages[0] if messages else {}
        subject = email.get("subject", "")
        fallback_name = email.get("from_name", "Unknown")

    return fallback_name, subject


def parse_classification_response(
    response_text: str,
    fallback_name: str,
    subject: str,
    is_summary_only: bool = False,
    pre_category: str | None = None
) -> dict:
    """Parse a classification or summary response from Claude."""
    if is_summary_only:
        # Summary-only response is just plain text
        summary = response_text.strip() if response_text else f"{fallback_name}: {subject}"
        return {
            "category": pre_category or "FYI",
            "summary": summary,
            "action_items": None
        }
    else:
        # Full classification response is JSON
        try:
            parsed = parse_json_response(response_text)
            return {
                "category": parsed.get("category", "FYI").upper(),
                "summary": parsed.get("summary", f"{fallback_name}: {subject}"),
                "action_items": parsed.get("action_items")
            }
        except ValueError:
            return {
                "category": "FYI",
                "summary": f"{fallback_name}: {subject}",
                "action_items": None
            }


async def classify_items_parallel(
    items: list[dict],
    use_cache: bool = True,
    max_concurrent: int = 5,
) -> tuple[list[dict], dict]:
    """Classify items using cache and parallel processing.

    Returns:
        Tuple of (classified_items, stats_dict)
    """
    stats = {
        "cache_hits": 0,
        "cache_misses": 0,
        "claude_calls": 0,
        "total_cost": 0.0,
        "pre_classified": 0,
    }

    # Initialize cache if using it
    if use_cache:
        init_cache_db()

    # Phase 1: Check cache and prepare items
    cache_hits = []  # Items with cached results
    needs_processing = []  # Items that need Claude

    for item in items:
        messages = item.get("messages", [])
        if not messages:
            continue

        cache_key = get_cache_key(item)

        # Check cache first
        if use_cache and cache_key:
            cached = lookup_cache(cache_key)
            if cached:
                item["category"] = cached["category"]
                item["summary"] = cached["summary"]
                item["action_items"] = cached["action_items"]
                stats["cache_hits"] += 1
                cache_hits.append(item)
                continue

        # Not in cache - check if we can pre-classify category
        pre_category = classify_by_labels(item)
        if pre_category:
            stats["pre_classified"] += 1

        needs_processing.append({
            "item": item,
            "cache_key": cache_key,
            "pre_category": pre_category,
        })
        stats["cache_misses"] += 1

    # Phase 2: Build prompts for items needing processing
    prompts = []
    for entry in needs_processing:
        item = entry["item"]
        pre_category = entry["pre_category"]

        if pre_category:
            # Only need summary
            prompt = build_summarize_prompt(item)
        else:
            # Need full classification
            prompt = build_classify_prompt(item)

        metadata = {
            "index": items.index(item),
            "cache_key": entry["cache_key"],
            "pre_category": pre_category,
            "item": item,
        }
        prompts.append((prompt, metadata))

    # Phase 3: Process in parallel
    if prompts:
        total_prompts = len(prompts)
        print(f"🏷️  Processing {total_prompts} items ({stats['cache_hits']} from cache)...", file=sys.stderr, flush=True)

        def progress_callback(completed: int, total: int, metadata: dict):
            item = metadata["item"]
            is_thread = item.get("is_thread", False)
            if is_thread:
                subject = item.get("subject", "")[:30]
                display = f"Thread: {subject}..."
            else:
                messages = item.get("messages", [])
                email = messages[0] if messages else {}
                subject = email.get("subject", "")[:30]
                from_name = email.get("from_name", "Unknown")[:15]
                display = f"{from_name}: {subject}..."
            print(f"  [{completed}/{total}] {display}", file=sys.stderr, flush=True)

        results = await query_claude_batch(
            prompts,
            max_concurrent=max_concurrent,
            timeout_seconds=90,
            progress_callback=progress_callback,
        )
        stats["claude_calls"] = len(prompts)

        # Phase 4: Parse responses and update items
        for response_text, cost, metadata, error in results:
            item = metadata["item"]
            cache_key = metadata["cache_key"]
            pre_category = metadata["pre_category"]
            fallback_name, subject = get_fallback_info(item)

            stats["total_cost"] += cost

            if error:
                print(f"  Warning: error for '{subject[:30]}...': {error}", file=sys.stderr)
                item["category"] = pre_category or "FYI"
                item["summary"] = f"{fallback_name}: {subject}"
                item["action_items"] = None
            else:
                result = parse_classification_response(
                    response_text,
                    fallback_name,
                    subject,
                    is_summary_only=(pre_category is not None),
                    pre_category=pre_category,
                )
                item["category"] = result["category"]
                item["summary"] = result["summary"]
                item["action_items"] = result["action_items"]

                # Save to cache
                if use_cache and cache_key:
                    save_to_cache(
                        cache_key=cache_key,
                        category=item["category"],
                        summary=item["summary"],
                        action_items=item["action_items"],
                        cost_usd=cost,
                    )
    else:
        print(f"🏷️  All {stats['cache_hits']} items found in cache!", file=sys.stderr, flush=True)

    # Phase 5: Combine results (cache hits + processed)
    classified_items = []
    for item in items:
        messages = item.get("messages", [])
        if not messages:
            continue

        # Clean up messages (remove body_preview, labels from output)
        for msg in messages:
            msg.pop("body_preview", None)
            msg.pop("labels", None)
            msg.pop("references", None)
            msg.pop("filepath", None)
            msg.pop("body_length", None)

        classified_items.append(item)

    return classified_items, stats


def main():
    parser = argparse.ArgumentParser(description="Classify emails/threads using Claude Agent SDK")
    parser.add_argument("--grouped", required=True, help="Grouped emails JSON file (from group_threads.py)")
    parser.add_argument("--output", required=True, help="Output classified JSON file")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching (re-classify everything)")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent Claude requests (default: 5)")
    args = parser.parse_args()

    # Load grouped items
    with open(args.grouped) as f:
        grouped_data = json.load(f)

    items = grouped_data.get("items", [])
    total = len(items)

    print(f"🏷️ Classifying {total} items (threads + single emails)...", file=sys.stderr, flush=True)

    # Run async classification
    classified_items, stats = asyncio.run(
        classify_items_parallel(
            items,
            use_cache=not args.no_cache,
            max_concurrent=args.concurrency,
        )
    )

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
    print(f"   Cache hits: {stats['cache_hits']}, Cache misses: {stats['cache_misses']}", file=sys.stderr)
    print(f"   Category from labels: {stats['pre_classified']}", file=sys.stderr)
    print(f"   Claude SDK calls: {stats['claude_calls']} (concurrency: {args.concurrency})", file=sys.stderr)
    if stats["total_cost"] > 0:
        print(f"   💰 Total cost: ${stats['total_cost']:.4f}", file=sys.stderr)
    for cat in ["URGENT", "NEEDS_RESPONSE", "CALENDAR", "FINANCIAL", "FYI", "NEWSLETTER", "AUTOMATED"]:
        if cat in categories:
            print(f"   {cat}: {categories[cat]}", file=sys.stderr)

    print(f"\n✅ Output written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
