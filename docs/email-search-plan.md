# Natural Language Email Search - Design Plan

## Overview

**Goal**: Answer questions like:
- "What did Sarah say about the Q4 budget?"
- "Find the restaurant recommendation from John last year"
- "What's the status of my insurance claim?"
- "When did I last hear from my accountant?"

**Approach**: Hybrid search (fast keyword filtering → LLM for semantic understanding)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  email-search.py "what did Sarah say about the Q4 budget?"     │
│  email-search.py --from="accountant" --since=2w                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: QUERY PARSING (LLM)                                    │
│                                                                 │
│  Extract from natural language:                                 │
│  - People: "Sarah" → search From/To headers                     │
│  - Time hints: "last year", "in March" → date filter            │
│  - Topics: "Q4 budget" → keywords for body/subject search       │
│  - Intent: question vs. find-document vs. list-emails           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: FAST CANDIDATE SEARCH (No LLM)                         │
│                                                                 │
│  a) SQLite: Filter by date range, labels                        │
│  b) Grep EML files: keyword matches in subject/body             │
│  c) Sender matching: fuzzy match on From header                 │
│  → Return top 50-100 candidates                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: PARSE & RANK                                           │
│                                                                 │
│  - Parse each candidate EML                                     │
│  - Score by relevance (keyword density, recency, sender match)  │
│  → Return top 10-20 most relevant                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: ANSWER GENERATION (LLM)                                │
│                                                                 │
│  Send top results + original question to Claude:                │
│  "Based on these emails, answer: {question}"                    │
│                                                                 │
│  Output:                                                        │
│  - Direct answer to the question                                │
│  - Source emails with snippets + Gmail links                    │
│  - Related threads if applicable                                │
└─────────────────────────────────────────────────────────────────┘
```

## Usage Examples

```bash
# Natural language question
./email-search.py "what did Sarah say about the Q4 budget?"

# With explicit filters (human-readable durations)
./email-search.py "insurance claim status" --since=6mo

# Just list matching emails (no LLM answer)
./email-search.py "invoice from AWS" --list-only

# Search from specific sender
./email-search.py --from="john@example.com" "restaurant"

# Limit results
./email-search.py "project update" --limit=5
```

## Output Format

```
🔍 Searching for: "what did Sarah say about the Q4 budget?"

📊 Found 3 relevant emails

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 ANSWER:

Sarah mentioned that the Q4 budget was approved at $450K, but she
flagged concerns about the marketing allocation being too low. She
suggested reallocating $50K from the travel budget.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📧 SOURCES:

1. Sarah Chen <sarah@company.com>
   Re: Q4 Budget Final Review
   Dec 5, 2024 · "...approved the $450K budget but I'm worried about..."
   → https://mail.google.com/mail/u/0/#all/abc123

2. Sarah Chen <sarah@company.com>
   Budget Reallocation Proposal
   Dec 8, 2024 · "...suggest moving $50K from travel to marketing..."
   → https://mail.google.com/mail/u/0/#all/def456
```

## Key Functions

| Function | Purpose | LLM? |
|----------|---------|------|
| `parse_query(query: str)` | Extract people, dates, topics from natural language | Yes (Haiku) |
| `search_by_sender(name: str)` | Fuzzy match on From header | No |
| `search_by_keywords(keywords: list)` | Grep EML files for terms | No |
| `search_by_date(since, until)` | SQLite date range query | No |
| `rank_candidates(emails, query)` | Score by relevance | No |
| `generate_answer(emails, query)` | Synthesize answer from sources | Yes (Haiku) |

## Performance

- **2 LLM calls per search**: query parsing + answer generation
- **Candidate search**: Fast (grep + SQLite), limited to 100 candidates
- **Estimated total time**: <10 seconds for typical queries

## Files

| File | Purpose |
|------|---------|
| `scripts/email_search.py` | Main search script |
| `.claude/skills/email-search/SKILL.md` | Skill for auto-triggering |
