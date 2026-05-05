# Entry point — FastAPI app, all routes defined here
# Entry point — FastAPI app, all routes defined here

from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agent import ask_agent, get_history, reset_conversation
from backend.config import get_settings
from backend.db import execute_query, test_connection
from backend.rules import add_custom_rule, get_rules_for_claude
from backend.schema_extractor import get_schema_for_claude

settings = get_settings()

# ── Initialize FastAPI ─────────────────────────────────
app = FastAPI(
    title="SQL AI Agent",
    description="Natural language to SQL using Claude AI",
    version="1.0.0",
)

# ── CORS Middleware ────────────────────────────────────
# Allows React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ────────────────────────────
class QuestionRequest(BaseModel):
    question: str
    reset_history: Optional[bool] = False


class QueryRequest(BaseModel):
    query: str


class RuleRequest(BaseModel):
    category: str
    rule: str


# ── Routes ─────────────────────────────────────────────


@app.get("/")
def root():
    """Health check — is the API alive?"""
    return {"status": "online", "app": "SQL AI Agent", "version": "1.0.0"}


@app.get("/health")
def health_check():
    """
    Deep health check — tests DB connection too.
    Used by AWS Lambda and load balancers.
    """
    db_ok = test_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "ai": "ready",
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):
    """
    Main endpoint — ask a natural language question.
    Claude returns SQL + explanation.
    """
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
    """
    Execute a raw SQL query directly.
    Used for running queries Claude generates.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Basic safety check
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
    """
    Return the current database schema.
    Used by frontend Context Panel.
    """
    schema = get_schema_for_claude()
    return {"success": True, "schema": schema}


@app.get("/rules")
def get_rules():
    """
    Return current business rules.
    Used by frontend Context Panel.
    """
    rules = get_rules_for_claude()
    return {"success": True, "rules": rules}


@app.post("/rules")
def add_rule(request: RuleRequest):
    """
    Add a new business rule at runtime.
    No restart needed.
    """
    success = add_custom_rule(category=request.category, rule=request.rule)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to add rule")

    return {"success": True, "message": f"Rule added to '{request.category}'"}


@app.get("/history")
def get_conversation_history():
    """Return current conversation history."""
    history = get_history()
    return {"success": True, "history": history, "length": len(history)}


@app.post("/reset")
def reset_chat():
    """Reset conversation history — start fresh."""
    return reset_conversation()


# ── Run server ─────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(settings.app_port),
        reload=settings.debug,
    )
