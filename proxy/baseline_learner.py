"""
baseline_learner.py
-------------------
Learns adaptive behavioral baselines per API endpoint using EWMA
(Exponentially Weighted Moving Average). Maintains upper/lower bands
using rolling standard deviation.

Baseline is only considered "ready" after MIN_SAMPLES observations —
this simulates the real-world concept of learning normal behaviour
at launch before anomaly detection kicks in.
"""

import time
import math
import threading
from dataclasses import dataclass, field
from typing import Optional


# How many samples before the baseline is considered "learned"
MIN_SAMPLES = 30

# EWMA smoothing factor — lower = slower to adapt, smoother baseline
ALPHA = 0.15

# Band width multiplier (how many std-devs define normal range)
BAND_WIDTH = 2.0


@dataclass
class BaselineState:
    endpoint: str
    metric: str

    # EWMA state
    ewma: float = 0.0
    ewma_sq: float = 0.0       # EWMA of squared values (for variance)
    std: float = 0.0

    sample_count: int = 0
    last_updated: float = 0.0
    is_ready: bool = False     # True once MIN_SAMPLES collected

    @property
    def upper_band(self) -> float:
        return self.ewma + BAND_WIDTH * self.std

    @property
    def lower_band(self) -> float:
        return max(0.0, self.ewma - BAND_WIDTH * self.std)

    def update(self, value: float):
        """Feed one new observation into the EWMA."""
        if self.sample_count == 0:
            # Bootstrap: set initial value
            self.ewma = value
            self.ewma_sq = value ** 2
        else:
            self.ewma = ALPHA * value + (1 - ALPHA) * self.ewma
            self.ewma_sq = ALPHA * (value ** 2) + (1 - ALPHA) * self.ewma_sq

        variance = max(0.0, self.ewma_sq - self.ewma ** 2)
        self.std = math.sqrt(variance)

        self.sample_count += 1
        self.last_updated = time.time()

        if self.sample_count >= MIN_SAMPLES:
            self.is_ready = True

    def z_score(self, value: float) -> float:
        """Compute z-score of a value against current baseline."""
        if self.std < 0.001:
            return 0.0
        return (value - self.ewma) / self.std

    def to_dict(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "metric": self.metric,
            "baseline": round(self.ewma, 3),
            "std": round(self.std, 3),
            "upper_band": round(self.upper_band, 3),
            "lower_band": round(self.lower_band, 3),
            "sample_count": self.sample_count,
            "is_ready": self.is_ready,
            "last_updated": self.last_updated,
        }


class BaselineLearner:
    """
    Manages baseline states for all (endpoint, metric) combinations.
    Metrics tracked: latency_ms, error_rate, packet_loss, throughput_rps, avg_payload
    """

    TRACKED_METRICS = ["latency_ms", "error_rate", "packet_loss", "throughput_rps", "avg_payload"]

    def __init__(self):
        self._lock = threading.Lock()
        # Key: (endpoint, metric) → BaselineState
        self._states: dict[tuple, BaselineState] = {}

    def _get_or_create(self, endpoint: str, metric: str) -> BaselineState:
        key = (endpoint, metric)
        if key not in self._states:
            self._states[key] = BaselineState(endpoint=endpoint, metric=metric)
        return self._states[key]

    def update(self, endpoint: str, metrics: dict):
        """
        Feed new metric observations for an endpoint.
        metrics: dict with keys matching TRACKED_METRICS
        """
        with self._lock:
            for metric in self.TRACKED_METRICS:
                value = metrics.get(metric)
                if value is not None:
                    state = self._get_or_create(endpoint, metric)
                    state.update(float(value))

    def get_baseline(self, endpoint: str, metric: str) -> Optional[BaselineState]:
        with self._lock:
            return self._states.get((endpoint, metric))

    def get_all_baselines(self, endpoint: str) -> dict[str, dict]:
        """Return all baseline states for an endpoint as dicts."""
        with self._lock:
            result = {}
            for metric in self.TRACKED_METRICS:
                state = self._states.get((endpoint, metric))
                if state:
                    result[metric] = state.to_dict()
            return result

    def is_ready(self, endpoint: str) -> bool:
        """Returns True if the latency baseline for this endpoint is learned."""
        with self._lock:
            state = self._states.get((endpoint, "latency_ms"))
            return state.is_ready if state else False

    def get_z_score(self, endpoint: str, metric: str, value: float) -> float:
        """Get z-score for a value against the current baseline."""
        with self._lock:
            state = self._states.get((endpoint, metric))
            if state and state.is_ready:
                return state.z_score(value)
            return 0.0

    def get_summary(self) -> dict:
        """Full summary of all baselines — used by dashboard."""
        with self._lock:
            summary = {}
            for (endpoint, metric), state in self._states.items():
                if endpoint not in summary:
                    summary[endpoint] = {
                        "endpoint": endpoint,
                        "is_ready": False,
                        "metrics": {}
                    }
                summary[endpoint]["metrics"][metric] = state.to_dict()
                if metric == "latency_ms":
                    summary[endpoint]["is_ready"] = state.is_ready
            return summary


# Global singleton
baseline_learner = BaselineLearner()
