"""
fault_controller.py
-------------------
Shared fault state for all three APIs.
Each API imports this module to know what fault (if any) is currently active.
Faults are set via the /control endpoint on each API.
"""

import asyncio
import time
import random

# Global fault state — shared across the process
_fault = {
    "type": None,          # None | "latency_spike" | "latency_drift" | "error_rate" | "packet_loss" | "retry_storm" | "cpu_overload"
    "active": False,
    "start_time": None,
    "duration_seconds": 0,

    # Latency spike
    "spike_ms": 0,

    # Latency drift
    "drift_start_ms": 0,
    "drift_increment_ms": 0,
    "drift_max_ms": 0,
    "drift_current_ms": 0,
    "drift_request_count": 0,

    # Error rate
    "error_pct": 0,        # 0-100

    # Packet loss (simulated as timeout probability)
    "loss_pct": 0,         # 0-100
}


def apply_fault(config: dict):
    """Called by /control endpoint. Sets the active fault."""
    global _fault
    _fault["type"] = config.get("fault")
    _fault["active"] = True
    _fault["start_time"] = time.time()
    _fault["duration_seconds"] = config.get("duration_seconds", 60)

    # Latency spike
    _fault["spike_ms"] = config.get("spike_ms", 1000)

    # Latency drift
    _fault["drift_start_ms"] = config.get("start_ms", 100)
    _fault["drift_increment_ms"] = config.get("increment_ms", 25)
    _fault["drift_max_ms"] = config.get("max_ms", 2000)
    _fault["drift_current_ms"] = config.get("start_ms", 100)
    _fault["drift_request_count"] = 0

    # Error rate
    _fault["error_pct"] = config.get("error_pct", 50)

    # Packet loss
    _fault["loss_pct"] = config.get("loss_pct", 30)


def reset_fault():
    """Called by /control with fault=reset. Clears all faults."""
    global _fault
    _fault["type"] = None
    _fault["active"] = False
    _fault["start_time"] = None


def _check_expired():
    """Auto-expire faults after duration_seconds."""
    if _fault["active"] and _fault["start_time"]:
        elapsed = time.time() - _fault["start_time"]
        if elapsed > _fault["duration_seconds"]:
            reset_fault()


async def apply_fault_delay() -> bool:
    """
    Call this at the start of every API endpoint handler.
    Returns True if the request should return a 503 error (for error/loss faults).
    Otherwise sleeps for the appropriate delay and returns False.
    """
    _check_expired()

    if not _fault["active"] or _fault["type"] is None:
        return False  # No fault — proceed normally

    fault_type = _fault["type"]

    if fault_type == "latency_spike":
        await asyncio.sleep(_fault["spike_ms"] / 1000.0)

    elif fault_type == "latency_drift":
        delay = min(_fault["drift_current_ms"], _fault["drift_max_ms"])
        await asyncio.sleep(delay / 1000.0)
        _fault["drift_request_count"] += 1
        _fault["drift_current_ms"] = min(
            _fault["drift_start_ms"] + _fault["drift_request_count"] * _fault["drift_increment_ms"],
            _fault["drift_max_ms"]
        )

    elif fault_type == "error_rate":
        if random.randint(1, 100) <= _fault["error_pct"]:
            return True  # Signal: return error

    elif fault_type == "packet_loss":
        if random.randint(1, 100) <= _fault["loss_pct"]:
            await asyncio.sleep(30)  # Simulate dropped packet (long timeout)

    elif fault_type == "cpu_overload":
        # Random jitter across all responses
        jitter = random.uniform(50, 800)
        await asyncio.sleep(jitter / 1000.0)

    elif fault_type == "retry_storm":
        # Intermittent errors to force client retries
        if random.randint(1, 100) <= 60:
            return True

    return False


def get_fault_status() -> dict:
    _check_expired()
    return {
        "active": _fault["active"],
        "type": _fault["type"],
        "elapsed_seconds": round(time.time() - _fault["start_time"], 1) if _fault["start_time"] else 0,
        "remaining_seconds": max(0, round(_fault["duration_seconds"] - (time.time() - _fault["start_time"]), 1)) if _fault["start_time"] else 0,
    }
