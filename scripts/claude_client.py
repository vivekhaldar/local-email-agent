#!/usr/bin/env python3
# ABOUTME: Shared Claude Agent SDK client for email agent
# ABOUTME: Provides async query functions with cost tracking and error handling

import asyncio
from typing import Any

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

# Default model for classification (fast, cheap)
# Claude Haiku 4.5 - latest as of Oct 2025
DEFAULT_MODEL = "claude-haiku-4-5"


class ClaudeQueryError(Exception):
    """Error during Claude query."""

    pass


async def query_claude(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 90,
) -> tuple[str, float]:
    """
    Query Claude and return (response_text, cost_usd).

    Uses the Claude Agent SDK which respects authentication precedence:
    ANTHROPIC_API_KEY > OAuth token > Max subscription

    If no API key is set, falls back to your Claude Max subscription.

    Args:
        prompt: The prompt to send to Claude
        model: Model to use (default: claude-haiku-4-5)
        timeout_seconds: Timeout for the query

    Returns:
        Tuple of (response text, cost in USD)

    Raises:
        ClaudeQueryError: If the query fails
        TimeoutError: If the query times out
    """
    options = ClaudeAgentOptions(
        model=model,
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
    except Exception as e:
        raise ClaudeQueryError(f"Claude query failed: {e}") from e

    return response_text, cost


async def query_claude_batch(
    prompts: list[tuple[str, dict]],
    model: str = DEFAULT_MODEL,
    max_concurrent: int = 5,
    timeout_seconds: int = 90,
    progress_callback: callable = None,
) -> list[tuple[str, float, dict, Exception | None]]:
    """
    Process multiple prompts concurrently with rate limiting.

    Args:
        prompts: List of (prompt_text, metadata) tuples
        model: Model to use for all queries
        max_concurrent: Maximum concurrent requests (default: 5)
        timeout_seconds: Timeout per query
        progress_callback: Optional callback(completed, total, metadata) for progress

    Returns:
        List of (response_text, cost_usd, metadata, error) tuples.
        error is None on success, Exception on failure.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    completed = 0

    async def process_one(prompt: str, metadata: dict) -> tuple[str, float, dict, Exception | None]:
        nonlocal completed
        async with semaphore:
            try:
                response_text, cost = await query_claude(prompt, model, timeout_seconds)
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(prompts), metadata)
                return (response_text, cost, metadata, None)
            except Exception as e:
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(prompts), metadata)
                return ("", 0.0, metadata, e)

    tasks = [process_one(prompt, meta) for prompt, meta in prompts]
    return await asyncio.gather(*tasks)


def query_claude_sync(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 90,
) -> tuple[str, float]:
    """
    Synchronous wrapper for query_claude().

    Args:
        prompt: The prompt to send to Claude
        model: Model to use (default: claude-haiku-4-5)
        timeout_seconds: Timeout for the query

    Returns:
        Tuple of (response text, cost in USD)

    Raises:
        ClaudeQueryError: If the query fails
        TimeoutError: If the query times out
    """
    return asyncio.run(query_claude(prompt, model, timeout_seconds))


def parse_json_response(response_text: str) -> dict[str, Any]:
    """
    Parse JSON from Claude response, handling markdown code blocks.

    Args:
        response_text: Raw response text from Claude

    Returns:
        Parsed JSON as dictionary

    Raises:
        ValueError: If JSON parsing fails or response is empty
    """
    import json

    text = response_text.strip()

    # Handle empty responses
    if not text:
        raise ValueError("Empty response from Claude")

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    text = text.strip()

    # Check again after stripping code blocks
    if not text:
        raise ValueError("Empty JSON content in response")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}") from e
