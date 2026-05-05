# backend/agent.py
# Claude AI integration — uses prompt_builder for all calls

import re

import anthropic

from backend.config import get_settings
from backend.prompt_builder import build_messages, build_system_prompt

# In-memory conversation history (resets on server restart)
_history: list = []
_client = None


def _get_client() -> anthropic.Anthropic:
    """Lazy initialize Claude client — reads env vars at call time."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ── Ask Claude ─────────────────────────────────────────


def ask_agent(question: str, reset: bool = False) -> dict:
    """
    Send a question to Claude with full schema + rules context.

    Args:
        question: Natural language question from the user
        reset:    If True, clears conversation history first

    Returns:
        dict with answer, sql (if found), and updated history
    """
    global _history

    if reset:
        _history = []

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=build_system_prompt(),
            messages=build_messages(question, _history),
        )

        answer = response.content[0].text

        _history.append({"role": "user", "content": question})
        _history.append({"role": "assistant", "content": answer})

        sql = _extract_sql(answer)

        return {
            "success": True,
            "answer": answer,
            "sql": sql,
            "history": _history,
        }

    except Exception as e:
        print(f"Claude API error: {type(e).__name__}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ── SQL Extractor ──────────────────────────────────────


def _extract_sql(text: str) -> str | None:
    """
    Pull the SQL query out of Claude's response.
    Handles both markdown code blocks and plain SQL: prefix.
    """
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"SQL:\s*(SELECT.*?)(?:\n\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


# ── History Helpers ────────────────────────────────────


def reset_conversation() -> None:
    """Clear conversation history."""
    global _history
    _history = []


def get_history() -> list:
    """Return current conversation history."""
    return _history
