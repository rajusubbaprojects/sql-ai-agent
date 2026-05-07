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
    global _client
    if _client is None:
        settings = get_settings()
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ── DB Router ──────────────────────────────────────────────────────────────────


def _route_database(user_question: str) -> str:
    """
    Ask Claude which database the question belongs to.
    Returns a database name from AVAILABLE_DATABASES.
    Falls back to airlines_db if unsure.
    """
    client = _get_client()
    db_list = ", ".join(AVAILABLE_DATABASES)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
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

    if chosen in AVAILABLE_DATABASES:
        logger.info(
            "db_router",
            extra={"event": "db_router", "question": user_question, "chosen_db": chosen},
        )
        return chosen

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
    if reset_history or reset:
        session_memory.reset(session_id)
    history = session_memory.get_history(session_id)

    try:
        client = _get_client()

        # Step 1 — route to the right database
        db_name = _route_database(user_question)

        # Step 2 — build system prompt with schema + rules for the routed DB
        from backend.schema_extractor import get_schema_for_claude

        schema = get_schema_for_claude(db_name)
        system_prompt = build_system_prompt(schema=schema, db_name=db_name)

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
    if sql and sql.strip().upper().startswith("SELECT"):
        return sql
    return f"SELECT 'Could not generate SQL for: {question[:50]}' AS message"


def _extract_sql(text: str) -> str | None:
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"SQL:\s*(SELECT.*?)(?:\n\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def reset_conversation(session_id: str = "default") -> dict:
    session_memory.reset(session_id)
    return {"success": True, "message": "Conversation reset"}


def get_history(session_id: str = "default") -> list:
    return session_memory.get_history(session_id)
