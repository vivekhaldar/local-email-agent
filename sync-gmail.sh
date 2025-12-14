#!/bin/bash
# ABOUTME: Sync Gmail to local folder using GYB (Got Your Back)
# ABOUTME: Credentials are stored in pass for security

set -e

EMAIL="vh@vivekhaldar.com"
LOCAL_FOLDER="$HOME/MAIL/gmail"
GYB_DIR="$HOME/bin/gyb"
CLIENT_SECRETS="$GYB_DIR/client_secrets.json"

# Ensure client_secrets.json exists (regenerate from pass if missing)
if [[ ! -f "$CLIENT_SECRETS" ]]; then
    echo "Regenerating client_secrets.json from pass..."
    pass show API_KEYS/gyb-gmail-client-secrets > "$CLIENT_SECRETS"
fi

echo "Starting Gmail sync for $EMAIL..."
"$GYB_DIR/gyb" --email "$EMAIL" --action backup --local-folder "$LOCAL_FOLDER" --fast-incremental
echo "Sync complete."
