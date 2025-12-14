#!/usr/bin/env python3
# ABOUTME: Natural language search over email archive using hybrid keyword + LLM approach
# ABOUTME: Usage: uv run scripts/email_search.py "find emails about a google interview"

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# Paths
DB_PATH = Path.home() / "MAIL" / "gmail" / "msg-db.sqlite"
GMAIL_DIR = Path.home() / "MAIL" / "gmail"
GMAIL_BASE_URL = "https://mail.google.com/mail/u/0/#all"
TEMPLATES_DIR = Path.home() / "MAIL" / "templates"
SEARCHES_DIR = Path.home() / "MAIL" / "searches"

# Limits
MAX_CANDIDATES = 100
MAX_RESULTS = 10
MAX_BODY_CHARS = 1000


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '1d', '12h', '1w', '1mo' into timedelta."""
    match = re.match(r"^(\d+)(h|d|w|mo|y)$", duration_str.lower())
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}. Use: 1d, 12h, 1w, 1mo, 1y")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    elif unit == "mo":
        return timedelta(days=value * 30)
    elif unit == "y":
        return timedelta(days=value * 365)
    else:
        raise ValueError(f"Unknown unit: {unit}")


def call_claude(prompt: str, timeout: int = 90) -> str:
    """Call claude CLI and return response text."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "haiku", "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            print(f"Warning: claude returned {result.returncode}", file=sys.stderr)
            return ""

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        print("Warning: claude timed out", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Warning: claude error: {e}", file=sys.stderr)
        return ""


def parse_query(query: str) -> dict:
    """Use LLM to extract search parameters from natural language query."""
    prompt = f"""Extract search parameters from this email search query. Be generous with keywords - include all relevant terms.

Query: "{query}"

Return ONLY this JSON (no markdown, no explanation):
{{"people": ["names to search in From/To"], "keywords": ["topic keywords to search"], "date_hint": "time hint like 'last year' or null"}}

Examples:
- "what did Sarah say about the budget" -> {{"people": ["Sarah"], "keywords": ["budget"], "date_hint": null}}
- "find emails about google interview" -> {{"people": [], "keywords": ["google", "interview"], "date_hint": null}}
- "tax documents from last year" -> {{"people": [], "keywords": ["tax", "documents"], "date_hint": "last year"}}"""

    response = call_claude(prompt)

    # Parse JSON from response
    try:
        # Handle markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        return json.loads(response.strip())
    except json.JSONDecodeError:
        # Fallback: use query words as keywords
        words = [w for w in query.split() if len(w) > 2]
        return {"people": [], "keywords": words, "date_hint": None}


def date_hint_to_range(hint: str) -> tuple[datetime, datetime] | None:
    """Convert date hint to datetime range."""
    if not hint:
        return None

    now = datetime.now()
    hint_lower = hint.lower()

    if "last year" in hint_lower or "past year" in hint_lower:
        return (now - timedelta(days=365), now)
    elif "last month" in hint_lower or "past month" in hint_lower:
        return (now - timedelta(days=30), now)
    elif "last week" in hint_lower or "past week" in hint_lower:
        return (now - timedelta(days=7), now)
    elif "this year" in hint_lower:
        return (datetime(now.year, 1, 1), now)
    elif match := re.search(r"(\d{4})", hint):
        year = int(match.group(1))
        return (datetime(year, 1, 1), datetime(year, 12, 31, 23, 59, 59))

    return None


def search_candidates(keywords: list[str], people: list[str], since: datetime | None, until: datetime | None) -> list[dict]:
    """Search for candidate emails using SQLite + grep."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build date filter
    date_conditions = []
    params = []

    if since:
        date_conditions.append("m.message_internaldate >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    if until:
        date_conditions.append("m.message_internaldate <= ?")
        params.append(until.strftime("%Y-%m-%d %H:%M:%S"))

    where_clause = " AND ".join(date_conditions) if date_conditions else "1=1"

    # Get candidate messages by date
    query = f"""
    SELECT
        m.message_num,
        m.message_filename,
        m.message_internaldate,
        u.uid,
        GROUP_CONCAT(l.label, '|') as labels
    FROM messages m
    LEFT JOIN uids u ON m.message_num = u.message_num
    LEFT JOIN labels l ON m.message_num = l.message_num
    WHERE {where_clause}
    GROUP BY m.message_num
    ORDER BY m.message_internaldate DESC
    LIMIT 10000
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    # Convert to list of dicts
    candidates = []
    for row in rows:
        labels = row["labels"].split("|") if row["labels"] else []
        # Skip promotional/automated unless explicitly searching for them
        if "CATEGORY_PROMOTIONS" in labels or "CATEGORY_UPDATES" in labels:
            continue

        uid = row["uid"] or ""
        candidates.append({
            "message_num": row["message_num"],
            "uid": uid,
            "gmail_link": f"{GMAIL_BASE_URL}/{uid}" if uid else "",
            "filename": row["message_filename"],
            "date": row["message_internaldate"],
            "labels": labels
        })

    if not keywords and not people:
        return candidates[:MAX_CANDIDATES]

    # Filter by keywords using grep on EML files
    matched = []
    search_terms = keywords + people

    for candidate in candidates:
        if len(matched) >= MAX_CANDIDATES:
            break

        filepath = GMAIL_DIR / candidate["filename"]
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(errors="replace").lower()

            # Check if any search term matches
            matches = sum(1 for term in search_terms if term.lower() in content)
            if matches > 0:
                candidate["match_score"] = matches
                matched.append(candidate)
        except Exception:
            continue

    # Sort by match score, then by date
    matched.sort(key=lambda x: (-x.get("match_score", 0), x["date"]), reverse=True)

    return matched[:MAX_CANDIDATES]


def parse_eml_file(filepath: Path) -> dict:
    """Parse EML file and extract key fields."""
    import email
    import email.policy
    from email.header import decode_header

    def decode_mime_header(header_value: str) -> str:
        if not header_value:
            return ""
        decoded_parts = []
        for part, charset in decode_header(header_value):
            if isinstance(part, bytes):
                charset = charset or "utf-8"
                try:
                    decoded_parts.append(part.decode(charset, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    decoded_parts.append(part.decode("utf-8", errors="replace"))
            else:
                decoded_parts.append(part)
        return "".join(decoded_parts)

    def get_body_text(msg) -> str:
        body_parts = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                body_parts.append(payload.decode(charset, errors="replace"))
            except Exception:
                pass
        return "\n".join(body_parts).strip()

    try:
        with open(filepath, "rb") as f:
            msg = email.message_from_binary_file(f, policy=email.policy.default)
    except Exception as e:
        return {"error": str(e)}

    from_header = decode_mime_header(msg.get("From", ""))
    # Extract name and email from From header
    match = re.match(r'^"?([^"<]*)"?\s*<?([^>]+@[^>]+)>?$', from_header.strip())
    if match:
        from_name = match.group(1).strip() or match.group(2).split("@")[0]
        from_email = match.group(2).strip()
    else:
        from_name = from_header
        from_email = from_header

    subject = decode_mime_header(msg.get("Subject", "(no subject)"))
    date = msg.get("Date", "")
    body = get_body_text(msg)

    return {
        "from_name": from_name,
        "from_email": from_email,
        "subject": subject,
        "date": date,
        "body_preview": body[:MAX_BODY_CHARS] + ("..." if len(body) > MAX_BODY_CHARS else "")
    }


def rank_and_parse_results(candidates: list[dict], keywords: list[str], people: list[str], limit: int = MAX_RESULTS) -> list[dict]:
    """Parse EML files and rank results."""
    results = []
    search_terms = [t.lower() for t in keywords + people]

    for candidate in candidates[:MAX_CANDIDATES]:
        filepath = GMAIL_DIR / candidate["filename"]
        if not filepath.exists():
            continue

        parsed = parse_eml_file(filepath)
        if "error" in parsed:
            continue

        # Calculate relevance score
        score = candidate.get("match_score", 0)

        # Boost for matches in subject
        subject_lower = parsed["subject"].lower()
        for term in search_terms:
            if term in subject_lower:
                score += 3

        # Boost for matches in sender
        sender_lower = (parsed["from_name"] + " " + parsed["from_email"]).lower()
        for person in people:
            if person.lower() in sender_lower:
                score += 5

        results.append({
            "message_num": candidate["message_num"],
            "gmail_link": candidate["gmail_link"],
            "from_name": parsed["from_name"],
            "from_email": parsed["from_email"],
            "subject": parsed["subject"],
            "date": candidate["date"],
            "body_preview": parsed["body_preview"],
            "score": score
        })

    # Sort by score descending
    results.sort(key=lambda x: -x["score"])

    return results[:limit]


def generate_answer(query: str, results: list[dict]) -> str:
    """Use LLM to synthesize an answer from search results."""
    if not results:
        return "No relevant emails found for your query."

    # Build context from results
    email_context = []
    for i, r in enumerate(results[:7], 1):  # Limit to top 7 for prompt size
        email_context.append(f"""
--- Email {i} ---
From: {r['from_name']} <{r['from_email']}>
Date: {r['date']}
Subject: {r['subject']}
Body excerpt:
{r['body_preview']}
""")

    prompt = f"""Based on these emails, answer the user's question. Be concise and specific.

QUESTION: {query}

EMAILS:
{"".join(email_context)}

Provide:
1. A direct answer to the question (2-4 sentences)
2. Cite specific emails by number when referencing information (e.g., "In Email 2, ...")

If the emails don't contain enough information to fully answer the question, say so."""

    return call_claude(prompt, timeout=120)


def format_date(date_str: str) -> str:
    """Format date string for display."""
    try:
        # Try parsing ISO format
        dt = datetime.fromisoformat(date_str.replace(" ", "T"))
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return date_str[:16]


def print_results(query: str, results: list[dict], answer: str, list_only: bool):
    """Print formatted search results."""
    print(f"\n🔍 Searching for: \"{query}\"")
    print(f"\n📊 Found {len(results)} relevant email{'s' if len(results) != 1 else ''}")

    if not list_only and answer:
        print("\n" + "━" * 60)
        print("\n💬 ANSWER:\n")
        print(answer)

    print("\n" + "━" * 60)
    print("\n📧 SOURCES:\n")

    for i, r in enumerate(results, 1):
        print(f"{i}. {r['from_name']} <{r['from_email']}>")
        print(f"   {r['subject']}")
        date_formatted = format_date(r['date'])
        # Strip HTML tags from snippet for cleaner CLI output
        clean_preview = re.sub(r"<[^>]+>", " ", r['body_preview'])
        clean_preview = re.sub(r"\s+", " ", clean_preview).strip()
        snippet = clean_preview[:80]
        if snippet:
            print(f"   {date_formatted} · \"{snippet}...\"")
        else:
            print(f"   {date_formatted}")
        if r['gmail_link']:
            print(f"   → {r['gmail_link']}")
        print()


def strip_html_tags(text: str) -> str:
    """Remove HTML tags from text."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def render_html_results(query: str, results: list[dict], answer: str) -> Path:
    """Render search results to HTML file and return the path."""
    # Ensure output directory exists
    SEARCHES_DIR.mkdir(parents=True, exist_ok=True)

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("search-results.html")

    # Format results for template
    formatted_results = []
    for r in results:
        # Clean snippet: strip HTML tags and normalize whitespace
        snippet = strip_html_tags(r["body_preview"])[:80] if r["body_preview"] else ""
        formatted_results.append({
            "from_name": r["from_name"],
            "from_email": r["from_email"],
            "subject": r["subject"],
            "date_formatted": format_date(r["date"]),
            "snippet": snippet,
            "gmail_link": r["gmail_link"]
        })

    # Generate HTML
    html = template.render(
        query=query,
        answer=answer,
        results=formatted_results,
        result_count=len(results),
        generated_at=datetime.now().strftime("%B %d, %Y at %I:%M %p")
    )

    # Save to file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_query = re.sub(r"[^\w\s-]", "", query)[:30].strip().replace(" ", "-")
    filename = f"search-{timestamp}-{safe_query}.html"
    output_path = SEARCHES_DIR / filename

    output_path.write_text(html)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Natural language search over email archive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "what did Sarah say about the budget?"
  %(prog)s "find emails about google interview"
  %(prog)s "tax documents" --since=1y
  %(prog)s "invoice from AWS" --list-only
        """
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Natural language search query"
    )
    parser.add_argument(
        "--since",
        help="Only search emails from this duration ago (e.g., 1d, 1w, 1mo, 1y)"
    )
    parser.add_argument(
        "--from",
        dest="from_filter",
        help="Filter by sender name or email"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Just list matching emails without LLM answer"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=MAX_RESULTS,
        help=f"Maximum number of results (default: {MAX_RESULTS})"
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip HTML output generation"
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't automatically open HTML in browser"
    )
    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    # Check database exists
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    query = args.query
    result_limit = args.limit

    # Step 1: Parse query with LLM
    print("🔎 Analyzing query...", file=sys.stderr)
    parsed = parse_query(query)
    keywords = parsed.get("keywords", [])
    people = parsed.get("people", [])
    date_hint = parsed.get("date_hint")

    # Add --from filter to people if provided
    if args.from_filter:
        people.append(args.from_filter)

    # Determine date range
    since = None
    until = None

    if args.since:
        try:
            delta = parse_duration(args.since)
            since = datetime.now() - delta
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif date_hint:
        date_range = date_hint_to_range(date_hint)
        if date_range:
            since, until = date_range

    # Step 2: Search for candidates
    print(f"🔍 Searching for: {keywords + people}...", file=sys.stderr)
    candidates = search_candidates(keywords, people, since, until)

    if not candidates:
        print("\n❌ No emails found matching your query.")
        sys.exit(0)

    # Step 3: Parse and rank results
    print(f"📄 Analyzing {len(candidates)} candidates...", file=sys.stderr)
    results = rank_and_parse_results(candidates, keywords, people, result_limit)

    if not results:
        print("\n❌ No relevant emails found.")
        sys.exit(0)

    # Step 4: Generate answer (unless --list-only)
    answer = ""
    if not args.list_only:
        print("💭 Generating answer...", file=sys.stderr)
        answer = generate_answer(query, results)

    # Step 5: Print results
    print_results(query, results, answer, args.list_only)

    # Step 6: Generate HTML output
    if not args.no_html:
        print("\n📄 Generating HTML...", file=sys.stderr)
        html_path = render_html_results(query, results, answer)
        print(f"\n💾 HTML saved to: {html_path}")

        if not args.no_open:
            webbrowser.open(f"file://{html_path}")


if __name__ == "__main__":
    main()
