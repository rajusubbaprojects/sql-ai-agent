import re
import time

import anthropic

from backend.config import get_settings
from backend.logger import get_logger, query_logger
from backend.prompt_builder import build_messages, build_system_prompt

logger = get_logger("sql-ai-agent.agent")

_history: list = []
_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def ask_agent(user_question: str, reset_history: bool = False, reset: bool = False) -> dict:
    global _history

    if reset_history or reset:
        _history = []

    try:
        client = _get_client()

        start = time.time()
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=build_system_prompt(),
            messages=build_messages(user_question, _history),
        )
        ai_latency_ms = (time.time() - start) * 1000

        answer = response.content[0].text
        sql = _extract_sql(answer)

        _history.append({"role": "user", "content": user_question})
        _history.append({"role": "assistant", "content": answer})

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
                "has_sql": sql is not None,
                "ai_latency_ms": round(ai_latency_ms, 2),
                "history_length": len(_history),
            },
        )

        return {
            "success": True,
            "answer": answer,
            "sql": sql,
            "history": _history,
            "history_length": len(_history),
        }

    except Exception as e:
        logger.error(
            "agent_error",
            extra={
                "event": "agent_error",
                "question": user_question,
                "error": str(e),
            },
        )
        return {
            "success": False,
            "error": str(e),
            "history_length": len(_history),
        }


def _extract_sql(text: str) -> str | None:
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"SQL:\s*(SELECT.*?)(?:\n\n|\Z)", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def reset_conversation() -> dict:
    global _history
    _history = []
    return {"success": True, "message": "Conversation reset"}


def get_history() -> list:
    return _history
