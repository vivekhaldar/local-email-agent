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
        ValueError: If JSON parsing fails
    """
    import json

    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}") from e
