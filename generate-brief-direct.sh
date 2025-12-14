#!/bin/bash
# ABOUTME: Generate email brief by directly running the Python pipeline
# ABOUTME: Faster than generate-brief.sh, shows all progress output

set -e

cd "$(dirname "$0")"

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
            echo "Generate an email brief by running the Python pipeline directly."
            echo "This is faster and shows more progress output than generate-brief.sh"
            echo ""
            echo "Options:"
            echo "  --since <duration>  How far back to look (default: 1d)"
            echo ""
            echo "Duration formats: 1h, 12h, 1d, 2d, 7d, 1w, 2w, 1mo"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create temp directory for intermediate files
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "📬 Generating email brief for last $SINCE..."
echo ""

# Step 1: Fetch emails from SQLite
echo "📥 Step 1/5: Fetching emails from database..."
uv run scripts/fetch_emails.py --since="$SINCE" --output="$TEMP_DIR/emails_raw.json"

# Check if we have emails
EMAIL_COUNT=$(python3 -c "import json; print(len(json.load(open('$TEMP_DIR/emails_raw.json'))['emails']))")
if [ "$EMAIL_COUNT" -eq 0 ]; then
    echo "❌ No emails found in the last $SINCE"
    exit 0
fi
echo "   Found $EMAIL_COUNT emails"
echo ""

# Step 2: Parse EML files
echo "📄 Step 2/5: Parsing email content..."
uv run scripts/parse_eml.py --batch="$TEMP_DIR/emails_raw.json" --output="$TEMP_DIR/emails_parsed.json"
echo ""

# Step 3: Group into threads
echo "🧵 Step 3/5: Grouping into threads..."
uv run scripts/group_threads.py --input="$TEMP_DIR/emails_parsed.json" --raw="$TEMP_DIR/emails_raw.json" --output="$TEMP_DIR/emails_grouped.json"
ITEM_COUNT=$(python3 -c "import json; print(len(json.load(open('$TEMP_DIR/emails_grouped.json'))['items']))")
echo "   Grouped into $ITEM_COUNT items (threads + singles)"
echo ""

# Step 4: Classify with Claude (this is the slow part - shows progress)
echo "🏷️  Step 4/5: Classifying with Claude..."
uv run scripts/classify_with_claude.py --grouped="$TEMP_DIR/emails_grouped.json" --output="$TEMP_DIR/emails_classified.json"
echo ""

# Step 5: Render HTML
echo "📝 Step 5/5: Rendering HTML brief..."
OUTPUT_FILE=$(uv run scripts/render_brief.py --input="$TEMP_DIR/emails_classified.json" --since="$SINCE" --duration="$SINCE")
echo ""

echo "✅ Brief generated!"
echo "📂 Opening: $OUTPUT_FILE"

# Open in browser
open "$OUTPUT_FILE"
