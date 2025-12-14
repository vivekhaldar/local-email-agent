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

**CRITICAL: You MUST read and analyze the actual email body content to generate summaries. Do NOT just repeat the subject line.**

#### 3a. Pre-classify by Gmail labels

First, use labels to identify low-value emails:
- Labels containing "CATEGORY_PROMOTIONS" → `NEWSLETTER`
- Labels containing "CATEGORY_UPDATES" → `AUTOMATED`

For NEWSLETTER/AUTOMATED emails, use template summaries:
- NEWSLETTER: "Marketing email from [sender] about [topic from subject]"
- AUTOMATED: "Notification from [sender]: [brief description]"

#### 3b. LLM-based classification for remaining emails

For ALL other emails (not NEWSLETTER/AUTOMATED), you MUST:

1. **Read the email body** from the parsed content
2. **Send to LLM** with this prompt for each email (or batch 5-10 together):

```
Analyze this email and provide:
1. Category: URGENT | NEEDS_RESPONSE | FYI
2. Summary: 1-2 sentences describing what this email is actually about (NOT just the subject line)
3. Action items: Any requests, deadlines, or required actions (or null)

URGENT signals: "urgent", "ASAP", "deadline", "by EOD", "action required", time-sensitive requests
NEEDS_RESPONSE signals: Direct questions, "please respond", "let me know", "what do you think"
FYI: Everything else - informational, announcements, updates

Email:
From: {from_name} <{from_email}>
Subject: {subject}
Body:
{body_preview}
```

3. **Use the LLM response** for the summary - it must reflect the actual email content

#### Summary quality requirements

- ✅ GOOD: "Sarah is asking for feedback on the new homepage design mockups before the client meeting on Monday."
- ✅ GOOD: "Weekly team standup notes covering sprint progress, blockers on the API migration, and holiday schedule."
- ❌ BAD: "Sarah: New homepage design" (just repeating sender + subject)
- ❌ BAD: "Team Update: Weekly standup notes" (just repeating subject)

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
