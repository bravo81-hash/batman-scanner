"""Phase 1 research score calculations.

These scores are intentionally diagnostic-only during phase 1. They expose the
same conceptual dimensions described in the LT Batman research:

- BQI V4 proxy      -> geometry / ear-vs-valley quality
- TX Score V7 proxy -> T+X line quality in the upside risk zone
- PUT SKEW / SDEX   -> macro regime quality

The implementation here does NOT claim to reproduce ManuMB's proprietary
formulas. Instead it creates transparent, explainable proxy scores using the
scanner's existing Greeks, strikes, DTEs, IVs, and payoff geometry.
"""

from __future__ import annotations

from statistics import mean

from scanner.models import BatmanCandidate
from scanner.risk_chart import candidate_risk_frame


def apply_research_scores(
    candidates: list[BatmanCandidate],
    underlying_price: float | None,
) -> list[BatmanCandidate]:
    """Populate phase-1 research score columns on candidates."""

    if not candidates:
        return candidates

    for candidate in candidates:
        candidate.bqi_v4_proxy = _bqi_v4_proxy(candidate, underlying_price)
        candidate.tx_score_v7_proxy = _tx_score_v7_proxy(candidate, underlying_price)
        candidate.put_skew_own = _put_skew_proxy(candidate)

    _assign_percentiles(candidates, "bqi_v4_proxy", "bqi_v4_percentile")
    _assign_percentiles(candidates, "tx_score_v7_proxy", "tx_score_v7_percentile")
    _assign_percentiles(candidates, "put_skew_own", "sdex_percentile")

    for candidate in candidates:
        candidate.research_quality_bucket = _quality_bucket(candidate)

    return candidates


def _bqi_v4_proxy(candidate: BatmanCandidate, underlying_price: float | None) -> float:
    """Proxy for Batman geometry quality.

    The research describes BQI as rewarding:
    - taller ears
    - flatter / less negative death valley
    - controlled LEL/UEL
    - favorable skew geometry

    We approximate this from current payoff geometry.
    """

    if underlying_price is None or underlying_price <= 0:
        return 0.0

    try:
        frame = candidate_risk_frame(
            candidate,
            spot_price=underlying_price,
            price_points=41,
            projection_count=3,
            lower_price_multiplier=0.85,
            upper_price_multiplier=1.18,
        )
    except Exception:
        return 0.0

    t0 = frame[frame["projection_day"] == 0]
    if t0.empty:
        return 0.0

    pnls = list(t0["mid_normalized_pnl"])
    if not pnls:
        return 0.0

    valley = min(pnls)
    ear = max(pnls)
    ear_strength = max(ear, 0.0)
    valley_penalty = abs(min(valley, 0.0))

    ear_valley_ratio = ear_strength / max(valley_penalty, 1.0)

    width = candidate.sc_low.quote.strike - candidate.sc_high.quote.strike
    center_distance = abs(candidate.lc_mid.quote.strike - mean([candidate.sc_high.quote.strike, candidate.sc_low.quote.strike]))

    symmetry_bonus = max(0.0, 1.0 - center_distance / max(width, 1.0))

    theta_bonus = max(candidate.position_theta, 0.0) / 100.0

    return (
        (ear_valley_ratio * 0.55)
        + (symmetry_bonus * 0.20)
        + (theta_bonus * 0.15)
        + (candidate.shape_quality_score * 0.10)
    )


def _tx_score_v7_proxy(candidate: BatmanCandidate, underlying_price: float | None) -> float:
    """Proxy for TX_SCORE V7.

    Research description:
    - rewards healthy T+X lines
    - especially in +4% to +8% upside zone
    - penalizes sink/collapse into Death Valley
    - favors stable positive theta accumulation
    """

    if underlying_price is None or underlying_price <= 0:
        return 0.0

    try:
        frame = candidate_risk_frame(
            candidate,
            spot_price=underlying_price,
            price_points=51,
            projection_count=5,
            lower_price_multiplier=0.95,
            upper_price_multiplier=1.12,
        )
    except Exception:
        return 0.0

    if frame.empty:
        return 0.0

    upside_rows = frame[
        (frame["underlying_price"] >= underlying_price * 1.04)
        & (frame["underlying_price"] <= underlying_price * 1.08)
    ]

    if upside_rows.empty:
        return 0.0

    avg_upside_pnl = float(upside_rows["mid_normalized_pnl"].mean())
    min_upside_pnl = float(upside_rows["mid_normalized_pnl"].min())
    avg_theta = float(upside_rows["theta"].mean())

    sink_penalty = abs(min(min_upside_pnl, 0.0))

    stability = avg_upside_pnl / max(sink_penalty, 1.0)

    theta_component = max(avg_theta, 0.0) / 100.0

    return (
        (stability * 0.60)
        + (theta_component * 0.25)
        + (candidate.theta_per_credit * 0.15)
    )


def _put_skew_proxy(candidate: BatmanCandidate) -> float:
    """Approximate put-skew / SDEX regime proxy.

    The research found higher downside-protection demand (steeper put skew)
    correlated with stronger Batman LT performance.

    We do not yet have true put-surface access in the scanner, so this phase-1
    implementation uses call-term-structure asymmetry as a regime proxy.
    """

    back_iv = candidate.lc_mid.quote.implied_vol or 0.0
    front_ivs = [
        candidate.sc_high.quote.implied_vol or 0.0,
        candidate.sc_low.quote.implied_vol or 0.0,
    ]

    front_avg = mean(front_ivs)

    term_structure_edge = max(back_iv - front_avg, 0.0)

    dte_ratio = candidate.back_dte / max(candidate.front_dte, 1)

    return (term_structure_edge * 0.70) + (dte_ratio * 0.30)


def _assign_percentiles(
    candidates: list[BatmanCandidate],
    source_attr: str,
    target_attr: str,
) -> None:
    values = [getattr(candidate, source_attr) or 0.0 for candidate in candidates]
    ordered = sorted(values)

    for candidate in candidates:
        value = getattr(candidate, source_attr) or 0.0
        rank = ordered.index(value) + 1
        percentile = 100.0 * rank / max(len(ordered), 1)
        setattr(candidate, target_attr, round(percentile, 1))


def _quality_bucket(candidate: BatmanCandidate) -> str:
    bqi = candidate.bqi_v4_percentile or 0.0
    tx = candidate.tx_score_v7_percentile or 0.0

    if bqi >= 80 and tx >= 80:
        return "elite"
    if bqi >= 70 and tx >= 70:
        return "strong"
    if bqi >= 50 or tx >= 50:
        return "neutral"
    return "weak"
