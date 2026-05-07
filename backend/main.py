"""FastAPI application entrypoint — defines all HTTP routes and middleware."""

import os
import time
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agent import ask_agent, reset_conversation
from backend.config import get_settings
from backend.db import execute_query, test_connection
from backend.logger import get_logger, query_logger
from backend.rules import add_custom_rule, get_rules_for_claude
from backend.schema_extractor import get_schema_for_claude

try:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.ext.fastapi.middleware import XRayMiddleware

    XRAY_ENABLED = True
except ImportError:
    XRAY_ENABLED = False

logger = get_logger("sql-ai-agent.main")
settings = get_settings()

app = FastAPI(
    title="SQL AI Agent",
    description="Natural language to SQL using Claude AI",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    os.environ.get("CLOUDFRONT_DOMAIN", ""),
    "http://localhost:3000",
    "http://localhost:5173",
]
ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

if XRAY_ENABLED:
    xray_recorder.configure(service="sql-ai-agent", daemon_address="127.0.0.1:2000")
    app.add_middleware(XRayMiddleware, recorder=xray_recorder)

# ── API KEY AUTH ───────────────────────────────────────────────────────────────
FRONTEND_API_KEY = os.environ.get("FRONTEND_API_KEY", "")


async def require_api_key(x_api_key: str = Header(None)):
    """Enforce the X-API-Key header when FRONTEND_API_KEY is configured.

    Args:
        x_api_key: Value of the X-API-Key request header.

    Raises:
        HTTPException: 403 if FRONTEND_API_KEY is set and the provided key
            does not match.
    """
    if not FRONTEND_API_KEY:
        return
    if x_api_key != FRONTEND_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ── REQUEST LOGGING ───────────────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request, call_next):
    """Middleware that records path, method, status code, and latency per request.

    Args:
        request: The incoming Starlette Request.
        call_next: The next middleware or route handler in the chain.

    Returns:
        The Response produced by the downstream handler.
    """
    start = time.time()
    response = await call_next(request)
    latency_ms = (time.time() - start) * 1000
    query_logger.log_request(
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    return response


# ── MODELS ────────────────────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    """Request body for /ask-and-run and /ask-stream endpoints.

    Attributes:
        question: Natural-language question to send to the AI agent.
        reset_history: Clear conversation history before this turn.
        session_id: Identifies the conversation session.
    """

    question: str
    reset_history: Optional[bool] = False
    session_id: str = "default"


class QueryRequest(BaseModel):
    """Request body for the /query endpoint.

    Attributes:
        query: Raw SQL statement to execute against the database.
    """

    query: str


class RuleRequest(BaseModel):
    """Request body for POST /rules.

    Attributes:
        category: Rule category (e.g. "query_rules", "safety_rules").
        rule: Rule text to append under the given category.
    """

    category: str
    rule: str


# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """Return service health status including database connectivity.

    Returns:
        JSON with status ("healthy" | "degraded"), database, and ai fields.
    """
    db_ok = test_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "ai": "ready",
    }


@app.post("/ask-and-run", dependencies=[Depends(require_api_key)])
def ask_and_run(request: QuestionRequest):
    """Translate a natural-language question to SQL and execute it in one step.

    Routes the question to the correct database, generates SQL via Claude,
    runs the query, and returns both the AI answer and raw query results.

    Args:
        request: QuestionRequest body.

    Returns:
        JSON with question, answer, sql, db_name, results, query_error,
        session_id, and history_length.

    Raises:
        HTTPException: 400 if the question is empty; 500 on agent failure.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = ask_agent(
        user_question=request.question,
        reset_history=request.reset_history,
        session_id=request.session_id,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    sql = result.get("sql")
    db_name = result.get("db_name", "airlines_db")
    query_result = None
    if sql and sql.strip().upper().startswith("SELECT"):
        query_result = execute_query(sql, db_name=db_name)
    return {
        "success": True,
        "question": request.question,
        "answer": result["answer"],
        "explanation": result.get("explanation", ""),
        "sql": sql,
        "db_name": db_name,
        "results": (
            query_result.get("rows") if query_result and query_result.get("success") else None
        ),
        "query_error": (
            query_result.get("error") if query_result and not query_result.get("success") else None
        ),
        "session_id": result["session_id"],
        "history_length": result["history_length"],
    }


@app.post("/ask-stream", dependencies=[Depends(require_api_key)])
def ask_stream(request: QuestionRequest):
    """Translate a natural-language question to SQL without executing the query.

    Useful for clients that want the AI answer and SQL text separately.

    Args:
        request: QuestionRequest body.

    Returns:
        JSON with success, answer, and session_id.

    Raises:
        HTTPException: 400 if the question is empty; 500 on agent failure.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = ask_agent(
        user_question=request.question,
        reset_history=request.reset_history,
        session_id=request.session_id,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return {
        "success": True,
        "answer": result["answer"],
        "session_id": result["session_id"],
    }


@app.post("/query", dependencies=[Depends(require_api_key)])
def run_query(request: QueryRequest):
    """Execute a raw SQL query against the default database.

    Args:
        request: QueryRequest body with a SQL statement.

    Returns:
        JSON with success, rows, and data.

    Raises:
        HTTPException: 400 if the query fails to execute.
    """
    result = execute_query(request.query)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "rows": result.get("rows"), "data": result.get("data")}


@app.get("/schema")
def get_schema():
    """Return the formatted database schema for the default database.

    Returns:
        JSON with success and the schema string.
    """
    schema = get_schema_for_claude()
    return {"success": True, "schema": schema}


@app.get("/rules")
def get_rules():
    """Return the formatted business rules string for Claude's prompt.

    Returns:
        JSON with success and the rules string.
    """
    rules = get_rules_for_claude()
    return {"success": True, "rules": rules}


@app.post("/rules")
def add_rule(request: RuleRequest):
    """Append a new rule to the specified category in rules.yaml.

    Args:
        request: RuleRequest body with category and rule text.

    Returns:
        JSON with success and a confirmation message.

    Raises:
        HTTPException: 500 if the rule cannot be persisted.
    """
    success = add_custom_rule(category=request.category, rule=request.rule)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add rule")
    return {"success": True, "message": f"Rule added to '{request.category}'"}


@app.post("/reset")
def reset_chat():
    """Clear the default conversation session history.

    Returns:
        JSON with success and a confirmation message.
    """
    return reset_conversation()


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(settings.app_port),
        reload=settings.debug,
    )
