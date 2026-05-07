"""In-process session memory with TTL-based expiry for multi-turn conversations."""

import time
from collections import defaultdict

from backend.logger import get_logger

logger = get_logger("sql-ai-agent.memory")

SESSION_TTL_SECONDS = 3600  # 1 hour


class SessionMemory:
    """In-memory store for per-session conversation histories.

    Tracks message turns keyed by session ID and automatically expires
    sessions idle for longer than SESSION_TTL_SECONDS.

    Attributes:
        _sessions: Maps session_id to a list of role/content turn dicts.
        _last_active: Maps session_id to the last-touched Unix timestamp.
    """

    def __init__(self):
        """Initialise empty session and last-active stores."""
        self._sessions: dict = defaultdict(list)
        self._last_active: dict = {}

    def get_history(self, session_id: str) -> list:
        """Return conversation history for a session, pruning expired sessions first.

        Args:
            session_id: Session identifier.

        Returns:
            List of {"role": ..., "content": ...} dicts, newest last.
        """
        self._cleanup_expired()
        return self._sessions[session_id]

    def add_turn(self, session_id: str, role: str, content: str):
        """Append a conversation turn and update the last-active timestamp.

        Args:
            session_id: Session to update.
            role: "user" or "assistant".
            content: Message text for this turn.
        """
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
        """Clear all history for a session without removing it from the store.

        Args:
            session_id: Session to reset.
        """
        self._sessions[session_id] = []
        self._last_active[session_id] = time.time()

    def _cleanup_expired(self):
        """Remove all sessions that have exceeded SESSION_TTL_SECONDS of inactivity."""
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
