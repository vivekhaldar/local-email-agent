# Thread Grouping in Email Brief

## Goal

Group emails that belong to the same thread and summarize them as a single unit instead of showing each message separately.

**Current behavior**: Each email in a thread appears separately with its own summary
**Desired behavior**: Thread appears as one item with message count, single summary, expandable to see individual messages

## Technical Context

**Thread detection headers in EML files:**
- `Message-ID`: Unique identifier for each message
- `In-Reply-To`: Points to parent message's Message-ID
- `References`: Chain of all Message-IDs in the conversation

**Current pipeline:**
1. `fetch_emails.py` → gets emails from SQLite
2. `parse_eml.py` → parses each email (does NOT extract thread headers currently)
3. `classify_with_claude.py` → classifies each email individually
4. `render_brief.py` → renders each email as separate card

## Implementation Plan

### Step 1: Enhance parse_eml.py to extract thread headers

Add extraction of:
```python
result["message_id"] = msg.get("Message-ID", "").strip("<>")
result["in_reply_to"] = msg.get("In-Reply-To", "").strip("<>")
result["references"] = msg.get("References", "")  # space-separated list
```

**File**: `~/MAIL/scripts/parse_eml.py`

### Step 2: Create thread grouping script

New script: `~/MAIL/scripts/group_threads.py`

```
Usage: uv run scripts/group_threads.py --input parsed.json --raw raw.json --output grouped.json
```

**Algorithm:**
1. Build a map: `message_id → email`
2. For each email with `in_reply_to`, link to parent
3. Group emails that share the same thread root
4. Sort messages within each thread chronologically
5. Output structure:
```json
{
  "items": [
    {
      "is_thread": true,
      "thread_id": "...",
      "message_count": 3,
      "participants": ["Alice", "Bob"],
      "subject": "Re: AI Data Intelligence @ Google!",
      "messages": [email1, email2, email3]
    },
    {
      "is_thread": false,
      "messages": [single_email]
    }
  ]
}
```

**Thread root detection:**
- Walk up `in_reply_to` chain until no parent found
- Fallback: If headers missing, use normalized subject ("Re:", "Fwd:" stripped)

### Step 3: Modify classify_with_claude.py to handle threads

When classifying a thread (multiple messages):
- Concatenate all messages in chronological order
- Send as single context to Haiku
- Return single category and summary for the thread

**Modified prompt for threads:**
```
This is an email thread with N messages. Summarize the entire conversation:
[Message 1: From X, Date Y]
Body...
[Message 2: From X, Date Y]
Body...

Provide JSON:
{"category": "...", "summary": "conversation summary", "action_items": "..."}
```

### Step 4: Update render_brief.py for thread display

- Detect `is_thread: true` items
- Pass thread metadata to template (message_count, participants, date_range)
- Gmail link uses thread view URL

### Step 5: Update brief.html template

Thread card design:
- Header: Participants + "· 3 messages"
- Subject line
- Single thread summary (not per-message)
- When expanded: shows individual message senders/dates
- Gmail link opens thread view

## Data Flow (After Changes)

```
fetch_emails.py → emails_raw.json
       ↓
parse_eml.py → emails_parsed.json (now includes message_id, in_reply_to)
       ↓
group_threads.py → emails_grouped.json (emails grouped into threads)
       ↓
classify_with_claude.py → emails_classified.json (threads classified as units)
       ↓
render_brief.py → brief.html (threads rendered as collapsible groups)
```

## Files to Modify

1. `~/MAIL/scripts/parse_eml.py` - Add thread header extraction
2. `~/MAIL/scripts/group_threads.py` - **NEW**: Thread grouping logic
3. `~/MAIL/scripts/classify_with_claude.py` - Handle thread classification
4. `~/MAIL/scripts/render_brief.py` - Thread-aware rendering
5. `~/MAIL/templates/brief.html` - Thread card UI
6. `~/MAIL/.claude/skills/email-brief/SKILL.md` - Add group_threads.py step

## Edge Cases

1. **Single-message "threads"**: Treat as regular email (is_thread: false)
2. **Thread spans multiple days**: Group by thread, use most recent date for sorting
3. **Mixed categories in thread**: Use category of most recent message
4. **Very long threads**: Include last 5 messages, note "N earlier messages"
5. **Missing thread headers**: Fall back to subject-line matching (strip Re:/Fwd:)
