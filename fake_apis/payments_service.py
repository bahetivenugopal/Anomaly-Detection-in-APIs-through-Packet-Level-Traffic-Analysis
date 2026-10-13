"""
payments_service.py — Payments API
------------------------------------
Runs on port 9002.
Depends on Auth API (calls /auth/verify before processing).
Endpoints:
  POST /payments/process   — process a payment
  GET  /payments/history   — get payment history
  GET  /payments/health    — health check
  POST /control            — fault injection
  GET  /status             — fault status
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import uuid
import time
import random
import httpx
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from fault_controller import apply_fault, reset_fault, apply_fault_delay, get_fault_status

app = FastAPI(title="Payments Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_URL = "http://localhost:9001"

# In-memory payment history
_payments: list[dict] = []


# ── Models ───────────────────────────────────────────────────────────────────

class PaymentRequest(BaseModel):
    amount: float
    currency: str = "USD"
    recipient: str
    description: str = ""
    token: str = "demo_token"

class ControlRequest(BaseModel):
    fault: str
    duration_seconds: int = 60
    spike_ms: int = 1000
    start_ms: int = 100
    increment_ms: int = 25
    max_ms: int = 2000
    error_pct: int = 50
    loss_pct: int = 30


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/payments/health")
async def health():
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Payments service degraded")
    return {
        "service": "payments",
        "status": "healthy",
        "timestamp": time.time(),
        "total_processed": len(_payments)
    }


@app.post("/payments/process")
async def process_payment(req: PaymentRequest):
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Payment processing unavailable")

    # Call Auth API to verify token (creates dependency)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            auth_resp = await client.post(
                f"{AUTH_URL}/auth/verify",
                json={"token": req.token}
            )
            if auth_resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Token verification failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Auth service timeout — payment cannot proceed")
    except httpx.ConnectError:
        # Auth service down — still process for demo resilience
        pass

    payment_id = str(uuid.uuid4())[:8].upper()
    payment = {
        "payment_id": payment_id,
        "amount": req.amount,
        "currency": req.currency,
        "recipient": req.recipient,
        "description": req.description,
        "status": "completed",
        "processed_at": time.time(),
        "fee": round(req.amount * 0.029, 2)
    }
    _payments.append(payment)

    return payment


@app.get("/payments/history")
async def payment_history():
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Payments service degraded")
    return {
        "payments": _payments[-20:],  # Last 20
        "total_count": len(_payments)
    }


@app.post("/control")
async def control(req: ControlRequest):
    if req.fault == "reset":
        reset_fault()
        return {"message": "All faults cleared", "status": "normal"}
    apply_fault(req.dict())
    return {
        "message": f"Fault '{req.fault}' activated on Payments API",
        "duration_seconds": req.duration_seconds,
        "fault": req.fault
    }


@app.get("/status")
async def status():
    return {
        "service": "payments",
        "port": 9002,
        "fault_status": get_fault_status()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9002, log_level="warning")
