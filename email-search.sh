#!/bin/bash
# ABOUTME: Natural language search over email archive
# ABOUTME: Usage: ./email-search.sh "find emails about X"

set -e

cd "$(dirname "$0")"

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 \"your search query\" [options]"
    echo ""
    echo "Options:"
    echo "  --since=DURATION   Only search emails from this duration ago (1d, 1w, 1mo, 1y)"
    echo "  --from=NAME        Filter by sender name or email"
    echo "  --list-only        Just list matching emails without LLM answer"
    echo "  --limit=N          Maximum number of results (default: 10)"
    echo "  --no-html          Skip HTML output generation"
    echo "  --no-open          Don't automatically open HTML in browser"
    echo ""
    echo "Examples:"
    echo "  $0 \"what did Sarah say about the budget?\""
    echo "  $0 \"find emails about google interview\""
    echo "  $0 \"tax documents\" --since=1y"
    echo "  $0 \"invoice from AWS\" --list-only"
    exit 1
fi

uv run scripts/email_search.py "$@"
