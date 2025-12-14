# Migration Plan: CLI Subprocess → Claude Agent SDK

This document outlines the plan to migrate our email agent from using `subprocess.run(["claude", ...])` to using the official Claude Agent SDK for Python.

## Executive Summary

| Aspect | Current (CLI) | Target (SDK) |
|--------|---------------|--------------|
| **Invocation** | `subprocess.run(["claude", "-p", ...])` | `async for msg in query(prompt, options)` |
| **Runtime** | Synchronous | Asynchronous (asyncio) |
| **Model Selection** | `--model haiku` flag | `ClaudeAgentOptions(env={"ANTHROPIC_MODEL": "..."})` |
| **Output** | Raw text, manual JSON parsing | Typed message objects (`AssistantMessage`, `TextBlock`) |
| **Error Handling** | Try/except subprocess errors | Async exception handling + typed errors |
| **Cost Tracking** | None | `ResultMessage.total_cost_usd` |

---

## 1. Current Implementation Analysis

### Files That Call Claude CLI

| File | Function | Purpose | Calls/Batch |
|------|----------|---------|-------------|
| `classify_with_claude.py` | `_call_claude()` | Classify & summarize emails | ~20-50 per brief |
| `email_search.py` | `call_claude()` | Parse query + generate answer | 2 per search |

### Current Pattern (Both Files)

```python
result = subprocess.run(
    ["claude", "-p", prompt, "--model", "haiku", "--output-format", "text"],
    capture_output=True,
    text=True,
    timeout=90
)
response_text = result.stdout.strip()
# Manual JSON parsing with markdown cleanup
parsed = json.loads(response_text)
```

### Issues with Current Approach

1. **Subprocess overhead**: Each call spawns a new process (~100-200ms overhead)
2. **No streaming**: Must wait for complete response
3. **No cost tracking**: Can't monitor spend
4. **Brittle parsing**: Manual markdown/JSON cleanup
5. **Limited error info**: Only return codes, no structured errors

---

## 2. Claude Agent SDK Overview

### Installation

```bash
pip install claude-agent-sdk
# or with uv:
uv add claude-agent-sdk
```

**Requirements**: Python 3.10+, Node.js 18+ (SDK bundles the Claude CLI internally)

### Core Concepts

1. **`query()` function**: Simple one-shot queries (our primary use case)
2. **`ClaudeSDKClient`**: Multi-turn conversations with session state
3. **`ClaudeAgentOptions`**: Configuration for model, tools, permissions
4. **Message Types**: `AssistantMessage`, `TextBlock`, `ToolUseBlock`, `ResultMessage`

### Basic Usage Pattern

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage

async def call_claude(prompt: str) -> tuple[str, float]:
    """Call Claude and return (response_text, cost_usd)."""
    options = ClaudeAgentOptions(
        env={"ANTHROPIC_MODEL": "claude-haiku-3"}
    )

    response_text = ""
    cost = 0.0

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response_text += block.text
        elif isinstance(message, ResultMessage):
            cost = message.total_cost_usd or 0.0

    return response_text, cost
```

---

## 3. Migration Strategy

### Phase 1: Add SDK Dependency & Async Infrastructure

**Goal**: Set up the SDK and create async wrapper functions

1. Add `claude-agent-sdk` to `pyproject.toml`
2. Create `scripts/claude_client.py` - shared async Claude client module
3. Add async helper utilities for running async code from sync contexts

**New File: `scripts/claude_client.py`**
```python
# ABOUTME: Shared Claude Agent SDK client for email agent
# ABOUTME: Provides async query functions with cost tracking and error handling

import asyncio
from typing import Any
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage
)

# Default model for classification (fast, cheap)
DEFAULT_MODEL = "claude-haiku-3"

async def query_claude(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 90
) -> tuple[str, float]:
    """
    Query Claude and return (response_text, cost_usd).

    Args:
        prompt: The prompt to send to Claude
        model: Model to use (default: claude-haiku-3)
        timeout_seconds: Timeout for the query

    Returns:
        Tuple of (response text, cost in USD)
    """
    options = ClaudeAgentOptions(
        env={"ANTHROPIC_MODEL": model}
    )

    response_text = ""
    cost = 0.0

    try:
        async with asyncio.timeout(timeout_seconds):
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text
                elif isinstance(message, ResultMessage):
                    cost = message.total_cost_usd or 0.0
    except asyncio.TimeoutError:
        raise TimeoutError(f"Claude query timed out after {timeout_seconds}s")

    return response_text, cost


def query_claude_sync(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 90
) -> tuple[str, float]:
    """Synchronous wrapper for query_claude()."""
    return asyncio.run(query_claude(prompt, model, timeout_seconds))
```

### Phase 2: Migrate `classify_with_claude.py`

**Goal**: Replace `_call_claude()` with SDK calls

**Changes**:
1. Import from `claude_client`
2. Replace `_call_claude()` with `query_claude_sync()`
3. Keep same JSON parsing logic (response format unchanged)
4. Add cost tracking and reporting

**Before**:
```python
def _call_claude(prompt: str, subject: str, fallback_name: str) -> dict:
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "haiku", "--output-format", "text"],
        capture_output=True, text=True, timeout=90
    )
    response_text = result.stdout.strip()
    # ... parse JSON ...
```

**After**:
```python
from claude_client import query_claude_sync

def _call_claude(prompt: str, subject: str, fallback_name: str) -> dict:
    try:
        response_text, cost = query_claude_sync(prompt, timeout_seconds=90)
        # ... parse JSON (same logic) ...
        result["cost_usd"] = cost
        return result
    except TimeoutError:
        # ... fallback handling ...
```

### Phase 3: Migrate `email_search.py`

**Goal**: Replace `call_claude()` with SDK calls

**Changes**:
1. Import from `claude_client`
2. Replace `call_claude()` with `query_claude_sync()`
3. Add cost tracking for searches

**Before**:
```python
def call_claude(prompt: str, timeout: int = 90) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "haiku", "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()
```

**After**:
```python
from claude_client import query_claude_sync

def call_claude(prompt: str, timeout: int = 90) -> str:
    try:
        response_text, _ = query_claude_sync(prompt, timeout_seconds=timeout)
        return response_text
    except TimeoutError:
        return ""
```

### Phase 4: Add Async Batch Processing (Optional Enhancement)

**Goal**: Process multiple emails concurrently for faster briefs

This is an optional optimization that could significantly speed up brief generation:

```python
import asyncio
from claude_client import query_claude

async def classify_batch(items: list[dict]) -> list[dict]:
    """Classify multiple emails concurrently."""
    tasks = [
        query_claude(build_prompt(item))
        for item in items
        if not classify_by_labels(item)  # Skip pre-classified
    ]

    # Run up to 5 concurrent requests
    semaphore = asyncio.Semaphore(5)

    async def bounded_query(prompt):
        async with semaphore:
            return await query_claude(prompt)

    results = await asyncio.gather(*[bounded_query(p) for p in tasks])
    return results
```

---

## 4. Testing Strategy

### Unit Tests

1. **Mock the SDK**: Create mock `query()` that returns expected message types
2. **Test JSON parsing**: Existing tests still valid
3. **Test timeout handling**: Verify fallback behavior
4. **Test cost accumulation**: Verify cost tracking works

### Integration Tests

1. **Live SDK test**: Simple prompt with real API
2. **Classification test**: Classify one email, verify JSON output
3. **Search test**: Run search query, verify answer generation

### Validation

Run existing tests to ensure no regressions:
```bash
uv run pytest
uv run pytest --cov=scripts
```

---

## 5. Rollout Plan

### Step 1: Feature Branch
```bash
git checkout -b feature/agent-sdk-migration
```

### Step 2: Add Dependency
```bash
uv add claude-agent-sdk
```

### Step 3: Create Shared Client
- Create `scripts/claude_client.py`
- Add unit tests in `tests/test_claude_client.py`

### Step 4: Migrate classify_with_claude.py
- Replace `_call_claude()` implementation
- Run tests, verify behavior unchanged
- Commit

### Step 5: Migrate email_search.py
- Replace `call_claude()` implementation
- Run tests, verify behavior unchanged
- Commit

### Step 6: Integration Testing
- Generate a brief with `./generate-brief.sh --since=1d`
- Run a search with `./email-search.sh "test query"`
- Verify HTML output looks correct

### Step 7: Merge
```bash
git checkout main
git merge feature/agent-sdk-migration
git push
```

---

## 6. Benefits After Migration

| Benefit | Impact |
|---------|--------|
| **Cost visibility** | Track spend per brief and per search |
| **Future extensibility** | Easy to add tools, multi-turn, streaming |
| **Concurrent processing** | Optional: 3-5x faster brief generation |
| **Better error handling** | Typed errors vs. return codes |
| **Reduced overhead** | No subprocess spawn per call |
| **Type safety** | TypedDict responses vs. raw text |

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **SDK requires Node.js** | Document in README; most dev machines have Node |
| **Async complexity** | Use sync wrapper for minimal code changes |
| **API changes** | Pin SDK version in pyproject.toml |
| **Different response format** | Careful testing; keep JSON parsing logic |

---

## 8. File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml` | Modify | Add `claude-agent-sdk` dependency |
| `scripts/claude_client.py` | **New** | Shared async Claude client |
| `scripts/classify_with_claude.py` | Modify | Use `claude_client` instead of subprocess |
| `scripts/email_search.py` | Modify | Use `claude_client` instead of subprocess |
| `tests/test_claude_client.py` | **New** | Unit tests for Claude client |
| `README.md` | Modify | Update requirements (Node.js) |
| `CLAUDE.md` | Modify | Document new architecture |

---

## 9. Success Criteria

- [ ] All existing tests pass
- [ ] Brief generation works identically
- [ ] Search works identically
- [ ] Cost is reported at end of brief generation
- [ ] No subprocess calls to `claude` CLI remain

---

*Plan created: December 2025*
