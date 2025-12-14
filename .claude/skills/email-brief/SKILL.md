---
name: email-brief
description: Use this skill when the user asks to "generate email brief", "email summary", "summarize my emails", "what emails did I get", "daily brief", "email digest", or wants a summary of recent emails.
---

# Email Brief Generator

Generate a summary brief of recent emails, classified by urgency and importance. Emails in the same thread are grouped and summarized together.

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

### Step 3: Group Threads

Group related emails into threads based on Message-ID and In-Reply-To headers:

```bash
cd ~/MAIL && uv run scripts/group_threads.py \
    --input /tmp/emails_parsed.json \
    --raw /tmp/emails_raw.json \
    --output /tmp/emails_grouped.json
```

This script:
- Links emails by Message-ID, In-Reply-To, and References headers
- Falls back to subject-line matching for emails missing thread headers
- Groups multi-message threads together
- Single emails remain ungrouped

Report the grouping stats from the script output.

### Step 4: Classify and Summarize

Run the classification script which uses `claude -p` with Haiku model:

```bash
cd ~/MAIL && uv run scripts/classify_with_claude.py \
    --grouped /tmp/emails_grouped.json \
    --output /tmp/emails_classified.json
```

This script:
- Pre-classifies NEWSLETTER/AUTOMATED items using Gmail labels (fast, no LLM)
- Calls `claude -p --model haiku` for each remaining item to classify and summarize
- For threads: summarizes the entire conversation as a single unit
- Categories: URGENT, NEEDS_RESPONSE, CALENDAR, FINANCIAL, FYI, NEWSLETTER, AUTOMATED

The script prints progress as it processes each item.

Report the final stats from the script output.

### Step 5: Render HTML Brief

```bash
cd ~/MAIL && uv run scripts/render_brief.py --input /tmp/emails_classified.json --since "{DURATION_TEXT}"
```

### Step 6: Final Report

Print summary:

```
📬 Email Brief Generated

Processed N items from the last {duration}:
  📧 Threads: X
  📨 Single emails: Y
  🔴 Urgent: Z
  🟡 Needs Response: W
  📅 Calendar: V
  💰 Financial: U
  🔵 FYI: T
  📰 Newsletters: A
  ⚙️ Automated: B

Brief saved to: ~/MAIL/briefs/YYYY-MM-DD.html
```

Offer to open the brief in the browser.
