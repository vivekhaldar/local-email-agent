#!/bin/bash
# ABOUTME: Print summary statistics from the GYB Gmail backup database
# ABOUTME: Shows message counts, date ranges, and label distribution

DB="$HOME/MAIL/gmail/msg-db.sqlite"

if [[ ! -f "$DB" ]]; then
    echo "Error: Database not found at $DB"
    exit 1
fi

echo "=== Gmail Backup Stats ==="
echo ""

# Total messages
total=$(sqlite3 "$DB" "SELECT COUNT(*) FROM messages;")
echo "Total messages: $total"
echo ""

# Date range
echo "Date range:"
sqlite3 "$DB" "SELECT
    '  Oldest: ' || MIN(message_internaldate),
    '  Newest: ' || MAX(message_internaldate)
FROM messages;" | tr '|' '\n'
echo ""

# Messages by year
echo "Messages by year:"
sqlite3 "$DB" "
SELECT '  ' || strftime('%Y', message_internaldate) AS year,
       COUNT(*) AS count
FROM messages
GROUP BY year
ORDER BY year DESC
LIMIT 10;"
echo ""

# Top labels
echo "Top 15 labels:"
sqlite3 "$DB" "
SELECT '  ' || label, COUNT(*) AS count
FROM labels
GROUP BY label
ORDER BY count DESC
LIMIT 15;"
echo ""

# Unread count
unread=$(sqlite3 "$DB" "SELECT COUNT(DISTINCT message_num) FROM labels WHERE label = 'UNREAD';")
echo "Unread messages: $unread"

# Storage stats
echo ""
echo "=== Storage ==="
db_size=$(du -h "$DB" | cut -f1)
echo "Database size: $db_size"

gmail_dir="$HOME/MAIL/gmail"
total_size=$(du -sh "$gmail_dir" 2>/dev/null | cut -f1)
echo "Total backup size: $total_size"

eml_count=$(find "$gmail_dir" -name "*.eml" 2>/dev/null | wc -l | tr -d ' ')
echo "EML files: $eml_count"

# Size in bytes for average calculation
total_bytes=$(du -s "$gmail_dir" 2>/dev/null | cut -f1)
if [[ $eml_count -gt 0 ]]; then
    avg_kb=$((total_bytes / eml_count))
    echo "Avg message size: ${avg_kb} KB"
fi
