"""
traffic_generator.py
--------------------
Sends realistic HTTP traffic through the Intelligence Proxy to all three APIs.
Simulates normal usage patterns. Also provides CLI fault injection.

Usage:
  python traffic_generator.py                    # Normal traffic (infinite)
  python traffic_generator.py --rps 5            # 5 requests/sec
  python traffic_generator.py --fault latency_spike --api payments
  python traffic_generator.py --fault reset --api all
"""

import requests
import time
import random
import argparse
import threading
import sys
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box

PROXY = "http://localhost:8080"

console = Console()

# Request templates per API
REQUESTS = {
    "/auth": [
        ("POST", "/auth/login",  {"username": "alice", "password": "pass123"}),
        ("POST", "/auth/login",  {"username": "bob",   "password": "securepass"}),
        ("POST", "/auth/verify", {"token": "demo_token"}),
        ("GET",  "/auth/health", None),
    ],
    "/payments": [
        ("POST", "/payments/process", {"amount": 49.99,  "currency": "USD", "recipient": "vendor_A", "token": "demo_token"}),
        ("POST", "/payments/process", {"amount": 129.00, "currency": "USD", "recipient": "vendor_B", "token": "demo_token"}),
        ("GET",  "/payments/history", None),
        ("GET",  "/payments/health",  None),
    ],
    "/inventory": [
        ("GET",  "/inventory/items",         None),
        ("GET",  "/inventory/item/ITEM001",  None),
        ("GET",  "/inventory/item/ITEM003",  None),
        ("POST", "/inventory/reserve",       {"sku": "ITEM002", "quantity": 1, "token": "demo_token"}),
        ("GET",  "/inventory/health",        None),
    ],
}

FAULT_PRESETS = {
    "latency_spike": {
        "fault": "latency_spike",
        "spike_ms": 1500,
        "duration_seconds": 60,
    },
    "latency_drift": {
        "fault": "latency_drift",
        "start_ms": 50,
        "increment_ms": 30,
        "max_ms": 2000,
        "duration_seconds": 90,
    },
    "error_rate": {
        "fault": "error_rate",
        "error_pct": 60,
        "duration_seconds": 60,
    },
    "packet_loss": {
        "fault": "packet_loss",
        "loss_pct": 40,
        "duration_seconds": 60,
    },
    "cpu_overload": {
        "fault": "cpu_overload",
        "duration_seconds": 60,
    },
    "retry_storm": {
        "fault": "retry_storm",
        "duration_seconds": 45,
    },
}

API_PORTS = {
    "auth":      9001,
    "/auth":     9001,
    "payments":  9002,
    "/payments": 9002,
    "inventory": 9003,
    "/inventory":9003,
}

stats = {
    "total": 0,
    "success": 0,
    "errors": 0,
    "avg_latency": 0.0,
    "last_status": {},
}


def send_request(method: str, path: str, body: dict | None) -> tuple[int, float]:
    """Send one request through the proxy."""
    url = PROXY + path
    try:
        start = time.time()
        if method == "GET":
            resp = requests.get(url, timeout=12)
        else:
            resp = requests.post(url, json=body, timeout=12)
        latency = (time.time() - start) * 1000
        return resp.status_code, latency
    except requests.Timeout:
        return 0, 12000.0
    except Exception as e:
        return -1, 0.0


def inject_fault(fault_name: str, api: str):
    """Send fault injection command directly to the API's /control endpoint."""
    if fault_name == "reset":
        payload = {"fault": "reset"}
    else:
        payload = FAULT_PRESETS.get(fault_name)
        if not payload:
            console.print(f"[red]Unknown fault: {fault_name}[/red]")
            console.print(f"Available: {list(FAULT_PRESETS.keys())}")
            return

    targets = []
    if api == "all":
        targets = [9001, 9002, 9003]
    else:
        port = API_PORTS.get(api)
        if not port:
            console.print(f"[red]Unknown API: {api}[/red]")
            return
        targets = [port]

    for port in targets:
        try:
            resp = requests.post(f"http://localhost:{port}/control", json=payload, timeout=5)
            console.print(f"[green]✓ Fault '{fault_name}' injected on port {port}: {resp.json().get('message', 'OK')}[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to inject on port {port}: {e}[/red]")


def run_traffic(rps: float = 3.0, verbose: bool = False):
    """Continuous traffic generation through the proxy."""
    interval = 1.0 / rps
    latencies = []

    console.print(f"\n[bold cyan]🚀 Traffic Generator Starting[/bold cyan]")
    console.print(f"[dim]Proxy: {PROXY}  |  RPS: {rps}  |  Ctrl+C to stop[/dim]\n")

    # Weighted API selection — payments and inventory called more often
    api_pool = ["/auth"] * 2 + ["/payments"] * 3 + ["/inventory"] * 3

    try:
        while True:
            loop_start = time.time()

            # Pick a random API and a random endpoint within it
            api = random.choice(api_pool)
            method, path, body = random.choice(REQUESTS[api])

            status, latency = send_request(method, path, body)

            stats["total"] += 1
            stats["last_status"][path] = status

            if 200 <= status < 300:
                stats["success"] += 1
                if verbose:
                    console.print(f"[green]{method:4} {path:35} {status} {latency:7.1f}ms[/green]")
            elif status == 0:
                stats["errors"] += 1
                if verbose:
                    console.print(f"[red]{method:4} {path:35} TIMEOUT[/red]")
            else:
                stats["errors"] += 1
                if verbose:
                    console.print(f"[yellow]{method:4} {path:35} {status} {latency:7.1f}ms[/yellow]")

            if latency > 0:
                latencies.append(latency)
                if len(latencies) > 50:
                    latencies.pop(0)
                stats["avg_latency"] = sum(latencies) / len(latencies)

            if not verbose and stats["total"] % 10 == 0:
                err_rate = stats["errors"] / stats["total"] * 100
                console.print(
                    f"[dim]Requests: {stats['total']:5}  "
                    f"Success: {stats['success']:5}  "
                    f"Errors: {stats['errors']:4}  "
                    f"Err%: {err_rate:5.1f}%  "
                    f"Avg Lat: {stats['avg_latency']:7.1f}ms[/dim]"
                )

            # Sleep to maintain target RPS
            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Traffic generator stopped.[/bold yellow]")
        console.print(f"Total: {stats['total']}  Success: {stats['success']}  Errors: {stats['errors']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traffic Generator & Fault Injector")
    parser.add_argument("--rps",     type=float, default=3.0,   help="Requests per second (default: 3.0)")
    parser.add_argument("--verbose", action="store_true",        help="Show every request")
    parser.add_argument("--fault",   type=str,   default=None,  help="Inject fault: latency_spike | latency_drift | error_rate | packet_loss | cpu_overload | retry_storm | reset")
    parser.add_argument("--api",     type=str,   default="all", help="Target API: auth | payments | inventory | all")
    args = parser.parse_args()

    if args.fault:
        inject_fault(args.fault, args.api)
    else:
        run_traffic(rps=args.rps, verbose=args.verbose)
