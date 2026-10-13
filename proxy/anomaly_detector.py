"""
anomaly_detector.py
-------------------
Two-layer anomaly detection:
  Layer 1 — Z-score per metric (fast, explainable, fires early)
  Layer 2 — Isolation Forest (multivariate, catches subtle multi-metric anomalies)

Only runs after the baseline is marked ready (MIN_SAMPLES collected).
"""

import time
import threading
import numpy as np
from dataclasses import dataclass
from typing import Optional
from sklearn.ensemble import IsolationForest
from baseline_learner import baseline_learner


# Z-score thresholds
Z_WARN = 1.8
Z_CRITICAL = 2.5

# Isolation Forest — retrain every N observations
IF_MIN_SAMPLES = 40
IF_RETRAIN_EVERY = 20


@dataclass
class AnomalyEvent:
    timestamp: float
    endpoint: str
    anomaly_type: str          # "latency_spike" | "error_surge" | "packet_loss" | "multivariate" | "throughput_drop"
    severity: float            # 0.0 – 10.0
    z_score: float
    metric: str
    metric_value: float
    baseline_value: float
    level: str                 # "warning" | "critical"
    description: str
    correlated_apis: list[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "endpoint": self.endpoint,
            "anomaly_type": self.anomaly_type,
            "severity": round(self.severity, 2),
            "z_score": round(self.z_score, 2),
            "metric": self.metric,
            "metric_value": round(self.metric_value, 3),
            "baseline_value": round(self.baseline_value, 3),
            "level": self.level,
            "description": self.description,
            "correlated_apis": self.correlated_apis or [],
        }


class AnomalyDetector:
    def __init__(self):
        self._lock = threading.Lock()
        # Per-endpoint history for Isolation Forest
        self._if_data: dict[str, list] = {}
        self._if_models: dict[str, IsolationForest] = {}
        self._if_counts: dict[str, int] = {}
        # Recent anomalies cache
        self._recent: list[AnomalyEvent] = []

    def _check_z_score(self, endpoint: str, metrics: dict) -> list[AnomalyEvent]:
        """Layer 1: Z-score check per metric."""
        events = []
        now = time.time()

        checks = [
            ("latency_ms",      "latency_spike",    "Latency spike detected"),
            ("error_rate",      "error_surge",      "Error rate surge"),
            ("packet_loss",     "packet_loss",      "Packet loss detected"),
            ("throughput_rps",  "throughput_drop",  "Throughput anomaly"),
            ("avg_payload",     "payload_anomaly",  "Payload size anomaly"),
        ]

        for metric, anomaly_type, desc_prefix in checks:
            value = metrics.get(metric)
            if value is None:
                continue

            state = baseline_learner.get_baseline(endpoint, metric)
            if not state or not state.is_ready:
                continue

            z = state.z_score(value)
            abs_z = abs(z)

            if abs_z < Z_WARN:
                continue

            level = "critical" if abs_z >= Z_CRITICAL else "warning"

            # Compute severity contribution from this metric
            severity = min(10.0, (abs_z / Z_CRITICAL) * 6.0)

            direction = "above" if z > 0 else "below"
            description = (
                f"{desc_prefix} on {endpoint}: "
                f"{metric}={round(value, 3)} is {round(abs_z, 1)}σ {direction} baseline "
                f"(baseline={round(state.ewma, 3)}, band=[{round(state.lower_band,1)}, {round(state.upper_band,1)}])"
            )

            events.append(AnomalyEvent(
                timestamp=now,
                endpoint=endpoint,
                anomaly_type=anomaly_type,
                severity=severity,
                z_score=z,
                metric=metric,
                metric_value=value,
                baseline_value=state.ewma,
                level=level,
                description=description,
            ))

        return events

    def _check_isolation_forest(self, endpoint: str, metrics: dict) -> Optional[AnomalyEvent]:
        """Layer 2: Isolation Forest multivariate anomaly detection."""
        features = [
            metrics.get("latency_ms", 0),
            metrics.get("error_rate", 0),
            metrics.get("packet_loss", 0),
            metrics.get("throughput_rps", 0),
            metrics.get("avg_payload", 0),
        ]

        with self._lock:
            if endpoint not in self._if_data:
                self._if_data[endpoint] = []
                self._if_counts[endpoint] = 0

            self._if_data[endpoint].append(features)
            self._if_counts[endpoint] += 1

            n = len(self._if_data[endpoint])

            # Need minimum samples to train
            if n < IF_MIN_SAMPLES:
                return None

            # Retrain periodically
            if self._if_counts[endpoint] % IF_RETRAIN_EVERY == 0 or endpoint not in self._if_models:
                data = np.array(self._if_data[endpoint][-200:])  # Last 200 points
                model = IsolationForest(
                    contamination=0.05,
                    n_estimators=100,
                    random_state=42
                )
                model.fit(data)
                self._if_models[endpoint] = model

            model = self._if_models.get(endpoint)
            if not model:
                return None

            score = model.decision_function([features])[0]
            prediction = model.predict([features])[0]

            # prediction == -1 means anomaly
            if prediction == -1:
                # Severity based on how anomalous the score is
                severity = min(10.0, max(0.0, (-score) * 8.0))
                return AnomalyEvent(
                    timestamp=time.time(),
                    endpoint=endpoint,
                    anomaly_type="multivariate",
                    severity=severity,
                    z_score=score,
                    metric="multivariate",
                    metric_value=score,
                    baseline_value=0.0,
                    level="critical" if severity >= 6 else "warning",
                    description=(
                        f"Multivariate anomaly on {endpoint}: "
                        f"Isolation Forest score={round(score, 3)} — "
                        f"unusual combination of metrics detected."
                    )
                )

        return None

    def detect(self, endpoint: str, metrics: dict) -> list[AnomalyEvent]:
        """
        Run all detection layers. Returns list of anomaly events.
        Empty list = no anomaly.
        """
        if not baseline_learner.is_ready(endpoint):
            return []

        events = []

        # Layer 1: Z-score
        z_events = self._check_z_score(endpoint, metrics)
        events.extend(z_events)

        # Layer 2: Isolation Forest
        if_event = self._check_isolation_forest(endpoint, metrics)
        if if_event:
            # Only add if not already flagged by z-score (avoid duplicate high severity)
            if not z_events or if_event.severity > max(e.severity for e in z_events):
                events.append(if_event)

        # Store recent
        with self._lock:
            self._recent.extend(events)
            self._recent = self._recent[-100:]  # Keep last 100

        return events

    def get_recent(self, limit=20) -> list[dict]:
        with self._lock:
            return [e.to_dict() for e in self._recent[-limit:]]


# Global singleton
anomaly_detector = AnomalyDetector()
