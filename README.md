# Local Email Agent

AI-powered tools for your local Gmail archive. Sync emails locally, generate smart briefs, and search with natural language.

## TL;DR

```bash
# Sync recent emails (last 3 days by default)
./sync-gmail.sh

# Generate a daily email brief (opens in browser)
./generate-brief.sh --since 1d

# Search emails with natural language
./email-search.sh "what did Sarah say about the budget?"
./email-search.sh "find invoices from AWS" --since=1y
```

## Features

### Email Briefs
Generate a beautifully formatted HTML summary of your inbox, organized by category with AI-generated summaries.

```bash
./generate-brief.sh --since 1d                    # Today's emails (default)
./generate-brief.sh --since 7d                    # Last week
./generate-brief.sh --since 2d --concurrency 10   # Faster with more parallelism
./generate-brief.sh --since 2d --no-cache         # Force re-classification
```

Features:
- Emails grouped into categories (Urgent, Needs Response, Financial, FYI, etc.)
- Thread grouping (conversations shown as single items)
- AI-generated one-line summaries
- Direct links to open each email in Gmail
- Collapsible sections for easy scanning
- **Caching**: Previously classified emails are cached, making subsequent runs instant
- **Parallel processing**: Multiple emails classified concurrently (default: 5)

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
│   ├── cache_manager.py         # Classification cache (SQLite)
│   ├── claude_client.py         # Claude Agent SDK client
│   ├── classify_with_claude.py  # AI classification (parallel + cached)
│   ├── email_search.py          # Search implementation
│   ├── fetch_emails.py          # Fetch emails from SQLite
│   ├── group_threads.py         # Group emails into threads
│   ├── parse_eml.py             # Parse EML files
│   └── render_brief.py          # Render HTML brief
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

- Python 3.12+ (via `uv`)
- Node.js 18+ (for Claude Agent SDK)
- [Claude CLI](https://github.com/anthropics/claude-code) or Claude Max subscription
- GYB installed at `~/bin/gyb/`
- Gmail API credentials in `pass` at `API_KEYS/gyb-gmail-client-secrets`

### Authentication

The Claude Agent SDK respects this authentication precedence:
1. `ANTHROPIC_API_KEY` environment variable (pay-as-you-go)
2. OAuth token (if approved by Anthropic)
3. Claude Max subscription (fallback if no API key is set)

For personal use with Claude Max, ensure `ANTHROPIC_API_KEY` is **not** set and the SDK will use your existing Claude Code login.

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

## Development

### Running Tests

The project uses pytest for unit testing:

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_parse_eml.py

# Run tests matching a pattern
uv run pytest -k "test_parse"
```

### Test Coverage

Generate a coverage report:

```bash
# Coverage with terminal output
uv run pytest --cov=scripts --cov-report=term-missing

# Coverage with HTML report
uv run pytest --cov=scripts --cov-report=html
# Then open htmlcov/index.html
```

Current coverage: ~34% (focused on pure functions and business logic).

### Project Structure for Tests

```
tests/
├── conftest.py              # Shared fixtures
├── test_cache_manager.py    # Cache operations
├── test_claude_client.py    # Claude SDK client
├── test_classify.py         # Classification logic
├── test_email_search.py     # Search functions
├── test_fetch_emails.py     # Duration parsing
├── test_group_threads.py    # Thread grouping
├── test_parse_eml.py        # Email parsing
└── test_render_brief.py     # Brief rendering
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

## Cache Management

Email classifications are cached in `~/MAIL/classification_cache.sqlite` to avoid redundant API calls. This makes subsequent brief generations much faster.

```bash
# View cache statistics
uv run scripts/cache_manager.py stats

# Clear the cache (force re-classification next time)
uv run scripts/cache_manager.py clear

# Generate brief without using cache
./generate-brief.sh --since 2d --no-cache
```

The cache key for threads includes all message IDs, so when a new message arrives in a thread, it will be re-classified with full context.

---

*Built with Claude Code*
