#!/usr/bin/env python3
# ABOUTME: Render classified emails to HTML using Jinja2 template
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


def organize_by_category(emails: list[dict]) -> list[dict]:
    """Organize emails into sections by category."""
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

    for email in emails:
        category = email.get("category", "FYI").upper()
        if category in sections:
            sections[category]["emails"].append(email)
        else:
            sections["FYI"]["emails"].append(email)

    # Return as list, ordered
    order = ["URGENT", "NEEDS_RESPONSE", "CALENDAR", "FINANCIAL", "FYI", "AUTOMATED", "NEWSLETTER"]
    return [sections[cat] for cat in order]


def render_brief(classified_emails: list[dict], since: str, output_path: Path) -> None:
    """Render the brief HTML from classified emails."""
    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("brief.html")

    # Add short date to each email
    for email in classified_emails:
        email["date_short"] = format_date_short(email.get("date", ""))

    # Organize into sections
    sections = organize_by_category(classified_emails)

    # Count stats
    total_count = len(classified_emails)
    urgent_count = len([e for e in classified_emails if e.get("category", "").upper() == "URGENT"])
    needs_response_count = len([e for e in classified_emails if e.get("category", "").upper() == "NEEDS_RESPONSE"])

    # Render
    html = template.render(
        date=datetime.now().strftime("%A, %B %d, %Y"),
        since=since,
        total_count=total_count,
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
        help="Input JSON file with classified emails"
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
    args = parser.parse_args()

    # Read input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        data = json.load(f)

    # Handle both formats: list of emails or {"emails": [...]}
    if isinstance(data, list):
        classified_emails = data
    else:
        classified_emails = data.get("emails", [])

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = BRIEFS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.html"

    # Render
    render_brief(classified_emails, args.since, output_path)


if __name__ == "__main__":
    main()
