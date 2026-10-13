"""
correlator.py
-------------
Cross-API anomaly correlation using NetworkX dependency graph.

The dependency graph encodes which APIs call which other APIs.
When an anomaly fires on a "root" API, this module checks if
dependent APIs are also showing anomalies within a time window —
if so, it marks them as correlated and identifies the likely root cause.
"""

import time
import threading
import networkx as nx
from dataclasses import dataclass


# Time window within which anomalies on different APIs are considered correlated
CORRELATION_WINDOW_SECONDS = 5


@dataclass
class CorrelationResult:
    root_cause: str             # Most likely root cause endpoint
    affected_apis: list[str]    # All APIs involved
    propagation_path: list[str] # How the fault propagated
    confidence: float           # 0.0 – 1.0
    description: str


class Correlator:
    def __init__(self):
        self._lock = threading.Lock()

        # Build the API dependency graph
        # Edge A → B means "B calls A" (B depends on A)
        # So if A has issues, B will be affected
        self._graph = nx.DiGraph()
        self._graph.add_nodes_from([
            "/auth",
            "/payments",
            "/inventory",
        ])
        # Payments depends on Auth
        self._graph.add_edge("/auth", "/payments", weight=1.0)
        # Inventory depends on Auth
        self._graph.add_edge("/auth", "/inventory", weight=1.0)

        # Recent anomaly timestamps per endpoint
        self._anomaly_times: dict[str, list[float]] = {}

    def _normalize_endpoint(self, endpoint: str) -> str:
        """Map full endpoint paths to graph node names."""
        if "auth" in endpoint:
            return "/auth"
        elif "payment" in endpoint:
            return "/payments"
        elif "inventory" in endpoint:
            return "/inventory"
        return endpoint

    def record_anomaly(self, endpoint: str, timestamp: float = None):
        """Record that an anomaly occurred on an endpoint."""
        node = self._normalize_endpoint(endpoint)
        with self._lock:
            if node not in self._anomaly_times:
                self._anomaly_times[node] = []
            self._anomaly_times[node].append(timestamp or time.time())
            # Keep last 20 anomaly times per endpoint
            self._anomaly_times[node] = self._anomaly_times[node][-20:]

    def correlate(self, endpoint: str) -> CorrelationResult | None:
        """
        Given a newly detected anomaly on `endpoint`, check if other APIs
        are also showing anomalies within the correlation window.
        Returns a CorrelationResult if correlation found, else None.
        """
        node = self._normalize_endpoint(endpoint)
        now = time.time()
        cutoff = now - CORRELATION_WINDOW_SECONDS

        with self._lock:
            # Find all APIs with recent anomalies
            recently_anomalous = set()
            for api, times in self._anomaly_times.items():
                if any(t >= cutoff for t in times):
                    recently_anomalous.add(api)

            if len(recently_anomalous) < 2:
                return None  # Need at least 2 APIs to correlate

            # Find the most likely root cause:
            # The root cause is the anomalous node that has the most
            # downstream dependents also showing anomalies.
            best_root = None
            best_score = 0
            best_affected = []
            best_path = []

            for candidate in recently_anomalous:
                # Get all descendants of this candidate in the graph
                try:
                    descendants = nx.descendants(self._graph, candidate)
                except Exception:
                    descendants = set()

                # How many of the anomalous APIs are descendants of this candidate?
                affected = [d for d in descendants if d in recently_anomalous]
                score = len(affected)

                if score > best_score:
                    best_score = score
                    best_root = candidate
                    best_affected = affected

            if not best_root or best_score == 0:
                # No clear propagation — still report co-occurring anomalies
                affected_list = list(recently_anomalous)
                return CorrelationResult(
                    root_cause=node,
                    affected_apis=affected_list,
                    propagation_path=affected_list,
                    confidence=0.4,
                    description=(
                        f"Co-occurring anomalies detected across: {', '.join(affected_list)}. "
                        f"No clear propagation path found."
                    )
                )

            # Build propagation path
            path = [best_root] + best_affected
            confidence = min(0.95, 0.5 + best_score * 0.2)
            all_affected = list(recently_anomalous)

            return CorrelationResult(
                root_cause=best_root,
                affected_apis=all_affected,
                propagation_path=path,
                confidence=round(confidence, 2),
                description=(
                    f"Root cause identified: {best_root}. "
                    f"Anomaly propagated to: {', '.join(best_affected)}. "
                    f"Confidence: {round(confidence * 100)}%."
                )
            )

    def get_graph_data(self) -> dict:
        """Returns graph structure for dashboard visualization."""
        with self._lock:
            now = time.time()
            cutoff = now - CORRELATION_WINDOW_SECONDS

            nodes = []
            for node in self._graph.nodes():
                times = self._anomaly_times.get(node, [])
                is_anomalous = any(t >= cutoff for t in times)
                nodes.append({
                    "id": node,
                    "label": node.strip("/").capitalize(),
                    "status": "anomalous" if is_anomalous else "healthy",
                    "anomaly_count": len([t for t in times if t >= cutoff]),
                })

            edges = []
            for src, dst, data in self._graph.edges(data=True):
                edges.append({
                    "source": src,
                    "target": dst,
                    "weight": data.get("weight", 1.0),
                })

            return {"nodes": nodes, "edges": edges}


# Global singleton
correlator = Correlator()
