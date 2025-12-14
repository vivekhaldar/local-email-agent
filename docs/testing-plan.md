# Unit Testing Plan

## Overview

This document outlines the unit testing strategy for the Local Email Agent project.

## Current State

- **Test framework**: None (being added)
- **Test coverage**: 0%
- **Scripts to test**: 7 Python scripts in `scripts/`

## Testability Analysis

### Pure Functions (No External Dependencies)

These functions can be tested without any mocking:

| Script | Function | Purpose |
|--------|----------|---------|
| `fetch_emails.py` | `parse_duration()` | Parse "1d", "12h", "1w", "1mo" strings |
| `parse_eml.py` | `decode_mime_header()` | Decode MIME-encoded email headers |
| `parse_eml.py` | `extract_name_and_email()` | Parse From header into name/email |
| `parse_eml.py` | `strip_html()` | Convert HTML to plain text |
| `group_threads.py` | `normalize_subject()` | Remove Re:, Fwd: prefixes |
| `group_threads.py` | `parse_date()` | Parse email date strings to datetime |
| `group_threads.py` | `find_thread_root()` | Walk In-Reply-To chain |
| `classify_emails.py` | `classify_by_labels()` | Map Gmail labels to categories |
| `classify_emails.py` | `generate_template_summary()` | Generate summary from sender/subject |
| `classify_with_claude.py` | `classify_by_labels()` | Map labels to categories (for threads) |
| `email_search.py` | `parse_duration()` | Parse duration strings |
| `email_search.py` | `date_hint_to_range()` | Convert "last year" → date range |
| `email_search.py` | `format_date()` | Format dates for display |
| `email_search.py` | `strip_html_tags()` | Remove HTML tags from text |
| `email_search.py` | `format_answer_html()` | Convert markdown to HTML, linkify email refs |
| `render_brief.py` | `format_date_short()` | Format dates with multiple input formats |
| `render_brief.py` | `organize_by_category()` | Organize items into category sections |

### Algorithmic Functions (Testable with Mock Data)

These functions have complex logic but can be tested with constructed input:

| Script | Function | Purpose |
|--------|----------|---------|
| `group_threads.py` | `group_emails_by_thread()` | Thread reconstruction algorithm |
| `email_search.py` | `rank_and_parse_results()` | Search scoring and ranking |

### Functions with External Dependencies

These require mocking or integration test fixtures:

| Script | Function | Dependency |
|--------|----------|------------|
| `fetch_emails.py` | `fetch_emails()` | SQLite database |
| `parse_eml.py` | `parse_eml()` | File I/O |
| `classify_emails.py` | `summarize_with_llm()` | Anthropic API |
| `classify_with_claude.py` | `_call_claude()` | Claude CLI subprocess |
| `email_search.py` | `call_claude()` | Claude CLI subprocess |
| `email_search.py` | `search_candidates()` | SQLite database |
| `render_brief.py` | `render_brief()` | Jinja2 + File I/O |

## Implementation Phases

### Phase 1: Pure Function Tests

Focus on the ~17 pure functions listed above. These provide:
- High test coverage with minimal effort
- No mocking required
- Fast test execution
- Good regression protection

**Estimated: 100-150 test cases**

### Phase 2: Algorithmic Logic Tests

Test complex business logic with constructed mock data:
- Thread grouping algorithm
- Search ranking algorithm

**Estimated: 50 test cases**

### Phase 3: Integration Tests (Future)

- SQLite queries with test database
- EML file parsing with fixture files
- Subprocess mocking for Claude CLI
- Jinja2 template rendering

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_fetch_emails.py
├── test_parse_eml.py
├── test_group_threads.py
├── test_classify.py
├── test_email_search.py
├── test_render_brief.py
└── fixtures/
    └── sample.eml
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=scripts --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_parse_eml.py

# Run with verbose output
uv run pytest -v
```

## Coverage Goals

- **Phase 1+2 target**: 60-70% line coverage
- **Long-term target**: 80%+ coverage

## Dependencies

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
]
```
