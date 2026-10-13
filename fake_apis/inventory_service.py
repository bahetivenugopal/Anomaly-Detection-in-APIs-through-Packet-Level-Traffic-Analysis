"""
inventory_service.py — Inventory API
--------------------------------------
Runs on port 9003.
Depends on Auth API (calls /auth/verify before fetching inventory).
Endpoints:
  GET  /inventory/items       — list all items
  GET  /inventory/item/{id}   — get single item
  POST /inventory/reserve     — reserve stock
  GET  /inventory/health      — health check
  POST /control               — fault injection
  GET  /status                — fault status
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import uuid
import time
import random
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fault_controller import apply_fault, reset_fault, apply_fault_delay, get_fault_status

app = FastAPI(title="Inventory Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_URL = "http://localhost:9001"

# Static inventory for demo
_inventory = {
    "ITEM001": {"name": "Laptop Pro 15", "sku": "ITEM001", "stock": 142, "price": 1299.99, "category": "Electronics"},
    "ITEM002": {"name": "Wireless Mouse", "sku": "ITEM002", "stock": 890, "price": 29.99, "category": "Accessories"},
    "ITEM003": {"name": "USB-C Hub", "sku": "ITEM003", "stock": 456, "price": 49.99, "category": "Accessories"},
    "ITEM004": {"name": "Monitor 27\"", "sku": "ITEM004", "stock": 78, "price": 399.99, "category": "Electronics"},
    "ITEM005": {"name": "Mechanical Keyboard", "sku": "ITEM005", "stock": 234, "price": 149.99, "category": "Accessories"},
}

_reservations: list[dict] = []


# ── Models ───────────────────────────────────────────────────────────────────

class ReserveRequest(BaseModel):
    sku: str
    quantity: int
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

@app.get("/inventory/health")
async def health():
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Inventory service degraded")
    return {
        "service": "inventory",
        "status": "healthy",
        "timestamp": time.time(),
        "items_tracked": len(_inventory)
    }


@app.get("/inventory/items")
async def list_items():
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Inventory service unavailable")

    # Verify via auth (creates dependency)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{AUTH_URL}/auth/verify", json={"token": "system_token"})
    except Exception:
        pass  # Continue for demo resilience

    return {
        "items": list(_inventory.values()),
        "total": len(_inventory),
        "timestamp": time.time()
    }


@app.get("/inventory/item/{sku}")
async def get_item(sku: str):
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Inventory service unavailable")

    item = _inventory.get(sku.upper())
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {sku} not found")

    return item


@app.post("/inventory/reserve")
async def reserve_item(req: ReserveRequest):
    should_error = await apply_fault_delay()
    if should_error:
        raise HTTPException(status_code=503, detail="Inventory reservation unavailable")

    # Auth dependency
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            auth_resp = await client.post(
                f"{AUTH_URL}/auth/verify",
                json={"token": req.token}
            )
    except Exception:
        pass

    item = _inventory.get(req.sku.upper())
    if not item:
        raise HTTPException(status_code=404, detail=f"SKU {req.sku} not found")

    if item["stock"] < req.quantity:
        raise HTTPException(status_code=409, detail="Insufficient stock")

    item["stock"] -= req.quantity
    reservation = {
        "reservation_id": str(uuid.uuid4())[:8].upper(),
        "sku": req.sku,
        "quantity": req.quantity,
        "reserved_at": time.time()
    }
    _reservations.append(reservation)
    return reservation


@app.post("/control")
async def control(req: ControlRequest):
    if req.fault == "reset":
        reset_fault()
        return {"message": "All faults cleared", "status": "normal"}
    apply_fault(req.dict())
    return {
        "message": f"Fault '{req.fault}' activated on Inventory API",
        "duration_seconds": req.duration_seconds,
        "fault": req.fault
    }


@app.get("/status")
async def status():
    return {
        "service": "inventory",
        "port": 9003,
        "fault_status": get_fault_status()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9003, log_level="warning")
