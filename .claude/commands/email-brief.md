# Email Brief Generator

Generate a summary brief of recent emails, classified by urgency and importance.

## Arguments

$ARGUMENTS - Time duration to look back (e.g., "1d", "12h", "1w", "2d"). Default: "1d"

## Instructions

You are generating an email brief. Follow these steps precisely:

### Step 1: Fetch Recent Emails

Run the fetch script to get recent emails:

```bash
uv run scripts/fetch_emails.py --since $ARGUMENTS --output /tmp/emails_raw.json
```

Report how many emails were found.

### Step 2: Parse Email Content

For each email, parse its content. Process in batches of 20 for efficiency.

Read the raw emails file and for each email, run:
```bash
uv run scripts/parse_eml.py <filename>
```

### Step 3: Classify and Summarize

For each email, determine:

1. **Category** - One of:
   - `URGENT` - Explicit urgency (ASAP, deadline, time-sensitive), requires immediate action
   - `NEEDS_RESPONSE` - Question asked, request made, waiting for your reply
   - `FYI` - Informational, no action needed
   - `NEWSLETTER` - Has CATEGORY_PROMOTIONS label, or is from a newsletter/marketing sender
   - `AUTOMATED` - Has CATEGORY_UPDATES label, receipts, notifications, alerts

2. **Summary** - 1-2 sentence summary of the email content

3. **Action Items** - Any explicit requests, deadlines, or actions needed (or null if none)

Use these signals for classification:
- Labels containing "CATEGORY_PROMOTIONS" → NEWSLETTER
- Labels containing "CATEGORY_UPDATES" → AUTOMATED
- Keywords like "urgent", "ASAP", "deadline", "by EOD", "action required" → URGENT
- Questions directed at the recipient, "please respond", "let me know" → NEEDS_RESPONSE
- Newsletters, marketing, promotions → NEWSLETTER (skip detailed summarization)

### Step 4: Create Classified JSON

Create a JSON file at `/tmp/emails_classified.json` with this structure:

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
      "summary": "John is asking for your review of the Q4 budget proposal before Friday's meeting.",
      "action_items": "Review budget proposal and respond by Friday"
    }
  ]
}
```

For NEWSLETTER and AUTOMATED emails, you can use a brief summary like "Marketing email from [sender]" or "Notification from [service]".

### Step 5: Render HTML Brief

```bash
uv run scripts/render_brief.py --input /tmp/emails_classified.json --since "$ARGUMENTS"
```

This creates the HTML brief in `~/MAIL/briefs/`.

### Step 6: Report Summary

Print a summary:
- Total emails processed
- Count by category (Urgent, Needs Response, FYI, etc.)
- Path to the generated HTML brief
- Offer to open it in the browser

## Example Output

```
📬 Email Brief Generated

Processed 47 emails from the last 24 hours:
  🔴 Urgent: 2
  🟡 Needs Response: 5
  🔵 FYI: 15
  📰 Newsletters: 18
  ⚙️ Automated: 7

Brief saved to: ~/MAIL/briefs/2024-12-13.html
```
