---
description: Use this skill when the user asks to "generate email brief", "email summary", "summarize my emails", "what emails did I get", "daily brief", "email digest", or wants a summary of recent emails.
---

# Email Brief Generator

Generate a summary brief of recent emails, classified by urgency and importance.

## Arguments

The user may specify a time duration like "last 2 days", "past week", "12 hours", etc. Default to 1 day if not specified.

Convert to duration format: 1d, 2d, 12h, 1w, 1mo

## Instructions

Follow these steps precisely, reporting progress after each step:

### Step 1: Fetch Recent Emails

```bash
uv run scripts/fetch_emails.py --since {DURATION} --output /tmp/emails_raw.json
```

Report: "📥 Found N emails in the last {duration}"

### Step 2: Parse Email Content

Read `/tmp/emails_raw.json`. For each email, parse its content:

```bash
uv run scripts/parse_eml.py {filename}
```

Process in batches of 10-20. Report progress: "📄 Parsing emails... (N/total)"

### Step 3: Classify and Summarize

For each email, determine:

**Category** - One of:
- `URGENT` - Explicit urgency (ASAP, deadline, time-sensitive), requires immediate action
- `NEEDS_RESPONSE` - Question asked, request made, waiting for your reply
- `FYI` - Informational, no action needed
- `NEWSLETTER` - Has CATEGORY_PROMOTIONS label, marketing/newsletter sender
- `AUTOMATED` - Has CATEGORY_UPDATES label, receipts, notifications, alerts

**Classification signals:**
- Labels with "CATEGORY_PROMOTIONS" → NEWSLETTER
- Labels with "CATEGORY_UPDATES" → AUTOMATED
- Keywords: "urgent", "ASAP", "deadline", "by EOD", "action required" → URGENT
- Questions to recipient, "please respond", "let me know" → NEEDS_RESPONSE

**Summary** - 1-2 sentences summarizing the email content

**Action Items** - Any explicit requests, deadlines, or actions (null if none)

For NEWSLETTER/AUTOMATED, brief summary like "Marketing email from [sender]" is sufficient.

Report progress: "🏷️ Classifying emails... (N/total)"

### Step 4: Create Classified JSON

Write to `/tmp/emails_classified.json`:

```json
{
  "emails": [
    {
      "message_num": 123,
      "uid": "abc123",
      "gmail_link": "https://mail.google.com/mail/u/0/#all/abc123",
      "from_name": "John Doe",
      "from_email": "john@example.com",
      "subject": "Q4 Budget Review",
      "date": "2024-12-13 10:30:00",
      "category": "NEEDS_RESPONSE",
      "summary": "John is asking for your review of the Q4 budget proposal before Friday.",
      "action_items": "Review budget proposal and respond by Friday"
    }
  ]
}
```

### Step 5: Render HTML Brief

```bash
uv run scripts/render_brief.py --input /tmp/emails_classified.json --since "{DURATION_TEXT}"
```

### Step 6: Final Report

Print summary:

```
📬 Email Brief Generated

Processed N emails from the last {duration}:
  🔴 Urgent: X
  🟡 Needs Response: Y
  🔵 FYI: Z
  📰 Newsletters: A
  ⚙️ Automated: B

Brief saved to: ~/MAIL/briefs/YYYY-MM-DD.html
```

Offer to open the brief in the browser.
