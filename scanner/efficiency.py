"""Candidate efficiency metrics for pre-entry selection.

These metrics are scanner-only decision aids. They do not manage open trades,
size positions, or place orders. The goal is to help identify candidates that
are worth modelling in OptionNet Explorer.
"""

from __future__ import annotations

from scanner.models import BatmanCandidate


EPSILON = 1e-9


def candidate_efficiency_metrics(candidate: BatmanCandidate) -> dict[str, float]:
    """Return deterministic efficiency metrics for one Batman candidate.

    Metrics intentionally use values already calculated by the scanner so they
    do not require extra market-data calls.
    """
    spread_risk = max(candidate.average_spread_ratio, EPSILON)
    credit = max(candidate.entry_credit, EPSILON)
    abs_delta = max(abs(candidate.position_delta), EPSILON)
    theta = candidate.position_theta
    theta_floor = max(theta, 0.0)

    return {
        "theta_per_credit": theta / credit,
        "positive_theta_per_credit": theta_floor / credit,
        "credit_per_spread_risk": candidate.entry_credit / spread_risk,
        "theta_per_spread_risk": theta / spread_risk,
        "positive_theta_per_spread_risk": theta_floor / spread_risk,
        "theta_per_abs_delta": theta / abs_delta,
        "credit_per_abs_delta": candidate.entry_credit / abs_delta,
        "liquidity_adjusted_credit": candidate.entry_credit * candidate.liquidity_score,
        "liquidity_adjusted_theta": theta * candidate.liquidity_score,
        "shape_adjusted_score": candidate.score * candidate.shape_quality_score,
    }


def apply_candidate_efficiency(candidate: BatmanCandidate) -> BatmanCandidate:
    """Attach key efficiency metrics directly to a candidate."""
    metrics = candidate_efficiency_metrics(candidate)
    candidate.theta_per_credit = metrics["theta_per_credit"]
    candidate.positive_theta_per_credit = metrics["positive_theta_per_credit"]
    candidate.credit_per_spread_risk = metrics["credit_per_spread_risk"]
    candidate.theta_per_spread_risk = metrics["theta_per_spread_risk"]
    candidate.theta_per_abs_delta = metrics["theta_per_abs_delta"]
    candidate.liquidity_adjusted_credit = metrics["liquidity_adjusted_credit"]
    candidate.liquidity_adjusted_theta = metrics["liquidity_adjusted_theta"]
    candidate.shape_adjusted_score = metrics["shape_adjusted_score"]
    return candidate


def efficiency_rows(candidates: list[BatmanCandidate]) -> list[dict[str, float | int | str]]:
    """Return UI/export friendly efficiency rows for ranked candidates."""
    rows: list[dict[str, float | int | str]] = []
    for candidate in candidates:
        metrics = candidate_efficiency_metrics(candidate)
        rows.append(
            {
                "rank": candidate.rank,
                "front_expiry": candidate.front_expiry,
                "back_expiry": candidate.back_expiry,
                "front_dte": candidate.front_dte,
                "back_dte": candidate.back_dte,
                "score": round(candidate.score, 4),
                "credit": round(candidate.entry_credit, 2),
                "position_delta": round(candidate.position_delta, 2),
                "position_theta": round(candidate.position_theta, 2),
                "liquidity_score": round(candidate.liquidity_score, 4),
                "shape_quality_score": round(candidate.shape_quality_score, 4),
                "theta_per_credit": round(metrics["theta_per_credit"], 4),
                "positive_theta_per_credit": round(metrics["positive_theta_per_credit"], 4),
                "credit_per_spread_risk": round(metrics["credit_per_spread_risk"], 2),
                "theta_per_spread_risk": round(metrics["theta_per_spread_risk"], 2),
                "theta_per_abs_delta": round(metrics["theta_per_abs_delta"], 4),
                "liquidity_adjusted_credit": round(metrics["liquidity_adjusted_credit"], 2),
                "liquidity_adjusted_theta": round(metrics["liquidity_adjusted_theta"], 2),
                "shape_adjusted_score": round(metrics["shape_adjusted_score"], 4),
            }
        )
    return rows
