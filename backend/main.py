import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agent import ask_agent, get_history, reset_conversation
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if XRAY_ENABLED:
    xray_recorder.configure(service="sql-ai-agent", daemon_address="127.0.0.1:2000")
    app.add_middleware(XRayMiddleware, recorder=xray_recorder)

logger = get_logger("sql-ai-agent.main")
settings = get_settings()

app = FastAPI(
    title="SQL AI Agent",
    description="Natural language to SQL using Claude AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class QuestionRequest(BaseModel):
    question: str
    reset_history: Optional[bool] = False


class QueryRequest(BaseModel):
    query: str


class RuleRequest(BaseModel):
    category: str
    rule: str


@app.get("/")
def root():
    return {"status": "online", "app": "SQL AI Agent", "version": "1.0.0"}


@app.get("/health")
def health_check():
    db_ok = test_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "ai": "ready",
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = ask_agent(user_question=request.question, reset_history=request.reset_history)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return {
        "success": True,
        "question": request.question,
        "answer": result["answer"],
        "history_length": result["history_length"],
    }


@app.post("/query")
def run_query(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    dangerous = ["DROP", "TRUNCATE", "DELETE", "ALTER"]
    query_upper = request.query.upper()
    for word in dangerous:
        if word in query_upper:
            raise HTTPException(
                status_code=403,
                detail=f"Dangerous operation '{word}' not allowed via API",
            )
    result = execute_query(request.query)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Query failed"))
    return result


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


@app.get("/history")
def get_conversation_history():
    history = get_history()
    return {"success": True, "history": history, "length": len(history)}


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
