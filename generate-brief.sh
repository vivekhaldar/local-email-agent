#!/bin/bash
# ABOUTME: Generate an email brief using Claude in headless mode
# ABOUTME: Usage: ./generate-brief.sh [--since <duration>]

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
        -h|--help)
            echo "Usage: $0 [--since <duration>]"
            echo ""
            echo "Generate an email brief summarizing recent emails."
            echo ""
            echo "Options:"
            echo "  --since <duration>  How far back to look (default: 1d)"
            echo ""
            echo "Duration formats:"
            echo "  1h, 12h      - hours"
            echo "  1d, 2d, 7d   - days"
            echo "  1w, 2w       - weeks"
            echo "  1mo          - months"
            echo ""
            echo "Examples:"
            echo "  $0                  # Last 24 hours"
            echo "  $0 --since 2d       # Last 2 days"
            echo "  $0 --since 1w       # Last week"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Convert duration to human-readable for display
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
cd "$(dirname "$0")"

# Build the prompt with full instructions
PROMPT="Generate an email brief for the last $SINCE_TEXT.

Step 1: Run this to fetch recent emails:
uv run scripts/fetch_emails.py --since $SINCE --output /tmp/emails_raw.json

Step 2: Read /tmp/emails_raw.json and for each email, parse its content by running:
uv run scripts/parse_eml.py <filename>

Step 3: Classify each email into one of: URGENT, NEEDS_RESPONSE, FYI, NEWSLETTER, AUTOMATED
- URGENT: explicit urgency words, deadlines, time-sensitive
- NEEDS_RESPONSE: questions, requests waiting for reply
- FYI: informational, no action needed
- NEWSLETTER: has CATEGORY_PROMOTIONS label
- AUTOMATED: has CATEGORY_UPDATES label, notifications

For each email, provide a 1-2 sentence summary and any action items.

Step 4: Create /tmp/emails_classified.json with the classified emails in this format:
{\"emails\": [{\"message_num\": N, \"uid\": \"...\", \"gmail_link\": \"...\", \"from_name\": \"...\", \"subject\": \"...\", \"date\": \"...\", \"category\": \"...\", \"summary\": \"...\", \"action_items\": \"...\"}]}

Step 5: Render the HTML brief:
uv run scripts/render_brief.py --input /tmp/emails_classified.json --since \"$SINCE_TEXT\"

Step 6: Report the summary and the path to the generated brief."

# Use --allowedTools to pre-approve the tools we need
claude -p "$PROMPT" --allowedTools "Bash,Read,Write,Edit"
