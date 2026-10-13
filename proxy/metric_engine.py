"""
metric_engine.py
----------------
Computes per-endpoint rolling time-series metrics from intercepted request/response data.
Maintains an in-memory rolling window of observations per endpoint.
"""

import time
import collections
import threading
from dataclasses import dataclass, field
from typing import Deque


WINDOW_SECONDS = 30       # Rolling window size for metric computation
RETRY_WINDOW_SECONDS = 5  # Window to detect retries per client


@dataclass
class RequestRecord:
    timestamp: float
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    req_size: int
    resp_size: int
    client_key: str        # (src_ip, src_port) as string


@dataclass
class EndpointMetrics:
    """Live computed metrics for one endpoint."""
    endpoint: str
    timestamp: float = 0.0
    latency_ms: float = 0.0
    error_rate: float = 0.0         # 0.0 - 1.0
    packet_loss: float = 0.0        # 0.0 - 1.0
    retry_count: int = 0
    throughput_rps: float = 0.0
    avg_payload: float = 0.0
    sample_count: int = 0


class MetricEngine:
    def __init__(self):
        self._lock = threading.Lock()
        # Per-endpoint rolling window of records
        self._windows: dict[str, Deque[RequestRecord]] = collections.defaultdict(
            lambda: collections.deque(maxlen=500)
        )
        # Track recent client keys to detect retries
        self._recent_clients: dict[str, Deque[tuple]] = collections.defaultdict(
            lambda: collections.deque(maxlen=200)
        )
        # Count of timeouts per endpoint (for packet loss estimate)
        self._timeout_counts: dict[str, int] = collections.defaultdict(int)
        self._total_counts: dict[str, int] = collections.defaultdict(int)

    def record(self, rec: RequestRecord):
        """Add a new request/response record."""
        with self._lock:
            self._windows[rec.endpoint].append(rec)
            self._total_counts[rec.endpoint] += 1
            if rec.status_code == 0:  # Timeout/no response
                self._timeout_counts[rec.endpoint] += 1
            # Track for retry detection
            self._recent_clients[rec.endpoint].append(
                (rec.timestamp, rec.client_key, rec.method)
            )

    def record_timeout(self, endpoint: str):
        """Explicitly record a request timeout (packet loss simulation)."""
        with self._lock:
            self._timeout_counts[endpoint] += 1
            self._total_counts[endpoint] += 1

    def compute(self, endpoint: str) -> EndpointMetrics | None:
        """Compute current metrics for an endpoint using the rolling window."""
        with self._lock:
            window = self._windows.get(endpoint)
            if not window:
                return None

            now = time.time()
            cutoff = now - WINDOW_SECONDS

            # Filter to records within the rolling window
            recent = [r for r in window if r.timestamp >= cutoff]

            if not recent:
                return None

            # Latency — average of successful responses
            latencies = [r.latency_ms for r in recent if r.status_code != 0 and r.latency_ms > 0]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

            # Error rate — 4xx/5xx / total
            errors = [r for r in recent if r.status_code >= 400]
            error_rate = len(errors) / len(recent) if recent else 0.0

            # Packet loss — timeouts / total in window (use global counter approximation)
            total = self._total_counts[endpoint]
            timeouts = self._timeout_counts[endpoint]
            packet_loss = min(timeouts / total, 1.0) if total > 0 else 0.0

            # Retries — same client, same endpoint, within retry window
            retry_cutoff = now - RETRY_WINDOW_SECONDS
            recent_clients = self._recent_clients.get(endpoint, [])
            client_requests: dict[str, list] = collections.defaultdict(list)
            for (ts, ck, method) in recent_clients:
                if ts >= retry_cutoff:
                    client_requests[ck].append(ts)
            retry_count = sum(max(0, len(v) - 1) for v in client_requests.values())

            # Throughput
            throughput_rps = len(recent) / WINDOW_SECONDS

            # Avg payload
            payloads = [r.resp_size for r in recent if r.resp_size > 0]
            avg_payload = sum(payloads) / len(payloads) if payloads else 0.0

            return EndpointMetrics(
                endpoint=endpoint,
                timestamp=now,
                latency_ms=round(avg_latency, 2),
                error_rate=round(error_rate, 4),
                packet_loss=round(packet_loss, 4),
                retry_count=retry_count,
                throughput_rps=round(throughput_rps, 3),
                avg_payload=round(avg_payload, 1),
                sample_count=len(recent)
            )

    def get_all_endpoints(self) -> list[str]:
        with self._lock:
            return list(self._windows.keys())

    def compute_all(self) -> dict[str, EndpointMetrics]:
        endpoints = self.get_all_endpoints()
        result = {}
        for ep in endpoints:
            m = self.compute(ep)
            if m:
                result[ep] = m
        return result


# Global singleton
metric_engine = MetricEngine()
