---
name: email-brief
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
cd ~/MAIL && uv run scripts/fetch_emails.py --since {DURATION} --output /tmp/emails_raw.json
```

Report: "📥 Found N emails in the last {duration}"

### Step 2: Parse Email Content

Parse all emails using the batch parser:

```bash
cd ~/MAIL && uv run scripts/parse_eml.py --batch /tmp/emails_raw.json --output /tmp/emails_parsed.json
```

Report: "📄 Parsed N emails"

### Step 3: Classify and Summarize

**CRITICAL: You MUST read and analyze the actual email body content to generate summaries. Do NOT just repeat the subject line.**

Read `/tmp/emails_parsed.json` and `/tmp/emails_raw.json` to get both content and labels.

#### 3a. Pre-classify by Gmail labels

Use labels to identify low-value emails:
- Labels containing "CATEGORY_PROMOTIONS" → `NEWSLETTER`
- Labels containing "CATEGORY_UPDATES" → `AUTOMATED`

For NEWSLETTER/AUTOMATED emails, use brief template summaries.

#### 3b. Analyze remaining emails

For ALL other emails (not NEWSLETTER/AUTOMATED), you MUST analyze the email body and generate:

1. **Category**: URGENT | NEEDS_RESPONSE | FYI
   - URGENT: "urgent", "ASAP", "deadline", "by EOD", "action required"
   - NEEDS_RESPONSE: Direct questions, "please respond", "let me know"
   - FYI: Everything else

2. **Summary**: 1-2 sentences describing what the email is actually about
   - ✅ GOOD: "Sarah is asking for feedback on the new homepage design mockups before the client meeting on Monday."
   - ❌ BAD: "Sarah: New homepage design" (just repeating sender + subject)

3. **Action items**: Any requests, deadlines, or actions (or null)

Report: "🏷️ Classified N emails"

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
cd ~/MAIL && uv run scripts/render_brief.py --input /tmp/emails_classified.json --since "{DURATION_TEXT}"
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
