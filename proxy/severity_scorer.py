"""
severity_scorer.py
------------------
Computes a unified 0–10 severity score from anomaly events and correlation data.
Also computes a short-horizon SLA breach probability (0–100%).
"""

import time
import math
from dataclasses import dataclass


# Metric weights for severity calculation
WEIGHTS = {
    "latency_ms":     0.35,
    "error_rate":     0.30,
    "packet_loss":    0.20,
    "throughput_rps": 0.10,
    "avg_payload":    0.05,
}

# Bonus multiplier for correlated multi-API anomalies
CORRELATION_MULTIPLIER = 0.5   # +50% severity per additional API involved (up to cap)
MAX_SEVERITY = 10.0


@dataclass
class SeverityReport:
    score: float                    # 0.0 – 10.0
    level: str                      # "normal" | "warning" | "critical"
    sla_breach_probability: float   # 0.0 – 100.0
    primary_metric: str             # Which metric is contributing most
    affected_api_count: int
    trend: str                      # "stable" | "rising" | "falling"
    description: str

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 2),
            "level": self.level,
            "sla_breach_probability": round(self.sla_breach_probability, 1),
            "primary_metric": self.primary_metric,
            "affected_api_count": self.affected_api_count,
            "trend": self.trend,
            "description": self.description,
        }


class SeverityScorer:
    def __init__(self):
        self._score_history: list[tuple[float, float]] = []  # (timestamp, score)

    def compute(
        self,
        anomaly_events: list,
        correlation_result=None,
        affected_api_count: int = 1
    ) -> SeverityReport:
        """
        Compute severity from a list of AnomalyEvent objects.
        """

        if not anomaly_events:
            report = SeverityReport(
                score=0.0,
                level="normal",
                sla_breach_probability=0.0,
                primary_metric="none",
                affected_api_count=0,
                trend=self._compute_trend(),
                description="All systems operating within normal parameters."
            )
            self._record(0.0)
            return report

        # Base score: weighted sum of per-metric z-scores
        metric_scores: dict[str, float] = {}
        for event in anomaly_events:
            metric = event.metric
            weight = WEIGHTS.get(metric, 0.1)
            contribution = min(10.0, abs(event.z_score) / 3.5 * 6.0) * weight
            # Take the max contribution per metric
            if metric not in metric_scores or contribution > metric_scores[metric]:
                metric_scores[metric] = contribution

        base_score = sum(metric_scores.values())

        # Correlation multiplier
        if correlation_result and affected_api_count > 1:
            extra = min(CORRELATION_MULTIPLIER * (affected_api_count - 1), 3.0)
            base_score *= (1 + extra * 0.3)

        score = min(MAX_SEVERITY, base_score)

        # Determine primary metric (highest contributor)
        primary_metric = max(metric_scores, key=metric_scores.get) if metric_scores else "unknown"

        # Determine level
        if score >= 7.0:
            level = "critical"
        elif score >= 4.0:
            level = "warning"
        else:
            level = "normal"

        # SLA breach probability — sigmoid function of score
        # Score 0 → ~2% probability, Score 7 → ~80%, Score 10 → ~97%
        sla_prob = 100.0 / (1.0 + math.exp(-1.2 * (score - 5.0)))

        trend = self._compute_trend()

        # Build description
        event_descs = [e.description for e in anomaly_events[:2]]
        description = f"Severity {round(score, 1)}/10 [{level.upper()}]. " + " | ".join(event_descs)

        self._record(score)

        return SeverityReport(
            score=round(score, 2),
            level=level,
            sla_breach_probability=round(sla_prob, 1),
            primary_metric=primary_metric,
            affected_api_count=affected_api_count,
            trend=trend,
            description=description,
        )

    def _record(self, score: float):
        self._score_history.append((time.time(), score))
        self._score_history = self._score_history[-50:]

    def _compute_trend(self) -> str:
        if len(self._score_history) < 5:
            return "stable"
        recent = [s for _, s in self._score_history[-5:]]
        earlier = [s for _, s in self._score_history[-10:-5]]
        if not earlier:
            return "stable"
        avg_recent = sum(recent) / len(recent)
        avg_earlier = sum(earlier) / len(earlier)
        delta = avg_recent - avg_earlier
        if delta > 0.5:
            return "rising"
        elif delta < -0.5:
            return "falling"
        return "stable"

    def get_current_score(self) -> float:
        if self._score_history:
            return self._score_history[-1][1]
        return 0.0

    def get_history(self) -> list[dict]:
        return [
            {"timestamp": t, "score": s}
            for t, s in self._score_history
        ]


# Global singleton
severity_scorer = SeverityScorer()
