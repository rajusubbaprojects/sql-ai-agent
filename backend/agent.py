"""SQL AI Agent core — routes questions to the right database and calls Claude."""

import re
import time

import anthropic

from backend.config import get_settings
from backend.db import AVAILABLE_DATABASES
from backend.logger import get_logger, query_logger
from backend.memory import session_memory
from backend.prompt_builder import build_messages, build_system_prompt

try:
    from aws_xray_sdk.core import patch_all, xray_recorder

    xray_recorder.configure(
        service="sql-ai-agent", daemon_address="127.0.0.1:2000", context_missing="LOG_ERROR"
    )
    patch_all()
    XRAY_ENABLED = True
except ImportError:
    XRAY_ENABLED = False

logger = get_logger("sql-ai-agent.agent")
_client = None


def _get_client() -> anthropic.Anthropic:
    """Return the singleton Anthropic client, creating it on first call.

    Returns:
        Cached Anthropic client instance.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ── DB Router ──────────────────────────────────────────────────────────────────


def _route_database(user_question: str) -> str:
    """Route a user question to the appropriate database using Claude Haiku.

    Makes a fast, cheap single-message call to classify which database best
    matches the question. Falls back to airlines_db if the response is
    unrecognised.

    Args:
        user_question: The raw natural-language question from the user.

    Returns:
        A database name from AVAILABLE_DATABASES (e.g. "airlines_db").
    """
    client = _get_client()
    db_list = ", ".join(AVAILABLE_DATABASES)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # fast + cheap for routing
        max_tokens=20,
        system=(
            f"You are a database router. Available databases: {db_list}.\n"
            "Reply with ONLY the database name that best matches the user's question. "
            "No explanation, no punctuation — just the database name.\n"
            "Database descriptions:\n"
            "- airlines_db: flights, airlines, airports, routes, fares, delays\n"
            "- sakila: movies, films, actors, rentals, customers, inventory, stores"
        ),
        messages=[{"role": "user", "content": user_question}],
    )

    chosen = response.content[0].text.strip().lower()

    # Validate — must be one of the known databases
    if chosen in AVAILABLE_DATABASES:
        logger.info(
            "db_router",
            extra={"event": "db_router", "question": user_question, "chosen_db": chosen},
        )
        return chosen

    # Fallback
    logger.info(
        "db_router_fallback",
        extra={"event": "db_router_fallback", "question": user_question, "raw": chosen},
    )
    return "airlines_db"


# ── Main Agent ─────────────────────────────────────────────────────────────────


def ask_agent(
    user_question: str,
    reset_history: bool = False,
    reset: bool = False,
    session_id: str = "default",
) -> dict:
    """Translate a natural-language question into SQL and return the result.

    Orchestrates DB routing, schema retrieval, prompt construction, and the
    Claude API call. Persists the conversation turn in session memory.

    Args:
        user_question: Natural-language question to answer.
        reset_history: If True, clear session history before this turn.
        reset: Alias for reset_history (kept for backwards compatibility).
        session_id: Identifies the conversation session.

    Returns:
        On success, a dict with keys: success (bool), answer (str),
        sql (str | None), db_name (str), history (list),
        history_length (int), and session_id (str).
        On failure, returns success=False with an "error" key instead.
    """
    if reset_history or reset:
        session_memory.reset(session_id)
    history = session_memory.get_history(session_id)

    try:
        client = _get_client()

        # Step 1 — route to the right database
        db_name = _route_database(user_question)

        # Step 2 — build system prompt with schema from the routed DB
        from backend.schema_extractor import get_schema_for_claude

        schema = get_schema_for_claude(db_name)
        system_prompt = build_system_prompt(schema=schema)

        # Step 3 — ask Claude to generate SQL
        start = time.time()
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=system_prompt,
            messages=build_messages(user_question, history),
        )
        ai_latency_ms = (time.time() - start) * 1000

        answer = response.content[0].text
        sql = _validate_sql(_extract_sql(answer), user_question)

        session_memory.add_turn(session_id, "user", user_question)
        session_memory.add_turn(session_id, "assistant", answer)
        updated_history = session_memory.get_history(session_id)

        query_logger.log_query(
            query=user_question,
            sql=sql or "",
            success=True,
            latency_ms=ai_latency_ms,
        )
        logger.info(
            "agent_response",
            extra={
                "event": "agent_response",
                "question": user_question,
                "session_id": session_id,
                "db_name": db_name,
                "has_sql": sql is not None,
                "ai_latency_ms": round(ai_latency_ms, 2),
                "history_length": len(updated_history),
            },
        )

        return {
            "success": True,
            "answer": answer,
            "explanation": _extract_explanation(answer),
            "sql": sql,
            "db_name": db_name,
            "history": updated_history,
            "history_length": len(updated_history),
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(
            "agent_error",
            extra={
                "event": "agent_error",
                "question": user_question,
                "session_id": session_id,
                "error": str(e),
            },
        )
        return {
            "success": False,
            "error": str(e),
            "history_length": 0,
            "session_id": session_id,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────


def _validate_sql(sql: str | None, question: str) -> str:
    """Ensure the extracted SQL is a SELECT statement.

    Args:
        sql: Candidate SQL string, or None if extraction failed.
        question: The original user question (used in the fallback message).

    Returns:
        The original sql if it starts with SELECT, otherwise a safe fallback
        SELECT that echoes the question back as a message column.
    """
    if sql and sql.strip().upper().startswith("SELECT"):
        return sql
    return f"SELECT 'Could not generate SQL for: {question[:50]}' AS message"


def _extract_sql(text: str) -> str | None:
    """Extract a SQL query from Claude's markdown response.

    Tries two patterns in order:
      1. A fenced ``sql ... `` code block.
      2. A bare ``SQL: SELECT ...`` line.

    Args:
        text: Raw text from Claude's response.

    Returns:
        The extracted SQL string, or None if no pattern matched.
    """
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"SQL:\s*(SELECT.*?)(?:\n\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_explanation(text: str) -> str:
    """Extract the plain-English explanation from Claude's response.

    Strips the SQL code block so the UI can display only the narrative text.
    Looks for an explicit EXPLANATION: label first; falls back to removing
    the fenced SQL block and returning whatever prose remains.

    Args:
        text: Full raw text from Claude's response.

    Returns:
        Explanation string, or the original text if no SQL block was found.
    """
    # Try the labelled EXPLANATION: section first
    match = re.search(
        r"EXPLANATION:\s*(.+?)(?:\n\s*ASSUMPTIONS:|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    # Fall back: strip the fenced SQL block and return the prose
    cleaned = re.sub(r"```sql.*?```", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    return cleaned if cleaned else text.strip()


def reset_conversation(session_id: str = "default") -> dict:
    """Clear all conversation history for a session.

    Args:
        session_id: Session to reset.

    Returns:
        A dict with success=True and a confirmation message.
    """
    session_memory.reset(session_id)
    return {"success": True, "message": "Conversation reset"}


def get_history(session_id: str = "default") -> list:
    """Return the current conversation history for a session.

    Args:
        session_id: Session to retrieve.

    Returns:
        List of {"role": ..., "content": ...} turn dicts.
    """
    return session_memory.get_history(session_id)
