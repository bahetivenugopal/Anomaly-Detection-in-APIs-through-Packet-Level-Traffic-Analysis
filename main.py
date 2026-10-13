"""
main.py
-------
Master launcher for the Anomaly Detection project.
Starts all services in the correct order with health checks.

Usage:
  python main.py              # Start everything
  python main.py --services   # Start only the 3 API services
  python main.py --proxy      # Start only the proxy + WebSocket server
  python main.py --check      # Health check all services
"""

import subprocess
import sys
import os
import time
import argparse
import threading
import requests
from colorama import init, Fore, Style

init(autoreset=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    {
        "name":    "Auth API",
        "script":  os.path.join(BASE_DIR, "fake_apis", "auth_service.py"),
        "port":    9001,
        "color":   Fore.CYAN,
        "check":   "http://localhost:9001/auth/health",
    },
    {
        "name":    "Payments API",
        "script":  os.path.join(BASE_DIR, "fake_apis", "payments_service.py"),
        "port":    9002,
        "color":   Fore.GREEN,
        "check":   "http://localhost:9002/payments/health",
    },
    {
        "name":    "Inventory API",
        "script":  os.path.join(BASE_DIR, "fake_apis", "inventory_service.py"),
        "port":    9003,
        "color":   Fore.YELLOW,
        "check":   "http://localhost:9003/inventory/health",
    },
]

PROXY = {
    "name":   "Intelligence Proxy",
    "script": os.path.join(BASE_DIR, "proxy", "interceptor.py"),
    "port":   8080,
    "color":  Fore.MAGENTA,
    "check":  "http://localhost:8080/api/status",
}

_processes = []


def print_banner():
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗
║     ANOMALY DETECTION IN APIs — PACKET-LEVEL TRAFFIC ANALYSIS ║
║                    VIT TYA13 — 2025-26                        ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def wait_for_service(url: str, name: str, timeout: int = 15) -> bool:
    """Poll until service is ready or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_service(svc: dict) -> subprocess.Popen:
    """Start a Python service as a subprocess."""
    print(f"{svc['color']}  → Starting {svc['name']} on port {svc['port']}...{Style.RESET_ALL}", end=" ", flush=True)

    proc = subprocess.Popen(
        [sys.executable, svc["script"]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.path.dirname(svc["script"]),
    )

    ready = wait_for_service(svc["check"], svc["name"])
    if ready:
        print(f"{Fore.GREEN}✓ Ready{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Failed to start (check port {svc['port']}){Style.RESET_ALL}")

    return proc


def check_all():
    """Health check all services."""
    print(f"\n{Fore.CYAN}Health Check:{Style.RESET_ALL}")
    all_services = SERVICES + [PROXY]
    for svc in all_services:
        try:
            resp = requests.get(svc["check"], timeout=3)
            status = f"{Fore.GREEN}✓ UP   {Style.RESET_ALL}" if resp.status_code < 500 else f"{Fore.RED}✗ ERROR{Style.RESET_ALL}"
        except Exception:
            status = f"{Fore.RED}✗ DOWN {Style.RESET_ALL}"
        print(f"  {status}  {svc['name']:20} port {svc['port']}")
    print()


def start_all():
    print_banner()

    print(f"{Fore.WHITE}Starting Enterprise API Services...{Style.RESET_ALL}")
    for svc in SERVICES:
        proc = start_service(svc)
        _processes.append(proc)

    print(f"\n{Fore.WHITE}Starting Intelligence Proxy...{Style.RESET_ALL}")
    proc = start_service(PROXY)
    _processes.append(proc)

    print(f"\n{Fore.GREEN}{'─'*62}")
    print(f"  All systems operational!")
    print(f"{'─'*62}{Style.RESET_ALL}")
    print(f"\n  {Fore.CYAN}Dashboard:{Style.RESET_ALL}      http://localhost:3000")
    print(f"  {Fore.CYAN}Proxy API:{Style.RESET_ALL}       http://localhost:8080/api/status")
    print(f"  {Fore.CYAN}WebSocket:{Style.RESET_ALL}       ws://localhost:8080/ws")
    print(f"  {Fore.CYAN}Auth API:{Style.RESET_ALL}        http://localhost:9001/auth/health")
    print(f"  {Fore.CYAN}Payments API:{Style.RESET_ALL}    http://localhost:9002/payments/health")
    print(f"  {Fore.CYAN}Inventory API:{Style.RESET_ALL}   http://localhost:9003/inventory/health")
    print(f"\n  {Fore.YELLOW}Traffic generator:{Style.RESET_ALL}")
    print(f"    python client/traffic_generator.py")
    print(f"\n  {Fore.YELLOW}Inject faults:{Style.RESET_ALL}")
    print(f"    python client/traffic_generator.py --fault latency_drift --api payments")
    print(f"    python client/traffic_generator.py --fault error_rate --api auth")
    print(f"    python client/traffic_generator.py --fault reset --api all")
    print(f"\n  {Fore.YELLOW}Bonus sniffer (run as Admin):{Style.RESET_ALL}")
    print(f"    python bonus/live_sniffer.py --list")
    print(f"    python bonus/live_sniffer.py --iface 'Wi-Fi' --filter 'tcp port 443'")
    print(f"\n  {Fore.RED}Press Ctrl+C to stop all services{Style.RESET_ALL}\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Shutting down all services...{Style.RESET_ALL}")
        for proc in _processes:
            try:
                proc.terminate()
            except Exception:
                pass
        print(f"{Fore.GREEN}All services stopped.{Style.RESET_ALL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anomaly Detection System — Master Launcher")
    parser.add_argument("--services", action="store_true", help="Start only the 3 API services")
    parser.add_argument("--proxy",    action="store_true", help="Start only the proxy")
    parser.add_argument("--check",    action="store_true", help="Health check all services")
    args = parser.parse_args()

    if args.check:
        check_all()
    elif args.services:
        print_banner()
        print(f"{Fore.WHITE}Starting Enterprise API Services only...{Style.RESET_ALL}")
        for svc in SERVICES:
            proc = start_service(svc)
            _processes.append(proc)
        print(f"\n{Fore.GREEN}APIs running. Press Ctrl+C to stop.{Style.RESET_ALL}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            for proc in _processes:
                proc.terminate()
    elif args.proxy:
        print_banner()
        proc = start_service(PROXY)
        _processes.append(proc)
        print(f"\n{Fore.GREEN}Proxy running. Press Ctrl+C to stop.{Style.RESET_ALL}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            proc.terminate()
    else:
        start_all()
