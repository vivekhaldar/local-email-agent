# Performance Enhancements Design: Caching & Parallelization

## Problem Statement

Current brief generation is slow due to:
1. **Redundant work**: Re-summarizing emails that were already processed in previous briefs
2. **Sequential processing**: Each Claude call waits for the previous one to complete

For a 4-day brief with 244 items, this means ~244 sequential API calls, each taking 2-5 seconds.

---

## Enhancement 1: Summary Caching

### Goal
Cache classification results so repeated brief generations skip already-processed emails.

### Cache Key Design

**Recommended: `message_num` for single emails, `thread_id` for threads**

| Key Type | Pros | Cons |
|----------|------|------|
| `message_num` | Stable integer, O(1) lookup | Breaks if database rebuilt |
| `uid` (Gmail ID) | Stable across resyncs | String comparison slower |
| Content hash | Survives any reorg | Must read all EMLs first |

**Decision**: Use `message_num` for singles, composite key for threads.

```python
def get_cache_key(item: dict) -> str:
    if item.get("is_thread"):
        # Thread: use sorted message_nums to handle order variations
        msg_nums = sorted(m["message_num"] for m in item["messages"])
        return f"thread:{'-'.join(map(str, msg_nums))}"
    else:
        return f"msg:{item['messages'][0]['message_num']}"
```

### Storage Design

**Recommended: Extend existing SQLite database**

```sql
-- Add to ~/MAIL/gmail/msg-db.sqlite
CREATE TABLE IF NOT EXISTS classification_cache (
    cache_key TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    action_items TEXT,
    cost_usd REAL DEFAULT 0.0,
    model_version TEXT,
    classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cache_date ON classification_cache(classified_at);
```

**Why SQLite over JSON file?**
- Already have `msg-db.sqlite` in the pipeline
- Transactional (no corruption on crash)
- Easy to query for analytics ("how much have I spent?")
- Scales to 100k+ entries without loading all into memory

### Cache Lookup Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    classify_with_claude.py                   │
├─────────────────────────────────────────────────────────────┤
│  for item in items:                                          │
│      cache_key = get_cache_key(item)                        │
│      cached = lookup_cache(cache_key)                       │
│                                                              │
│      if cached and not cache_expired(cached):               │
│          item["category"] = cached["category"]              │
│          item["summary"] = cached["summary"]                │
│          cache_hits += 1                                    │
│      else:                                                  │
│          result = call_claude(item)  ← Only if cache miss   │
│          save_to_cache(cache_key, result)                   │
│          cache_misses += 1                                  │
└─────────────────────────────────────────────────────────────┘
```

### Cache Invalidation Strategy

**Option A: Never expire (recommended for emails)**
- Emails don't change after receipt
- Summary of an email is deterministic
- Model version stored for future re-classification if needed

**Option B: TTL-based**
- Expire after 30 days
- Useful if prompts change frequently

**Option C: Model-version based**
- Invalidate when `model_version` differs from current
- Re-classify old entries with new model

**Decision**: Option A with Option C fallback. Store `model_version` but don't auto-expire. Add `--force-reclassify` flag for manual refresh.

### Expected Impact

| Scenario | Without Cache | With Cache |
|----------|---------------|------------|
| First run (244 items) | 244 Claude calls | 244 Claude calls |
| Second run (same 244) | 244 Claude calls | **0 Claude calls** |
| Daily brief (50 new) | 50 Claude calls | **50 Claude calls** |
| Weekly brief (overlap) | 350 Claude calls | **~50 Claude calls** |

---

## Enhancement 2: Parallel Classification

### Goal
Process multiple emails concurrently instead of sequentially.

### Current Sequential Flow

```python
for item in items:           # 244 iterations
    result = classify(item)  # 2-5 seconds each
    # Total: 244 × 3s = ~12 minutes
```

### Proposed Parallel Flow

```python
async def classify_batch(items, max_concurrent=10):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def classify_one(item):
        async with semaphore:  # Rate limiting
            return await classify_async(item)

    tasks = [classify_one(item) for item in items]
    results = await asyncio.gather(*tasks)
    # Total: 244 items / 10 concurrent × 3s = ~75 seconds
```

### Rate Limiting Strategy

**Semaphore-based throttling:**

| Concurrency | Time for 244 items | Risk |
|-------------|-------------------|------|
| 1 (current) | ~12 minutes | None |
| 5 | ~2.5 minutes | Low |
| 10 | ~75 seconds | Medium |
| 20 | ~40 seconds | High (rate limits) |

**Recommendation**: Start with `max_concurrent=5`, make configurable.

### Implementation Architecture

```python
# New in claude_client.py
async def query_claude_batch(
    prompts: list[tuple[str, dict]],  # (prompt, metadata) pairs
    max_concurrent: int = 5,
    progress_callback: Callable = None
) -> list[tuple[str, float, dict]]:
    """
    Process multiple prompts concurrently.

    Returns: list of (response_text, cost_usd, metadata)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    completed = 0

    async def process_one(prompt: str, metadata: dict):
        nonlocal completed
        async with semaphore:
            result = await query_claude(prompt)
            completed += 1
            if progress_callback:
                progress_callback(completed, len(prompts), metadata)
            return (*result, metadata)

    tasks = [process_one(p, m) for p, m in prompts]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Progress Reporting

With parallel execution, we need different progress reporting:

```
🏷️  Classifying 244 items (10 concurrent)...
   [50/244] 20% complete (5 cache hits)
   [100/244] 41% complete (12 cache hits)
   [150/244] 61% complete (18 cache hits)
   [200/244] 82% complete (25 cache hits)
   [244/244] 100% complete ✓

📊 Summary:
   Cache hits: 32 (13%)
   Claude calls: 212
   Total cost: $0.0234
   Time: 45 seconds
```

### Error Handling

```python
results = await asyncio.gather(*tasks, return_exceptions=True)

for item, result in zip(items, results):
    if isinstance(result, Exception):
        # Fallback for failed items
        item["category"] = "FYI"
        item["summary"] = f"{item['from_name']}: {item['subject']}"
        errors.append((item, result))
    else:
        item["category"] = result["category"]
        item["summary"] = result["summary"]
```

---

## Combined Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     classify_with_claude.py                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Load items from group_threads.py output                     │
│                                                                  │
│  2. Check cache for each item                                   │
│     ├── Cache HIT → Use cached result                           │
│     └── Cache MISS → Add to "needs_classification" list         │
│                                                                  │
│  3. Classify uncached items IN PARALLEL                         │
│     └── asyncio.gather() with Semaphore(5)                      │
│                                                                  │
│  4. Save new classifications to cache                           │
│                                                                  │
│  5. Merge cached + new results                                  │
│                                                                  │
│  6. Output classified items                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Changes Summary

| File | Changes |
|------|---------|
| `scripts/claude_client.py` | Add `query_claude_batch()` async function |
| `scripts/classify_with_claude.py` | Add cache layer + parallel processing |
| `scripts/cache_manager.py` | **New** - SQLite cache operations |
| `tests/test_cache_manager.py` | **New** - Cache tests |

---

## CLI Interface Changes

```bash
# Normal operation (uses cache, parallel)
./generate-brief-direct.sh --since 2d

# Force re-classify everything (ignore cache)
./generate-brief-direct.sh --since 2d --no-cache

# Control parallelism
./generate-brief-direct.sh --since 2d --concurrency 10

# Show cache stats
uv run scripts/cache_manager.py stats
# Output: 1,234 cached classifications, $0.45 total spend

# Clear cache
uv run scripts/cache_manager.py clear
```

---

## Implementation Phases

### Phase 1: Caching (Lower risk, immediate benefit)
1. Create `cache_manager.py` with SQLite operations
2. Add cache lookup/save to `classify_with_claude.py`
3. Test with repeated brief generation

### Phase 2: Parallelization (Higher impact, more complexity)
1. Add `query_claude_batch()` to `claude_client.py`
2. Refactor classification loop to use async batch
3. Add progress reporting
4. Test with various concurrency levels

---

## Implementation Notes (December 2025)

### Decisions Made

Based on review, the following decisions were made:

1. **Cache location**: Created new `~/MAIL/classification_cache.sqlite` (separate from GYB's `msg-db.sqlite` to avoid any interference with the sync tool)

2. **Concurrency default**: Started with 5 concurrent requests. Configurable via `--concurrency N` flag.

3. **Cache expiration**: Never expire. Emails don't change after receipt, so cached summaries remain valid indefinitely. The `--no-cache` flag allows manual re-classification when needed.

4. **Thread cache key**: Uses sorted message_nums (`thread:100-200-300`). When a new message arrives in a thread, the key changes, triggering a cache miss and re-classification with full context.

### Files Created/Modified

| File | Status | Description |
|------|--------|-------------|
| `scripts/cache_manager.py` | **New** | SQLite cache with `get_cache_key()`, `lookup_cache()`, `save_to_cache()`, `get_cache_stats()`, `clear_cache()` |
| `tests/test_cache_manager.py` | **New** | 16 tests covering all cache operations |
| `scripts/claude_client.py` | Modified | Added `query_claude_batch()` with semaphore-based rate limiting |
| `scripts/classify_with_claude.py` | Modified | Complete async refactor with 5-phase architecture |
| `generate-brief-direct.sh` | Modified | Added `--no-cache` and `--concurrency N` flags |

### Architecture Changes

The classification script now uses a 5-phase async architecture:

1. **Cache Check**: Loop through all items, separate into cache hits and misses
2. **Prompt Building**: Build prompts only for cache misses
3. **Parallel Execution**: Process with `asyncio.gather()` and `Semaphore(N)`
4. **Response Parsing**: Parse responses, save successful results to cache
5. **Result Merging**: Combine cached + new results, clean up output

### Error Handling

- Batch function returns `(response, cost, metadata, error)` tuples
- Errors don't abort the batch - partial success is possible
- Failed items fall back to template summaries
- All errors are logged to stderr

---

*Design created: December 2025*
*Implementation completed: December 2025*
