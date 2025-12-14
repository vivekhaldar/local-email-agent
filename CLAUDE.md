# Claude Instructions for Local Email Agent

This is a local email agent that syncs Gmail locally and provides AI-powered tools for briefs and search.

## Project Overview

- **Purpose**: AI-powered tools for a local Gmail archive
- **Email storage**: `~/MAIL/gmail/` with SQLite database and EML files
- **Python**: Uses `uv` for all Python operations (no direct python3)
- **LLM**: Uses Claude Agent SDK with Haiku model for classification
- **Authentication**: Falls back to Claude Max subscription if no `ANTHROPIC_API_KEY` is set

## Key Commands

```bash
# Sync emails
./sync-gmail.sh

# Generate email brief
./generate-brief.sh --since=1d

# Search emails
./email-search.sh "your query"

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=scripts --cov-report=term-missing
```

## Architecture

### Data Flow for Briefs
```
fetch_emails.py → parse_eml.py → group_threads.py → classify_with_claude.py → render_brief.py
```

### Data Flow for Search
```
email_search.py (query parsing → candidate search → ranking → answer generation)
```

## Important Files

| File | Purpose |
|------|---------|
| `scripts/claude_client.py` | Shared Claude Agent SDK client with sync/async wrappers |
| `scripts/classify_with_claude.py` | Classify and summarize using Claude |
| `scripts/email_search.py` | Natural language search implementation |
| `scripts/fetch_emails.py` | Query SQLite for recent emails |
| `scripts/group_threads.py` | Group emails into conversation threads |
| `scripts/parse_eml.py` | Parse EML files, extract headers/body |
| `scripts/render_brief.py` | Render HTML briefs with Jinja2 |
| `templates/brief.html` | Jinja2 template for briefs |
| `templates/search-results.html` | Jinja2 template for search results |

## Database Schema (GYB)

The SQLite database (`gmail/msg-db.sqlite`) contains:
- `messages`: message_num, message_filename, message_internaldate
- `labels`: message_num, label
- `uids`: message_num, uid (Gmail message ID for URLs)

Note: Subject, From, and Body are only in EML files, not in SQLite.

## Gmail Links

Format: `https://mail.google.com/mail/u/0/#all/{uid}`

The `uid` comes from the `uids` table and matches EML filenames.

## Classification Categories

| Category | Description |
|----------|-------------|
| URGENT | Time-sensitive, deadlines, "ASAP" |
| NEEDS_RESPONSE | Questions, requests for reply |
| CALENDAR | Meeting invites, events |
| FINANCIAL | Bank statements, bills |
| FYI | Informational, no action needed |
| NEWSLETTER | Marketing, promotions |
| AUTOMATED | Notifications, automated updates |

## Testing

- Tests are in `tests/` directory
- Focus on pure functions (no external dependencies)
- Run with `uv run pytest`
- Coverage report: `uv run pytest --cov=scripts`

## Code Style

- All Python files start with two ABOUTME comment lines
- Use type hints
- Scripts are standalone CLI tools with argparse
- HTML templates use Jinja2 with consistent styling (Fraunces + DM Sans fonts)

## Common Tasks

### Adding a new email category
1. Add to `organize_by_category()` in `render_brief.py`
2. Update classification prompt in `classify_with_claude.py`
3. Add CSS class in `templates/brief.html`

### Modifying HTML output
- Brief template: `templates/brief.html`
- Search template: `templates/search-results.html`
- Both use CSS variables for consistent theming

### Adding new search features
- Query parsing: `parse_query()` in `email_search.py`
- Date handling: `date_hint_to_range()` in `email_search.py`
- Answer formatting: `format_answer_html()` in `email_search.py`
