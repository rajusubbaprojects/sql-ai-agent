import os
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.logger import query_logger

app = FastAPI()

# ── CORS ──────────────────────────────────────────────────────────────────────
# Replace "*" with explicit origins.
# CLOUDFRONT_DOMAIN is injected via ECS task definition environment variables.
# During local dev, localhost:3000 / 5173 are also allowed.

ALLOWED_ORIGINS = [
    os.environ.get("CLOUDFRONT_DOMAIN", ""),  # e.g. https://xxxx.cloudfront.net
    "http://localhost:3000",
    "http://localhost:5173",
]
# Filter out empty strings (in case env var isn't set yet)
ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# ── API KEY DEPENDENCY ────────────────────────────────────────────────────────
# The key is stored in AWS Secrets Manager and injected into the ECS task
# as the FRONTEND_API_KEY environment variable (same pattern as your DB creds).

FRONTEND_API_KEY = os.environ.get("FRONTEND_API_KEY", "")


async def require_api_key(x_api_key: str = Header(None)):
    """
    FastAPI dependency — attach with Depends(require_api_key) on any route
    you want to protect. Returns 403 if the header is missing or wrong.
    Health check is intentionally left unprotected.
    """
    if not FRONTEND_API_KEY:
        # If the env var isn't set (e.g. during early local dev), skip check.
        # Remove this branch once you have the key wired up everywhere.
        return
    if x_api_key != FRONTEND_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ── REQUEST LOGGING MIDDLEWARE ────────────────────────────────────────────────
# Unchanged from your Phase 7B implementation — keeping it exactly as-is.


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


# ── ROUTE EXAMPLES ────────────────────────────────────────────────────────────
# Add Depends(require_api_key) to every route you want protected.
# /health stays open — ALB health checks hit it without any headers.


@app.get("/health")
async def health():
    return {"status": "ok"}  # no dependency — intentional


@app.post("/ask-and-run")
async def ask_and_run(body: dict, _=Depends(require_api_key)):
    pass  # your existing implementation goes here


@app.post("/ask-stream")
async def ask_stream(body: dict, _=Depends(require_api_key)):
    pass  # your existing implementation goes here


@app.post("/query")
async def query(body: dict, _=Depends(require_api_key)):
    pass  # your existing implementation goes here
