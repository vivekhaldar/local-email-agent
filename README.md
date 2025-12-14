# Gmail Local Backup

Local mirror of Gmail using [Got Your Back (GYB)](https://github.com/GAM-team/got-your-back).

## Overview

- **Email**: vh@vivekhaldar.com
- **Local storage**: `~/MAIL/gmail/`
- **Tool**: GYB (Gmail API-based backup)
- **Credentials**: Stored in `pass` at `API_KEYS/gyb-gmail-client-secrets`

## Directory Structure

```
~/MAIL/
├── README.md              # This file
├── sync-gmail.sh          # Sync script
└── gmail/
    ├── msg-db.sqlite      # SQLite database with message metadata
    └── YYYY/
        └── MM/
            └── DD/
                └── XXXXX.eml  # Individual email files
```

## Running a Sync

```bash
~/MAIL/sync-gmail.sh
```

The script:
1. Checks if `client_secrets.json` exists (regenerates from `pass` if missing)
2. Runs GYB backup, downloading only new messages since last sync

**Resumable**: If interrupted, just run again—GYB picks up where it left off.

## Checking Progress

While a sync is running, check how many messages have been backed up:

```bash
sqlite3 ~/MAIL/gmail/msg-db.sqlite "SELECT COUNT(*) FROM messages;"
```

## Setup Process (Reference)

This documents how the backup system was originally configured.

### 1. Google Cloud Project Setup

1. Created project "gmail-local-backup" in [Google Cloud Console](https://console.cloud.google.com)
2. Enabled the **Gmail API** (APIs & Services → Library → Gmail API)
3. Created OAuth credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Name: "GYB Backup"
4. Downloaded `client_secrets.json`

### 2. Google Workspace Configuration

Since `vh@vivekhaldar.com` is a Google Workspace account, the app needed to be allowed:

1. [Google Admin Console](https://admin.google.com) → Security → Access and data control → API controls
2. Manage Third-Party App Access → Add app → OAuth App Name Or Client ID
3. Entered Client ID: `45158837944-shlat8e0s5eo7bi651132sr2ougvk50b.apps.googleusercontent.com`
4. Set access to **Trusted**

### 3. GYB Installation

```bash
# Installed via official script (upgrade-only mode to skip interactive prompts)
bash <(curl -s -S -L https://git.io/gyb-install) -l
```

Installs to: `~/bin/gyb/`

### 4. Credential Storage

OAuth credentials stored securely in `pass`:

```bash
# Store credentials
cat ~/Downloads/client_secret_*.json | pass insert -m API_KEYS/gyb-gmail-client-secrets

# Extract to GYB directory
pass show API_KEYS/gyb-gmail-client-secrets > ~/bin/gyb/client_secrets.json
```

### 5. Initial Authorization

First run opens browser for Google OAuth consent. After approval, GYB caches access/refresh tokens locally.

## Querying the Backup

The SQLite database contains message metadata:

```bash
# Count all messages
sqlite3 ~/MAIL/gmail/msg-db.sqlite "SELECT COUNT(*) FROM messages;"

# View schema
sqlite3 ~/MAIL/gmail/msg-db.sqlite ".schema"

# Recent messages
sqlite3 ~/MAIL/gmail/msg-db.sqlite \
  "SELECT message_num, message_subject FROM messages ORDER BY message_date DESC LIMIT 10;"
```

## Reading Email Files

Individual emails are stored as `.eml` files (RFC 5322 format):

```bash
# Find an email file
find ~/MAIL/gmail -name "*.eml" | head -1

# Read with Python
python3 -c "
import email
from pathlib import Path
eml = next(Path('$HOME/MAIL/gmail').rglob('*.eml'))
msg = email.message_from_bytes(eml.read_bytes())
print(f'From: {msg[\"From\"]}')
print(f'Subject: {msg[\"Subject\"]}')
"
```

## Troubleshooting

### "Access blocked" error
If OAuth fails with "institution's admin needs to review", the app needs to be allowed in Google Workspace Admin Console (see Setup step 2).

### Token expired
GYB automatically refreshes tokens. If issues persist, delete cached tokens and re-authorize:
```bash
rm ~/bin/gyb/*.json  # Removes cached tokens (not client_secrets)
pass show API_KEYS/gyb-gmail-client-secrets > ~/bin/gyb/client_secrets.json
~/MAIL/sync-gmail.sh  # Re-triggers OAuth flow
```

### Upgrade GYB
```bash
bash <(curl -s -S -L https://git.io/gyb-install) -l
```

## Future: AI Agent Access

The backup format is designed for programmatic access:
- **SQLite database**: Query message metadata (dates, subjects, labels, message IDs)
- **EML files**: Parse full message content with Python's `email` module
- **Labels preserved**: Gmail labels are stored in the database

---

*Setup completed: December 13, 2025*
