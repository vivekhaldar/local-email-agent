#!/usr/bin/env python3
# ABOUTME: Render classified emails/threads to HTML using Jinja2 template
# ABOUTME: Usage: uv run scripts/render_brief.py --input classified.json --output brief.html

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Error: jinja2 not installed. Run: uv pip install jinja2", file=sys.stderr)
    sys.exit(1)

# Paths
TEMPLATE_DIR = Path.home() / "MAIL" / "templates"
BRIEFS_DIR = Path.home() / "MAIL" / "briefs"


def format_date_short(date_str: str) -> str:
    """Format date for display in email card."""
    try:
        # Try parsing various formats
        for fmt in ["%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"]:
            try:
                dt = datetime.strptime(date_str.split(" +")[0].split(" -")[0], fmt.split(" %z")[0].split(" %Z")[0])
                return dt.strftime("%b %d, %I:%M %p")
            except ValueError:
                continue
        return date_str[:16]
    except Exception:
        return date_str[:16] if date_str else ""


def organize_by_category(items: list[dict]) -> list[dict]:
    """Organize items (threads and single emails) into sections by category."""
    sections = {
        "URGENT": {
            "name": "Urgent",
            "icon": "🔴",
            "css_class": "urgent",
            "emails": []
        },
        "NEEDS_RESPONSE": {
            "name": "Needs Response",
            "icon": "🟡",
            "css_class": "needs-response",
            "emails": []
        },
        "CALENDAR": {
            "name": "Calendar & Events",
            "icon": "📅",
            "css_class": "calendar",
            "emails": []
        },
        "FINANCIAL": {
            "name": "Financial",
            "icon": "💰",
            "css_class": "financial",
            "emails": []
        },
        "FYI": {
            "name": "FYI",
            "icon": "🔵",
            "css_class": "fyi",
            "emails": []
        },
        "NEWSLETTER": {
            "name": "Newsletters & Promotions",
            "icon": "📰",
            "css_class": "newsletter",
            "emails": []
        },
        "AUTOMATED": {
            "name": "Automated & Updates",
            "icon": "⚙️",
            "css_class": "automated",
            "emails": []
        }
    }

    for item in items:
        category = item.get("category", "FYI").upper()
        if category in sections:
            sections[category]["emails"].append(item)
        else:
            sections["FYI"]["emails"].append(item)

    # Return as list, ordered
    order = ["URGENT", "NEEDS_RESPONSE", "CALENDAR", "FINANCIAL", "FYI", "AUTOMATED", "NEWSLETTER"]
    return [sections[cat] for cat in order]


def prepare_item_for_template(item: dict) -> dict:
    """Prepare an item (thread or single email) for template rendering."""
    is_thread = item.get("is_thread", False)
    messages = item.get("messages", [])

    if not messages:
        return item

    # Format dates for all messages
    for msg in messages:
        msg["date_short"] = format_date_short(msg.get("date", ""))

    if is_thread:
        # Thread: use thread-level data
        item["display_name"] = ", ".join(item.get("participants", [])[:3])
        if len(item.get("participants", [])) > 3:
            item["display_name"] += f" +{len(item['participants']) - 3}"
        item["display_subject"] = item.get("subject", messages[0].get("subject", ""))
        item["date_short"] = format_date_short(item.get("last_date", messages[-1].get("date", "")))
        item["message_count"] = len(messages)
        # Gmail link from the item (set by group_threads) or most recent message
        if not item.get("gmail_link"):
            item["gmail_link"] = messages[-1].get("gmail_link", "")
    else:
        # Single email: use the message data
        email = messages[0]
        item["display_name"] = email.get("from_name", "Unknown")
        item["display_subject"] = email.get("subject", "")
        item["date_short"] = format_date_short(email.get("date", ""))
        item["message_count"] = 1
        item["gmail_link"] = email.get("gmail_link", "")

    return item


def render_brief(classified_items: list[dict], since: str, output_path: Path) -> None:
    """Render the brief HTML from classified items."""
    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("brief.html")

    # Prepare each item for template
    for item in classified_items:
        prepare_item_for_template(item)

    # Organize into sections
    sections = organize_by_category(classified_items)

    # Count stats
    total_count = len(classified_items)
    urgent_count = len([i for i in classified_items if i.get("category", "").upper() == "URGENT"])
    needs_response_count = len([i for i in classified_items if i.get("category", "").upper() == "NEEDS_RESPONSE"])
    thread_count = len([i for i in classified_items if i.get("is_thread")])

    # Render
    html = template.render(
        date=datetime.now().strftime("%A, %B %d, %Y"),
        since=since,
        total_count=total_count,
        thread_count=thread_count,
        urgent_count=urgent_count,
        needs_response_count=needs_response_count,
        sections=sections,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    output_path.write_text(html)
    print(f"Brief written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Render classified emails to HTML")
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON file with classified items"
    )
    parser.add_argument(
        "--output",
        help="Output HTML file path (default: ~/MAIL/briefs/YYYY-MM-DD.html)"
    )
    parser.add_argument(
        "--since",
        default="24 hours",
        help="Duration string for display (e.g., '24 hours', '2 days')"
    )
    parser.add_argument(
        "--duration",
        default="1d",
        help="Compact duration code for filename (e.g., '1d', '3d', '1w')"
    )
    args = parser.parse_args()

    # Read input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        data = json.load(f)

    # Handle both formats: list or {"items": [...]}
    if isinstance(data, list):
        classified_items = data
    else:
        classified_items = data.get("items", data.get("emails", []))

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_path = BRIEFS_DIR / f"{date_str}_{args.duration}.html"

    # Render
    render_brief(classified_items, args.since, output_path)


if __name__ == "__main__":
    main()
