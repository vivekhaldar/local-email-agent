#!/usr/bin/env python3
# ABOUTME: Parse EML files and extract headers and body as JSON
# ABOUTME: Usage: uv run scripts/parse_eml.py <eml_file> or pipe JSON list of filenames

import argparse
import email
import email.policy
import json
import re
import sys
from email.header import decode_header
from html import unescape
from pathlib import Path

# Base path for email files
GMAIL_DIR = Path.home() / "MAIL" / "gmail"

# Maximum body preview length
MAX_BODY_PREVIEW = 1500


def decode_mime_header(header_value: str) -> str:
    """Decode MIME-encoded header (e.g., =?utf-8?Q?...?=)."""
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


def extract_name_and_email(from_header: str) -> tuple[str, str]:
    """Extract display name and email from From header."""
    from_header = decode_mime_header(from_header)

    # Pattern: "Name" <email> or Name <email> or just email
    match = re.match(r'^"?([^"<]*)"?\s*<?([^>]+@[^>]+)>?$', from_header.strip())
    if match:
        name = match.group(1).strip()
        email_addr = match.group(2).strip()
        if not name:
            name = email_addr.split("@")[0]
        return name, email_addr

    # Fallback: just return as-is
    return from_header, from_header


def strip_html(html: str) -> str:
    """Convert HTML to plain text."""
    # Remove style and script tags with content
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Replace <br> and <p> with newlines
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</div>', '\n', html, flags=re.IGNORECASE)

    # Remove all other tags
    html = re.sub(r'<[^>]+>', '', html)

    # Decode HTML entities
    text = unescape(html)

    # Normalize whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)

    return text.strip()


def get_body_text(msg: email.message.Message) -> str:
    """Extract plain text body from email message."""
    body_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
                except Exception:
                    pass
            elif content_type == "text/html" and not body_parts:
                # Use HTML only if no plain text found
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    body_parts.append(strip_html(html))
                except Exception:
                    pass
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            if content_type == "text/html":
                body_parts.append(strip_html(payload.decode(charset, errors="replace")))
            else:
                body_parts.append(payload.decode(charset, errors="replace"))
        except Exception:
            pass

    return "\n".join(body_parts).strip()


def parse_eml(filepath: Path) -> dict:
    """Parse a single EML file and return structured data."""
    try:
        with open(filepath, "rb") as f:
            msg = email.message_from_binary_file(f, policy=email.policy.default)
    except Exception as e:
        return {"error": str(e), "filepath": str(filepath)}

    from_name, from_email = extract_name_and_email(msg.get("From", ""))
    subject = decode_mime_header(msg.get("Subject", "(no subject)"))
    date = msg.get("Date", "")
    to = decode_mime_header(msg.get("To", ""))

    # Extract thread headers for threading support
    message_id = msg.get("Message-ID", "")
    if message_id:
        message_id = message_id.strip().strip("<>")

    in_reply_to = msg.get("In-Reply-To", "")
    if in_reply_to:
        in_reply_to = in_reply_to.strip().strip("<>")

    references = msg.get("References", "")
    if references:
        # References is a space/newline-separated list of Message-IDs
        references = " ".join(references.split())

    body_text = get_body_text(msg)
    body_preview = body_text[:MAX_BODY_PREVIEW]
    if len(body_text) > MAX_BODY_PREVIEW:
        body_preview += "..."

    return {
        "filepath": str(filepath),
        "from_email": from_email,
        "from_name": from_name,
        "to": to,
        "subject": subject,
        "date": date,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "body_preview": body_preview,
        "body_length": len(body_text)
    }


def main():
    parser = argparse.ArgumentParser(description="Parse EML file(s) and output JSON")
    parser.add_argument(
        "eml_file",
        nargs="?",
        help="Path to EML file (relative to ~/MAIL/gmail/ or absolute)"
    )
    parser.add_argument(
        "--batch",
        help="JSON file with emails to parse (from fetch_emails.py output)"
    )
    parser.add_argument(
        "--output",
        help="Output file for batch results (default: stdout)"
    )
    args = parser.parse_args()

    if args.batch:
        # Read JSON from file
        with open(args.batch) as f:
            input_data = json.load(f)

        # Handle both formats: list of filenames or {emails: [...]} from fetch_emails.py
        if isinstance(input_data, list):
            emails = input_data
        elif "emails" in input_data:
            emails = input_data["emails"]
        else:
            emails = input_data.get("filenames", [])

        results = []
        for item in emails:
            # Support both string filenames and email objects with 'filename' key
            if isinstance(item, str):
                filename = item
                message_num = None
            else:
                filename = item.get("filename", "")
                message_num = item.get("message_num")

            filepath = GMAIL_DIR / filename
            result = parse_eml(filepath)
            if message_num is not None:
                result["message_num"] = message_num
            results.append(result)

        output_json = json.dumps(results, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output_json)
            print(f"Parsed {len(results)} emails to {args.output}", file=sys.stderr)
        else:
            print(output_json)

    elif args.eml_file:
        # Parse single file
        filepath = Path(args.eml_file)
        if not filepath.is_absolute():
            filepath = GMAIL_DIR / filepath

        result = parse_eml(filepath)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
