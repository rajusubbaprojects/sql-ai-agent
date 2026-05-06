import time
from collections import defaultdict

from backend.logger import get_logger

logger = get_logger("sql-ai-agent.memory")

SESSION_TTL_SECONDS = 3600  # 1 hour


class SessionMemory:
    def __init__(self):
        self._sessions: dict = defaultdict(list)
        self._last_active: dict = {}

    def get_history(self, session_id: str) -> list:
        self._cleanup_expired()
        return self._sessions[session_id]

    def add_turn(self, session_id: str, role: str, content: str):
        self._sessions[session_id].append({"role": role, "content": content})
        self._last_active[session_id] = time.time()
        logger.info(
            "session_updated",
            extra={
                "event": "session_updated",
                "session_id": session_id,
                "turns": len(self._sessions[session_id]),
            },
        )

    def reset(self, session_id: str):
        self._sessions[session_id] = []
        self._last_active[session_id] = time.time()

    def _cleanup_expired(self):
        now = time.time()
        expired = [
            sid for sid, last in self._last_active.items() if now - last > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]
            del self._last_active[sid]
            logger.info(
                "session_expired",
                extra={
                    "event": "session_expired",
                    "session_id": sid,
                },
            )


session_memory = SessionMemory()
