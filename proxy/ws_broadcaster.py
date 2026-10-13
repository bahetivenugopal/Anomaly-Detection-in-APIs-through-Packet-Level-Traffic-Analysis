"""
ws_broadcaster.py
-----------------
Manages all active WebSocket connections and broadcasts events to the dashboard.
Message types:
  - packet       : new intercepted packet data
  - metrics      : updated metrics for an endpoint
  - baseline     : current baseline state
  - anomaly      : anomaly event detected
  - correlation  : cross-API correlation result
  - severity     : updated severity report
  - graph        : API dependency graph state
  - sniffer      : real-world packet from bonus sniffer
  - system       : system status / heartbeat
"""

import asyncio
import json
import time
import threading
from typing import Set
from fastapi import WebSocket


class WSBroadcaster:
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        print(f"[WS] Client connected. Total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)
        print(f"[WS] Client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, msg_type: str, data: dict):
        """Broadcast a message to all connected dashboard clients."""
        payload = json.dumps({
            "type": msg_type,
            "timestamp": time.time(),
            "data": data
        })

        if not self._connections:
            return

        dead = set()
        async with self._lock:
            conns = list(self._connections)

        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    def broadcast_sync(self, msg_type: str, data: dict):
        """
        Thread-safe synchronous broadcast — use this from non-async contexts.
        """
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.broadcast(msg_type, data),
                self._loop
            )

    def emit_packet(self, packet_data: dict):
        self.broadcast_sync("packet", packet_data)

    def emit_metrics(self, metrics_data: dict):
        self.broadcast_sync("metrics", metrics_data)

    def emit_baseline(self, baseline_data: dict):
        self.broadcast_sync("baseline", baseline_data)

    def emit_anomaly(self, anomaly_data: dict):
        self.broadcast_sync("anomaly", anomaly_data)

    def emit_correlation(self, correlation_data: dict):
        self.broadcast_sync("correlation", correlation_data)

    def emit_severity(self, severity_data: dict):
        self.broadcast_sync("severity", severity_data)

    def emit_graph(self, graph_data: dict):
        self.broadcast_sync("graph", graph_data)

    def emit_sniffer(self, sniffer_data: dict):
        self.broadcast_sync("sniffer", sniffer_data)

    def emit_system(self, system_data: dict):
        self.broadcast_sync("system", system_data)


# Global singleton
broadcaster = WSBroadcaster()
