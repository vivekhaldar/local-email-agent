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
claude -p "/email-brief $SINCE"
