import logging
import sys

from pythonjsonlogger import jsonlogger


def get_logger(name: str) -> logging.Logger:
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
    def __init__(self):
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
