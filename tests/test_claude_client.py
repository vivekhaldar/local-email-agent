# ABOUTME: Tests for claude_client.py - shared Claude Agent SDK client
# ABOUTME: Tests parse_json_response() and error handling patterns

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from claude_client import parse_json_response, ClaudeQueryError


class TestParseJsonResponse:
    """Tests for parse_json_response() function."""

    def test_plain_json(self):
        """Plain JSON is parsed correctly."""
        response = '{"category": "URGENT", "summary": "Test"}'
        result = parse_json_response(response)
        assert result["category"] == "URGENT"
        assert result["summary"] == "Test"

    def test_json_with_markdown_code_block(self):
        """JSON wrapped in markdown code block is extracted."""
        response = """Here's the result:
```json
{"category": "FYI", "summary": "Information"}
```
Some trailing text."""
        result = parse_json_response(response)
        assert result["category"] == "FYI"
        assert result["summary"] == "Information"

    def test_json_with_plain_code_block(self):
        """JSON wrapped in plain code block is extracted."""
        response = """```
{"category": "CALENDAR", "summary": "Meeting invite"}
```"""
        result = parse_json_response(response)
        assert result["category"] == "CALENDAR"
        assert result["summary"] == "Meeting invite"

    def test_json_with_whitespace(self):
        """JSON with leading/trailing whitespace is parsed."""
        response = """
        {"category": "FINANCIAL", "summary": "Bank statement"}
        """
        result = parse_json_response(response)
        assert result["category"] == "FINANCIAL"

    def test_nested_json(self):
        """Nested JSON structures are parsed."""
        response = '{"category": "FYI", "data": {"nested": true}}'
        result = parse_json_response(response)
        assert result["data"]["nested"] is True

    def test_json_with_null(self):
        """JSON with null values is parsed."""
        response = '{"category": "FYI", "action_items": null}'
        result = parse_json_response(response)
        assert result["action_items"] is None

    def test_json_array(self):
        """JSON arrays are parsed."""
        response = '[1, 2, 3]'
        result = parse_json_response(response)
        assert result == [1, 2, 3]

    def test_invalid_json_raises(self):
        """Invalid JSON raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_json_response("not valid json")
        assert "Failed to parse JSON" in str(exc_info.value)

    def test_empty_string_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_json_response("")

    def test_only_code_block_markers_raises(self):
        """Only code block markers without content raises ValueError."""
        with pytest.raises(ValueError):
            parse_json_response("```\n```")

    def test_multiple_code_blocks_uses_first(self):
        """When multiple code blocks exist, uses the first json one."""
        response = """```json
{"first": true}
```

```json
{"second": true}
```"""
        result = parse_json_response(response)
        assert result["first"] is True

    def test_unicode_content(self):
        """JSON with unicode content is parsed."""
        response = '{"summary": "Meeting about café budget"}'
        result = parse_json_response(response)
        assert "café" in result["summary"]


class TestClaudeQueryError:
    """Tests for ClaudeQueryError exception."""

    def test_error_message(self):
        """Error message is preserved."""
        error = ClaudeQueryError("Connection failed")
        assert str(error) == "Connection failed"

    def test_error_is_exception(self):
        """ClaudeQueryError is an Exception subclass."""
        assert issubclass(ClaudeQueryError, Exception)

    def test_can_be_raised_and_caught(self):
        """ClaudeQueryError can be raised and caught."""
        with pytest.raises(ClaudeQueryError):
            raise ClaudeQueryError("Test error")
