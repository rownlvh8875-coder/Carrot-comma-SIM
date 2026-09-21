from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import html
import json
from pathlib import Path
import random

from .campaign_manifest import canonical_json
from .sealed_holdout_revalidator import HoldoutResult


@dataclass(frozen=True)
class RecommendationInputs:
  candidate_id: str | None
  holdout: HoldoutResult
  safety_pass: bool
  coverage_sufficient: bool
  display_name: str


@dataclass(frozen=True)
class RecommendationPolicy:
  min_routes: int
  bootstrap_samples: int
  confidence_level: float
  max_worst_route_degradation: float

  def __post_init__(self) -> None:
    if self.min_routes <= 0 or self.bootstrap_samples <= 0:
      raise ValueError("route and bootstrap counts must be positive")
    if not 0.0 < self.confidence_level < 1.0:
      raise ValueError("confidence_level must be in (0,1)")


@dataclass(frozen=True)
class RecommendationReport:
  state: str
  candidate_id: str | None
  display_name: str
  route_count: int
  mean_delta: float | None
  confidence_interval: tuple[float, float] | None
  worst_route_delta: float | None
  reasons: tuple[str, ...]
  deployment_authorized: bool = False
  real_vehicle_write: bool = False

  def to_artifact(self) -> dict[str, object]:
    return {
      "schema_version": 1,
      "state": self.state,
      "candidate_id": self.candidate_id,
      "display_name": self.display_name,
      "route_count": self.route_count,
      "mean_delta": self.mean_delta,
      "confidence_interval": self.confidence_interval,
      "worst_route_delta": self.worst_route_delta,
      "reasons": self.reasons,
      "deployment_authorized": self.deployment_authorized,
      "real_vehicle_write": self.real_vehicle_write,
    }


def _bootstrap(values: tuple[float, ...], samples: int, confidence: float, seed_text: str) -> tuple[float, float]:
  rng = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16))
  means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(samples))
  tail = (1.0 - confidence) / 2.0
  lower = means[min(len(means) - 1, int(tail * len(means)))]
  upper = means[min(len(means) - 1, int((1.0 - tail) * len(means)))]
  return lower, upper


def build_recommendation(inputs: RecommendationInputs, policy: RecommendationPolicy) -> RecommendationReport:
  values = tuple(inputs.holdout.route_deltas[route] for route in sorted(inputs.holdout.route_deltas))
  reasons: list[str] = []
  interval = None
  mean = None
  if values:
    mean = sum(values) / len(values)
    interval = _bootstrap(values, policy.bootstrap_samples, policy.confidence_level,
                          f"{inputs.holdout.receipt_hash}|{inputs.candidate_id}")
  if not inputs.coverage_sufficient or len(values) < policy.min_routes:
    state = "INSUFFICIENT_EVIDENCE"
    reasons.append("COVERAGE_OR_POWER")
  elif not inputs.candidate_id or not inputs.safety_pass:
    state = "RETAIN_CURRENT"
    reasons.append("NO_SAFE_CANDIDATE")
  elif inputs.holdout.worst_route_delta is None or inputs.holdout.worst_route_delta < policy.max_worst_route_degradation:
    state = "RETAIN_CURRENT"
    reasons.append("WORST_ROUTE_REGRESSION")
  elif interval is None or interval[0] <= 0.0:
    state = "RETAIN_CURRENT"
    reasons.append("BENEFIT_UNRESOLVED")
  else:
    state = "CONDITIONAL_CANDIDATE"
    reasons.append("SIMULATION_AND_HOLDOUT_GATES_PASSED")
  return RecommendationReport(state, inputs.candidate_id, inputs.display_name, len(values), mean, interval,
                              inputs.holdout.worst_route_delta, tuple(reasons))


def write_report_bundle(report: RecommendationReport, directory: str | Path) -> dict[str, Path]:
  destination = Path(directory)
  destination.mkdir(parents=True, exist_ok=True)
  json_path = destination / "recommendation.json"
  csv_path = destination / "recommendation.csv"
  html_path = destination / "report.html"
  json_path.write_text(canonical_json(report.to_artifact()) + "\n", encoding="utf-8")
  with csv_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(("state", "candidate_id", "route_count", "mean_delta", "ci_lower", "ci_upper",
                     "worst_route_delta", "deployment_authorized", "real_vehicle_write"))
    interval = report.confidence_interval or ("", "")
    writer.writerow((report.state, report.candidate_id or "", report.route_count, report.mean_delta,
                     interval[0], interval[1], report.worst_route_delta, False, False))
  safe_name = html.escape(report.display_name)
  html_path.write_text(
    "<!doctype html><meta charset='utf-8'><title>Carrot recommendation</title>"
    f"<h1>{html.escape(report.state)}</h1><p>{safe_name}</p>"
    f"<p>Routes: {report.route_count}</p><p>Deployment authorized: false</p>",
    encoding="utf-8",
  )
  return {"json": json_path, "csv": csv_path, "html": html_path}
