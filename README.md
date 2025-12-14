# Local Email Agent

AI-powered tools for your local Gmail archive. Sync emails locally, generate smart briefs, and search with natural language.

## TL;DR

```bash
# Sync recent emails (last 3 days by default)
./sync-gmail.sh

# Generate a daily email brief (opens in browser)
./generate-brief.sh

# Search emails with natural language
./email-search.sh "what did Sarah say about the budget?"
./email-search.sh "find invoices from AWS" --since=1y
```

## Features

### Email Briefs
Generate a beautifully formatted HTML summary of your inbox, organized by category with AI-generated summaries.

```bash
./generate-brief.sh              # Today's emails
./generate-brief.sh --since=7d   # Last week
./generate-brief.sh --since=1mo  # Last month
```

Features:
- Emails grouped into categories (Work, Finance, Travel, etc.)
- Thread grouping (conversations shown as single items)
- AI-generated one-line summaries
- Direct links to open each email in Gmail
- Collapsible sections for easy scanning

### Natural Language Search
Ask questions about your email archive and get synthesized answers with source citations.

```bash
./email-search.sh "what's the status of my insurance claim?"
./email-search.sh "find emails about google interview"
./email-search.sh "tax documents from last year" --since=1y
./email-search.sh "invoices" --list-only  # Skip AI answer, just list matches
```

Features:
- Hybrid search: fast keyword filtering + LLM semantic understanding
- Synthesized answers citing specific emails
- Clickable source links to Gmail
- HTML output with anchor links to sources
- Time filtering with human-readable durations (1d, 2w, 1mo, 1y)

### Gmail Sync
Keep a local mirror of your Gmail using [Got Your Back (GYB)](https://github.com/GAM-team/got-your-back).

```bash
./sync-gmail.sh           # Last 3 days (default)
./sync-gmail.sh 7d        # Last week
./sync-gmail.sh full      # Full sync of all messages
```

## Directory Structure

```
~/MAIL/
├── README.md                    # This file
├── sync-gmail.sh                # Gmail sync script
├── generate-brief.sh            # Email brief generator
├── email-search.sh              # Natural language search
├── scripts/
│   ├── fetch_emails.py          # Fetch emails from SQLite
│   ├── parse_eml.py             # Parse EML files
│   ├── group_threads.py         # Group emails into threads
│   ├── classify_with_claude.py  # AI classification
│   ├── render_brief.py          # Render HTML brief
│   └── email_search.py          # Search implementation
├── templates/
│   ├── brief.html               # Brief HTML template
│   └── search-results.html      # Search results template
├── briefs/                      # Generated briefs (gitignored)
├── searches/                    # Generated search results (gitignored)
└── gmail/
    ├── msg-db.sqlite            # SQLite database with metadata
    └── YYYY/MM/DD/*.eml         # Email files
```

## Requirements

- Python 3.11+ (via `uv`)
- [Claude CLI](https://github.com/anthropics/claude-code) with API access
- GYB installed at `~/bin/gyb/`
- Gmail API credentials in `pass` at `API_KEYS/gyb-gmail-client-secrets`

## Setup

### 1. Google Cloud Project

1. Create project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **Gmail API**
3. Create OAuth credentials (Desktop app)
4. Download `client_secrets.json`

### 2. Google Workspace (if applicable)

For Workspace accounts, allow the app:

1. [Google Admin Console](https://admin.google.com) → Security → API controls
2. Manage Third-Party App Access → Add app → OAuth App Name Or Client ID
3. Set access to **Trusted**

### 3. GYB Installation

```bash
bash <(curl -s -S -L https://git.io/gyb-install) -l
```

### 4. Credential Storage

```bash
cat ~/Downloads/client_secret_*.json | pass insert -m API_KEYS/gyb-gmail-client-secrets
```

### 5. Initial Sync

```bash
./sync-gmail.sh full  # First-time full sync (may take hours for large mailboxes)
```

## Querying the Database

```bash
# Count all messages
sqlite3 ~/MAIL/gmail/msg-db.sqlite "SELECT COUNT(*) FROM messages;"

# Recent messages
sqlite3 ~/MAIL/gmail/msg-db.sqlite \
  "SELECT message_num, message_subject FROM messages ORDER BY message_date DESC LIMIT 10;"

# View schema
sqlite3 ~/MAIL/gmail/msg-db.sqlite ".schema"
```

## Troubleshooting

### "Access blocked" error
The app needs to be allowed in Google Workspace Admin Console (see Setup step 2).

### Token expired
GYB automatically refreshes tokens. If issues persist:
```bash
rm ~/bin/gyb/*.json  # Remove cached tokens
pass show API_KEYS/gyb-gmail-client-secrets > ~/bin/gyb/client_secrets.json
./sync-gmail.sh      # Re-triggers OAuth flow
```

### Upgrade GYB
```bash
bash <(curl -s -S -L https://git.io/gyb-install) -l
```

---

*Built with Claude Code*
