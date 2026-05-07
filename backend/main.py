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
    if not FRONTEND_API_KEY:
        return
    if x_api_key != FRONTEND_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ── REQUEST LOGGING ───────────────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request, call_next):
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
    question: str
    reset_history: Optional[bool] = False
    session_id: str = "default"


class QueryRequest(BaseModel):
    query: str


class RuleRequest(BaseModel):
    category: str
    rule: str


# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    db_ok = test_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "ai": "ready",
    }


@app.post("/ask-and-run", dependencies=[Depends(require_api_key)])
def ask_and_run(request: QuestionRequest):
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
    result = execute_query(request.query)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "rows": result.get("rows"), "data": result.get("data")}


@app.get("/schema")
def get_schema():
    schema = get_schema_for_claude()
    return {"success": True, "schema": schema}


@app.get("/rules")
def get_rules():
    rules = get_rules_for_claude()
    return {"success": True, "rules": rules}


@app.post("/rules")
def add_rule(request: RuleRequest):
    success = add_custom_rule(category=request.category, rule=request.rule)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add rule")
    return {"success": True, "message": f"Rule added to '{request.category}'"}


@app.post("/reset")
def reset_chat():
    return reset_conversation()


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(settings.app_port),
        reload=settings.debug,
    )
