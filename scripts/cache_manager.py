#!/usr/bin/env python3
# ABOUTME: SQLite cache for email classification results
# ABOUTME: Avoids redundant Claude calls for previously processed emails

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

# Default cache location
CACHE_DB_PATH = Path.home() / "MAIL" / "classification_cache.sqlite"


def get_cache_key(item: dict) -> str:
    """Generate a cache key for an email item (single or thread).

    For threads: uses sorted message_nums so the key changes when new messages arrive.
    For singles: uses the single message's message_num.
    """
    messages = item.get("messages", [])
    if not messages:
        return ""

    if item.get("is_thread"):
        # Thread: sorted message_nums to detect when thread grows
        msg_nums = sorted(m.get("message_num", 0) for m in messages)
        return f"thread:{'-'.join(map(str, msg_nums))}"
    else:
        # Single email
        return f"msg:{messages[0].get('message_num', 0)}"


def init_cache_db(db_path: Path = CACHE_DB_PATH) -> None:
    """Initialize the cache database with required tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS classification_cache (
                cache_key TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                action_items TEXT,
                cost_usd REAL DEFAULT 0.0,
                model_version TEXT,
                classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_date
            ON classification_cache(classified_at)
        """)
        conn.commit()
    finally:
        conn.close()


def lookup_cache(
    cache_key: str,
    db_path: Path = CACHE_DB_PATH
) -> Optional[dict]:
    """Look up a cached classification result.

    Returns dict with category, summary, action_items, cost_usd if found, None otherwise.
    """
    if not cache_key or not db_path.exists():
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT category, summary, action_items, cost_usd FROM classification_cache WHERE cache_key = ?",
            (cache_key,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "category": row["category"],
                "summary": row["summary"],
                "action_items": row["action_items"],
                "cost_usd": row["cost_usd"],
                "from_cache": True
            }
        return None
    finally:
        conn.close()


def save_to_cache(
    cache_key: str,
    category: str,
    summary: str,
    action_items: Optional[str],
    cost_usd: float,
    model_version: str = "claude-haiku-4-5",
    db_path: Path = CACHE_DB_PATH
) -> None:
    """Save a classification result to the cache."""
    if not cache_key:
        return

    init_cache_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO classification_cache
            (cache_key, category, summary, action_items, cost_usd, model_version, classified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (cache_key, category, summary, action_items, cost_usd, model_version, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_cache_stats(db_path: Path = CACHE_DB_PATH) -> dict:
    """Get statistics about the cache."""
    if not db_path.exists():
        return {
            "total_entries": 0,
            "total_cost_usd": 0.0,
            "oldest_entry": None,
            "newest_entry": None
        }

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM classification_cache")
        total = cursor.fetchone()[0]

        cursor = conn.execute("SELECT SUM(cost_usd) FROM classification_cache")
        cost = cursor.fetchone()[0] or 0.0

        cursor = conn.execute("SELECT MIN(classified_at), MAX(classified_at) FROM classification_cache")
        dates = cursor.fetchone()

        return {
            "total_entries": total,
            "total_cost_usd": cost,
            "oldest_entry": dates[0],
            "newest_entry": dates[1]
        }
    finally:
        conn.close()


def clear_cache(db_path: Path = CACHE_DB_PATH) -> int:
    """Clear all entries from the cache. Returns number of entries deleted."""
    if not db_path.exists():
        return 0

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM classification_cache")
        count = cursor.fetchone()[0]
        conn.execute("DELETE FROM classification_cache")
        conn.commit()
        return count
    finally:
        conn.close()


def main():
    """CLI interface for cache management."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Manage classification cache")
    parser.add_argument("command", choices=["stats", "clear"], help="Command to run")
    args = parser.parse_args()

    if args.command == "stats":
        stats = get_cache_stats()
        print(f"Cache Statistics:")
        print(f"  Total entries: {stats['total_entries']:,}")
        print(f"  Total cost: ${stats['total_cost_usd']:.4f}")
        if stats['oldest_entry']:
            print(f"  Date range: {stats['oldest_entry']} to {stats['newest_entry']}")
        else:
            print(f"  Cache is empty")

    elif args.command == "clear":
        count = clear_cache()
        print(f"Cleared {count:,} entries from cache")


if __name__ == "__main__":
    main()
