# Email Agent Capabilities - Brainstorm

## Implementation Progress

### 2025-12-13: Email Brief Implementation

**Completed:**
- [x] `scripts/fetch_emails.py` - Queries SQLite for recent emails, outputs JSON with Gmail links
- [x] `scripts/parse_eml.py` - Parses EML files, extracts headers and body text
- [x] `scripts/render_brief.py` - Renders classified emails to HTML using Jinja2 template
- [x] `templates/brief.html` - Responsive HTML template with category sections
- [x] `.claude/skills/email-brief/SKILL.md` - Project-local skill (auto-triggered)
- [x] `generate-brief.sh` - Entry point script with `--since` argument, streams progress
- [x] `pyproject.toml` - Python project with jinja2 dependency

**Usage:**
```bash
cd ~/MAIL
./generate-brief.sh                # Last 24 hours
./generate-brief.sh --since 2d     # Last 2 days
./generate-brief.sh --since 1w     # Last week
```

---

## What We Have to Work With

- **SQLite database**: Message metadata (dates, subjects, labels, message IDs)
- **EML files**: Full message content (headers, body, attachments)
- **~100k+ messages**: Rich historical data
- **Python `email` module**: Standard library for parsing EML
- **LLM access**: Claude API for summarization, classification, Q&A

---

## Agent Capability Ideas

### 1. Daily/Weekly Email Brief (User's primary interest)

**What it does:**
- Scan emails from last 24h (or since last brief)
- Summarize each email in 1-2 sentences
- Categorize: Urgent, Needs Response, FYI, Newsletter, Promotional
- Highlight action items and deadlines
- Output: Markdown report or terminal summary

**Technical approach:**
- Query SQLite for recent messages
- Parse EML files for body content
- Batch emails to LLM with classification prompt
- Extract: sender importance, urgency signals, action items

**Urgency signals to detect:**
- Keywords: "urgent", "ASAP", "deadline", "by EOD", "action required"
- Sender patterns: boss, key clients, family
- Reply-to threads you started
- Calendar invites / meeting requests

---

### 2. Smart Triage / Inbox Zero Assistant

**What it does:**
- Classify every email into buckets
- Suggest: Reply now, Reply later, Delegate, Archive, Unsubscribe
- Track emails awaiting your response vs. awaiting their response

**Categories:**
- 🔴 Urgent - needs response today
- 🟡 Important - needs response this week
- 🔵 FYI - read but no action needed
- ⚪ Noise - newsletters, promotions, automated

---

### 3. Thread Summarizer

**What it does:**
- Given a thread/conversation, summarize the entire exchange
- Extract: key decisions, action items, open questions
- "Catch me up on the Project X discussion"

**Use case:** You've been CC'd on a 47-message thread. Get the TL;DR.

---

### 4. Natural Language Search

**What it does:**
- "Find emails about the Q4 budget from Sarah"
- "What did my accountant say about estimated taxes?"
- "When did I last hear from John?"

**Technical approach:**
- Option A: LLM-powered SQL query generation
- Option B: Semantic search with embeddings (requires vector DB)
- Option C: Hybrid - keyword search + LLM ranking

---

### 5. Action Item Extractor

**What it does:**
- Parse emails for commitments, requests, deadlines
- Build a task list from your inbox
- Track: "I promised X" vs "They asked me for Y"

**Output:** Markdown checklist or integration with task manager

---

### 6. Sender Intelligence

**What it does:**
- Track communication patterns with key contacts
- "Show me my recent exchanges with [person]"
- VIP list: Always surface emails from these senders
- Response time analytics

---

### 7. Email Analytics Dashboard

**What it does:**
- Volume trends (emails per day/week/month)
- Top senders / most frequent correspondents
- Response time analysis
- Unanswered email tracking
- Label/category distribution

---

### 8. Historical Context Retrieval

**What it does:**
- "What was that restaurant recommendation from 2019?"
- "Find the receipt for my laptop purchase"
- "What was the decision on the office move?"

**Value:** Your email is a searchable life log.

---

### 9. Newsletter Digest

**What it does:**
- Identify newsletter/digest emails
- Consolidate into a single daily/weekly summary
- Filter signal from noise

---

## Technical Architecture Options

### Option A: On-Demand Agent
- User asks a question → Agent queries DB → Parses relevant EMLs → LLM processes → Returns answer
- Pros: No pre-processing, always fresh
- Cons: Slower for large queries, repeated LLM costs

### Option B: Batch Pre-Processing
- Scheduled job classifies/summarizes new emails
- Store classifications in SQLite (new columns or separate table)
- Briefs generated from pre-computed data
- Pros: Fast queries, consistent classification
- Cons: Upfront processing cost, storage for embeddings

### Option C: Hybrid
- Pre-compute: embeddings, basic classification, sender importance
- On-demand: LLM for summaries, complex questions
- Best of both worlds

---

## Cost & Performance Considerations

- **100k emails × LLM call = expensive** - need selective processing
- **Incremental processing** - only analyze new emails since last run
- **Caching** - store summaries/classifications to avoid reprocessing
- **Batching** - group multiple emails into single LLM call
- **Local models** - Ollama/llama.cpp for lower cost (but lower quality)

---

## Privacy Considerations

- All processing is local (email never leaves your machine)
- LLM API calls send email content to Anthropic/OpenAI - acceptable?
- Alternative: Local LLM (Ollama) for sensitive emails
- Hybrid: Local classification, cloud LLM only for summaries

---

## Design Decisions (Confirmed)

1. **Time range**: Configurable via argument (e.g., `24h`, `48h`, `monday`, `2024-12-10`)
2. **Output**: HTML file with elegant typography, consistent template day-to-day
3. **LLM**: Claude API via Claude Code skill
4. **Gmail links**: Every email summary links back to original in Gmail

---

## First Implementation: Daily Email Brief

### Architecture: Shell Script + Project-Local Skill + Python Helpers

```
┌─────────────────────────────────────────────────────────┐
│  generate-brief.sh                                      │
│  (Entry point - invokes Claude in headless mode)        │
│                                                         │
│  ./generate-brief.sh --since 1d                         │
│  ./generate-brief.sh --since 12h                        │
│  ./generate-brief.sh --since 1w                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  claude -p "generate email brief for last {since}"      │
│  (runs in ~/MAIL directory, picks up local skill)       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Project-Local Skill: .claude/skills/email-brief/       │
│  (scoped to ~/MAIL, auto-triggered by phrases like      │
│   "generate email brief", "summarize my emails")        │
│                                                         │
│  Orchestrates the brief generation:                     │
│  1. Calls Python scripts for data gathering             │
│  2. Analyzes and classifies emails                      │
│  3. Generates HTML output from template                 │
└─────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ fetch_emails.py │  │  parse_eml.py   │  │ render_brief.py │
│                 │  │                 │  │                 │
│ Query SQLite    │  │ Parse EML files │  │ Generate HTML   │
│ Get recent msgs │  │ Extract headers │  │ from template   │
│ Return JSON     │  │ Extract body    │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Why this architecture:**
- **Shell script entry point**: Easy to run, shows progress, takes `--since` argument
- **Claude headless mode**: `claude -p` runs the prompt non-interactively
- **Project-local skill**: Lives in `~/MAIL/.claude/commands/`, not global `~/.claude`
- **Python scripts**: Handle repeatable I/O (DB queries, file parsing, HTML generation)
- Template ensures consistent look across briefs

### Entry Point: `generate-brief.sh`

```bash
#!/bin/bash
# ABOUTME: Generate an email brief using Claude in headless mode
# ABOUTME: Usage: ./generate-brief.sh --since 1d

set -e

# Default: last 24 hours
SINCE="1d"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --since)
            SINCE="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--since <duration>]"
            echo "  duration: 1d, 12h, 1w, 1mo, 2d, etc."
            exit 1
            ;;
    esac
done

# Convert duration to human-readable for prompt
case $SINCE in
    *h) SINCE_TEXT="${SINCE%h} hours" ;;
    *d) SINCE_TEXT="${SINCE%d} days" ;;
    *w) SINCE_TEXT="${SINCE%w} weeks" ;;
    *mo) SINCE_TEXT="${SINCE%mo} months" ;;
    *) SINCE_TEXT="$SINCE" ;;
esac

echo "📬 Generating email brief for last $SINCE_TEXT..."
echo ""

# Run Claude in headless mode from ~/MAIL directory
cd ~/MAIL
claude -p "Generate an email brief for the last $SINCE_TEXT. Use the /email-brief command."
```

**Progress output**: Claude's headless mode streams output, so user sees progress as emails are processed.

### Gmail Message Links

Gmail URL format:
```
https://mail.google.com/mail/u/0/#all/{message_id}
```

The `message_id` is stored in the `uids` table and matches the EML filename:
```sql
SELECT u.uid FROM uids u WHERE u.message_num = ?
-- Returns: 19b18f6a1dda4196
-- Link: https://mail.google.com/mail/u/0/#all/19b18f6a1dda4196
```

### Output: HTML Brief

```
~/MAIL/briefs/
├── 2024-12-13.html      # Today's brief
├── 2024-12-12.html      # Yesterday's
└── template.html        # Shared template
```

**HTML Template Features:**
- Clean, readable typography (system fonts, good line height)
- Sections with visual hierarchy (Urgent → Needs Response → FYI → Newsletters)
- Each email summary is a card with:
  - Sender name + email
  - Subject (linked to Gmail)
  - Date/time
  - 1-2 sentence summary
  - Action items (if any)
  - Category badge
- Mobile-responsive
- Print-friendly

### Database Schema (GYB)

```sql
-- messages: message_num, message_filename, message_internaldate
-- labels: message_num, label (e.g., "INBOX", "UNREAD", "CATEGORY_PROMOTIONS")
-- uids: message_num, uid (Gmail message ID for URL links)
-- Note: Subject/From/Body are ONLY in EML files, not in SQLite
```

**Useful label pre-filters:**
- `CATEGORY_PROMOTIONS` → likely promotional
- `CATEGORY_UPDATES` → automated updates
- `UNREAD` → hasn't been seen yet
- Custom labels available too

### Python Helper Scripts

**1. `scripts/fetch_emails.py`**
```bash
# Fetch recent emails as JSON
uv run scripts/fetch_emails.py --since=24h
```
Output:
```json
[
  {
    "message_num": 1,
    "uid": "19b18f6a1dda4196",
    "gmail_link": "https://mail.google.com/mail/u/0/#all/19b18f6a1dda4196",
    "filename": "2025/12/13/19b18f6a1dda4196.eml",
    "date": "2025-12-13T10:26:14",
    "labels": ["INBOX", "UNREAD", "CATEGORY_UPDATES"]
  },
  ...
]
```

**2. `scripts/parse_eml.py`**
```bash
# Parse EML file, extract headers and body
uv run scripts/parse_eml.py ~/MAIL/gmail/2025/12/13/19b18f6a1dda4196.eml
```
Output:
```json
{
  "from": "notifications@github.com",
  "from_name": "GitHub",
  "to": "vh@vivekhaldar.com",
  "subject": "Re: [org/repo] Fix login bug (#123)",
  "date": "2025-12-13T10:26:14",
  "body_text": "...",
  "body_preview": "First 500 chars..."
}
```

**3. `scripts/render_brief.py`**
```bash
# Render classified emails to HTML
uv run scripts/render_brief.py --input=classified.json --output=~/MAIL/briefs/2024-12-13.html
```

### Project-Local Command: `/email-brief`

Location: `~/MAIL/.claude/commands/email-brief.md`

This is a **slash command** (not a skill), scoped to the ~/MAIL project directory.

**Invoked via:**
```bash
# From within ~/MAIL directory
claude -p "Generate email brief for last 2 days. Use /email-brief"

# Or interactively
claude> /email-brief 2d
```

**Command workflow:**
1. Parse time range from argument (e.g., "2d", "12h", "1w")
2. Run `fetch_emails.py --since={duration}` to get recent message metadata
3. For each batch of emails:
   - Run `parse_eml.py` to get content
   - Classify and summarize (Claude's job)
   - Print progress: "Processing batch 1/5... 20 emails classified"
4. Group by category
5. Run `render_brief.py` to generate HTML
6. Print summary stats + path to HTML file
7. Open HTML in browser (optional)

### Classification Categories

| Category | Badge Color | Criteria |
|----------|-------------|----------|
| 🔴 URGENT | Red | Explicit urgency, deadlines, VIP sender |
| 🟡 NEEDS_RESPONSE | Yellow | Question asked, request made, waiting on you |
| 🔵 FYI | Blue | Informational, no action needed |
| 📰 NEWSLETTER | Gray | `CATEGORY_PROMOTIONS` label or known sender |
| ⚙️ AUTOMATED | Gray | `CATEGORY_UPDATES`, notifications, receipts |

### File Structure (Updated)

```
~/MAIL/
├── generate-brief.sh        # Entry point: ./generate-brief.sh --since 1d
├── .claude/
│   └── commands/
│       └── email-brief.md   # Project-local slash command
├── scripts/
│   ├── fetch_emails.py      # Query SQLite, return JSON
│   ├── parse_eml.py         # Parse single EML, return JSON
│   └── render_brief.py      # Generate HTML from template
├── templates/
│   └── brief.html           # Jinja2 HTML template
├── briefs/                   # Generated HTML briefs (gitignored)
│   └── 2024-12-13.html
├── gmail/                    # Email archive (gitignored)
├── sync-gmail.sh
├── gmail-stats.sh
└── README.md
```

### HTML Template Design

```html
<!-- templates/brief.html (Jinja2) -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Email Brief - {{ date }}</title>
  <style>
    /* Clean typography */
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 2rem;
      color: #333;
    }
    /* Category sections */
    .section { margin-bottom: 2rem; }
    .section-header {
      font-size: 1.25rem;
      border-bottom: 2px solid #eee;
      padding-bottom: 0.5rem;
    }
    /* Email cards */
    .email-card {
      background: #fafafa;
      border-left: 4px solid #ccc;
      padding: 1rem;
      margin: 1rem 0;
    }
    .email-card.urgent { border-left-color: #e53e3e; }
    .email-card.needs-response { border-left-color: #ecc94b; }
    .email-card.fyi { border-left-color: #4299e1; }
    /* Links */
    a { color: #2b6cb0; }
    .gmail-link { font-size: 0.875rem; }
  </style>
</head>
<body>
  <h1>📬 Email Brief</h1>
  <p class="meta">{{ date }} · {{ total_count }} emails · {{ urgent_count }} urgent</p>

  {% for section in sections %}
  <div class="section">
    <h2 class="section-header">{{ section.icon }} {{ section.name }}</h2>
    {% for email in section.emails %}
    <div class="email-card {{ section.class }}">
      <div class="sender">{{ email.from_name }}</div>
      <div class="subject">
        <a href="{{ email.gmail_link }}">{{ email.subject }}</a>
      </div>
      <div class="summary">{{ email.summary }}</div>
      {% if email.action_items %}
      <div class="actions">Action: {{ email.action_items }}</div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</body>
</html>
```

### Dependencies
- Python 3.x (via uv)
- Jinja2 (HTML templating)
- sqlite3 (stdlib)
- email (stdlib)

### Design Decision: Promotional Emails
- Include in a separate **"Newsletters & Promotions"** section at the end
- Don't send to LLM for classification (use Gmail labels)
- Just list sender + subject with Gmail link, no summarization

---

## Second Implementation: Thread Summarizer

### Usage
```bash
# Summarize a thread by subject search
~/MAIL/email-thread.py "Project X kickoff"

# Summarize by sender
~/MAIL/email-thread.py --from="sarah@company.com"

# Summarize thread containing a specific message
~/MAIL/email-thread.py --message-id="abc123"
```

### What It Does
1. Find all emails matching the query (subject, sender, or message-id)
2. Reconstruct the thread (using In-Reply-To / References headers)
3. Order chronologically
4. Send entire thread to Claude for summarization
5. Output: TL;DR, key decisions, action items, open questions

### Implementation Steps

1. **Find seed messages**
   - Search EML files for subject match or sender match
   - Or look up specific message by ID

2. **Reconstruct thread**
   - Parse `In-Reply-To` and `References` headers
   - Build thread tree
   - Collect all related messages

3. **Prepare thread for LLM**
   - Order messages chronologically
   - Format: `From: X | Date: Y | Subject: Z\n\nBody...`
   - Truncate if thread is extremely long

4. **Send to Claude**
   - Prompt: Summarize this email thread, extract decisions and action items
   - Return structured summary

5. **Output**
   - Print to terminal
   - Optionally save to file

### Thread Summarizer Prompt (Draft)
```
Summarize this email thread:

1. TL;DR (2-3 sentences)
2. Key decisions made
3. Action items (who needs to do what)
4. Open questions or unresolved issues
5. Timeline of key events
```

---

## Third Implementation: Natural Language Search

### Usage
```bash
# Search by natural language
~/MAIL/email-search.py "what did Sarah say about the Q4 budget?"

# Search with date filter
~/MAIL/email-search.py "tax documents from my accountant" --since=2024-01-01

# Just find emails (no LLM summarization)
~/MAIL/email-search.py "invoice from AWS" --list-only
```

### What It Does
1. Parse natural language query → extract entities (people, topics, dates)
2. Search emails using extracted criteria
3. Rank results by relevance
4. Optionally summarize findings with LLM

### Implementation Approaches

**Option A: LLM-Powered SQL Generation**
- Send query to Claude → generate SQL/search criteria
- Pros: Flexible, handles complex queries
- Cons: Extra LLM call, potential SQL injection if not careful

**Option B: Keyword + Heuristic Search**
- Extract keywords from query
- Search subject/body with LIKE or regex
- Rank by keyword frequency
- Pros: Fast, no LLM needed for search
- Cons: Less flexible

**Option C: Hybrid (Recommended)**
- Use keyword search to find candidate emails
- Use LLM to rank/filter results and answer the question
- Best of both: fast initial search, smart final answer

### Implementation Steps (Hybrid Approach)

1. **Parse query for hints**
   - Detect names (proper nouns) → search From/To
   - Detect dates ("last month", "in January") → filter by date
   - Extract keywords → search subject/body

2. **Initial search**
   - Query SQLite for date-filtered messages
   - Grep EML files for keyword matches
   - Limit to top N candidates (e.g., 50)

3. **Parse candidate EMLs**
   - Extract headers + body for matches

4. **LLM ranking + answer**
   - Send candidates to Claude: "Which of these emails answers: {query}?"
   - Return: Direct answer + relevant email references

5. **Output**
   - Answer the question directly
   - List source emails with snippets

---

## File Structure (Updated)

```
~/MAIL/
├── email-brief.py      # Daily email brief
├── email-thread.py     # Thread summarizer
├── email-search.py     # Natural language search
├── lib/
│   ├── __init__.py
│   ├── db.py           # SQLite queries
│   ├── eml.py          # EML parsing utilities
│   └── llm.py          # Claude API wrapper
├── briefs/             # Generated brief reports
│   └── YYYY-MM-DD.md
├── gmail/              # Email archive (existing)
├── sync-gmail.sh       # Sync script (existing)
└── README.md           # Documentation (existing)
```

### Shared Library (`lib/`)

**db.py** - SQLite utilities
- `get_messages_since(date)` → list of (message_num, filename, date, labels)
- `get_message_by_id(message_num)` → single message
- `search_by_date_range(start, end)` → messages in range

**eml.py** - EML parsing
- `parse_eml(filepath)` → dict with from, to, subject, date, body, headers
- `get_thread_messages(message)` → list of related messages (via References)
- `extract_plain_text(message)` → body as plain text

**llm.py** - Claude API wrapper
- `classify_emails(emails)` → list of classifications
- `summarize_thread(messages)` → thread summary
- `answer_question(query, candidate_emails)` → answer + sources
