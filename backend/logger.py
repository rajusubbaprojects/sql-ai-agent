"""Structured JSON logging helpers for the SQL AI Agent service."""

import logging
import sys

from pythonjsonlogger import jsonlogger


def get_logger(name: str) -> logging.Logger:
    """Create or retrieve a JSON-formatted logger.

    Configures a StreamHandler to stdout on first call; subsequent calls
    for the same name return the cached logger without adding duplicate
    handlers.

    Args:
        name: Logger name (used as the "name" field in log output).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


class QueryLogger:
    """Structured logger for SQL query and HTTP request events.

    Wraps get_logger to emit JSON log lines with consistent field names
    for downstream log aggregators.
    """

    def __init__(self):
        """Initialise the query logger using the shared JSON logger."""
        self.logger = get_logger("sql-ai-agent.query")

    def log_query(
        self,
        query: str,
        sql: str,
        success: bool,
        latency_ms: float,
        error: str = None,
        row_count: int = None,
    ):
        """Log a completed SQL query execution.

        Args:
            query: The original natural-language question.
            sql: The generated SQL statement.
            success: Whether the query executed without error.
            latency_ms: End-to-end Claude API latency in milliseconds.
            error: Error message if success is False, otherwise None.
            row_count: Number of rows returned, or None for write operations.
        """
        self.logger.info(
            "query_executed",
            extra={
                "event": "query_executed",
                "query": query,
                "sql": sql,
                "success": success,
                "latency_ms": round(latency_ms, 2),
                "row_count": row_count,
                "error": error,
            },
        )

    def log_request(self, path: str, method: str, status_code: int, latency_ms: float):
        """Log a completed HTTP request.

        Args:
            path: URL path of the request.
            method: HTTP method (GET, POST, etc.).
            status_code: HTTP response status code.
            latency_ms: Total request handling time in milliseconds.
        """
        self.logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "path": path,
                "method": method,
                "status_code": status_code,
                "latency_ms": round(latency_ms, 2),
            },
        )


query_logger = QueryLogger()
