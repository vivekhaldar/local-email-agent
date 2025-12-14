# Email Agent Capabilities - Brainstorm

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

1. **Time range**: Configurable via flag (e.g., `--since=24h`, `--since=monday`)
2. **Output**: Both terminal (summary) and markdown file (full report to `~/MAIL/briefs/`)
3. **LLM**: Claude API - quality over privacy concerns

---

## First Implementation: Daily Email Brief

### Usage
```bash
# Default: last 24 hours
~/MAIL/email-brief.py

# Custom time range
~/MAIL/email-brief.py --since=48h
~/MAIL/email-brief.py --since=monday
~/MAIL/email-brief.py --since="2024-12-10"
```

### Output Structure
```
~/MAIL/briefs/
└── 2024-12-13.md   # Full report with all summaries

Terminal output:
- Quick stats (X emails, Y urgent, Z need response)
- Top 5 urgent/important items
- Path to full report
```

### Database Schema (GYB)

```sql
-- messages: message_num, message_filename, message_internaldate
-- labels: message_num, label (e.g., "INBOX", "UNREAD", "CATEGORY_PROMOTIONS")
-- Note: Subject/From/Body are ONLY in EML files, not in SQLite
```

**Useful label pre-filters:**
- `CATEGORY_PROMOTIONS` → likely promotional
- `CATEGORY_UPDATES` → automated updates
- `UNREAD` → hasn't been seen yet
- Custom labels available too

### Implementation Steps

1. **Query recent emails from SQLite**
   ```sql
   SELECT m.message_num, m.message_filename, m.message_internaldate,
          GROUP_CONCAT(l.label) as labels
   FROM messages m
   LEFT JOIN labels l ON m.message_num = l.message_num
   WHERE m.message_internaldate >= ?
   GROUP BY m.message_num
   ORDER BY m.message_internaldate DESC
   ```

2. **Parse EML files for headers + body**
   - Use Python `email` module
   - Extract: From, Subject, Date, plain text body
   - Handle multipart (prefer text/plain, fallback to text/html→strip tags)
   - Truncate very long emails (e.g., >2000 chars)

3. **Pre-filter obvious categories**
   - Skip or downrank: `CATEGORY_PROMOTIONS`, known newsletter senders
   - Prioritize: `UNREAD`, emails from VIP senders

4. **Batch to Claude API**
   - Group emails (e.g., 10-20 per API call to stay under context limits)
   - Prompt: Classify + summarize + extract action items
   - Return structured JSON

5. **Generate report**
   - Group by category (Urgent, Needs Response, FYI, etc.)
   - Format as markdown with sections
   - Save to `~/MAIL/briefs/YYYY-MM-DD.md`
   - Print summary to terminal

### Classification Prompt (Draft)

```
For each email, provide:
1. Category: URGENT | NEEDS_RESPONSE | FYI | NEWSLETTER | PROMOTIONAL | AUTOMATED
2. Summary: 1-2 sentence summary
3. Action items: List any explicit requests or deadlines
4. Urgency reason: Why this is urgent (if applicable)

Signals for URGENT:
- Explicit urgency words (ASAP, urgent, deadline)
- Time-sensitive requests
- From known VIP senders
- Requires decision/approval
```

### Dependencies
- Python 3.x (via uv)
- anthropic SDK
- sqlite3 (stdlib)
- email (stdlib)

### Design Decision: Promotional Emails
- Include in a separate **"Newsletters & Promotions"** section at the end
- Don't send to LLM for classification (use Gmail labels)
- Just list sender + subject, no summarization

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
