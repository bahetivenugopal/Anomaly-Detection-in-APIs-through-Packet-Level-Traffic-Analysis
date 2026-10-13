"""
auth_service.py — Auth API
--------------------------
Runs on port 9001.
Endpoints:
  POST /auth/login       — returns a JWT-like token
  POST /auth/verify      — verifies a token
  GET  /auth/health      — health check
  POST /control          — fault injection control
  GET  /status           — current fault status
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import uuid
import time
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fault_controller import apply_fault, reset_fault, apply_fault_delay, get_fault_status

app = FastAPI(title="Auth Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory token store
_tokens: dict[str, dict] = {}


# ── Request/Response Models ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyRequest(BaseModel):
    token: str

class ControlRequest(BaseModel):
    fault: str                          # "latency_spike" | "latency_drift" | "error_rate" | "packet_loss" | "cpu_overload" | "retry_storm" | "reset"
    duration_seconds: int = 60
    spike_ms: int = 1000
    start_ms: int = 100
    increment_ms: int = 25
    max_ms: int = 2000
    error_pct: int = 50
    loss_pct: int = 30


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/auth/health")
async def health():
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Auth service degraded")
    return {
        "service": "auth",
        "status": "healthy",
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() % 86400, 2)
    }


@app.post("/auth/login")
async def login(req: LoginRequest):
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    # Simulate auth logic — accept any non-empty credentials for demo
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password required")

    token = str(uuid.uuid4())
    _tokens[token] = {
        "username": req.username,
        "issued_at": time.time(),
        "expires_at": time.time() + 3600
    }

    return {
        "token": token,
        "username": req.username,
        "expires_in": 3600,
        "token_type": "Bearer",
        "issued_at": time.time()
    }


@app.post("/auth/verify")
async def verify(req: VerifyRequest):
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    token_data = _tokens.get(req.token)
    if not token_data:
        # For demo: generate a valid result for any token so dependent APIs work
        return {
            "valid": True,
            "username": "demo_user",
            "expires_at": time.time() + 3600
        }

    if time.time() > token_data["expires_at"]:
        raise HTTPException(status_code=401, detail="Token expired")

    return {
        "valid": True,
        "username": token_data["username"],
        "expires_at": token_data["expires_at"]
    }


@app.post("/control")
async def control(req: ControlRequest):
    """Fault injection control endpoint."""
    if req.fault == "reset":
        reset_fault()
        return {"message": "All faults cleared", "status": "normal"}

    apply_fault(req.dict())
    return {
        "message": f"Fault '{req.fault}' activated on Auth API",
        "duration_seconds": req.duration_seconds,
        "fault": req.fault
    }


@app.get("/status")
async def status():
    return {
        "service": "auth",
        "port": 9001,
        "fault_status": get_fault_status()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001, log_level="warning")
