"""Estimated BQI v4 component calculations for LT Batman candidates.

This implements the formula structure supplied in the BQI v4 slides:

- 45% Batman Forward Factor
- 34% Temporal Greeks
- 10% Stats / heuristics
- 5% alternate vertical/horizontal skew metric
- 6% payoff geometry

The raw ingredients are computed from TWS option IVs/Greeks and the scanner's
risk-chart model. The only deliberately estimated component is the 10% stats /
heuristics block because the presenter has not supplied its exact sub-formula.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean

from scanner.models import BatmanCandidate
from scanner.risk_chart import CONTRACT_MULTIPLIER, candidate_risk_frame


@dataclass(frozen=True)
class BQIV4Components:
    bqi_raw: float
    bff: float
    temporal_greeks: float
    stats_heuristic: float
    alternate_skew: float
    payoff_geometry: float
    left_ear_height: float
    right_ear_height: float
    ear_score: float
    pnl_vod: float
    evr: float


def calculate_bqi_v4_components(candidate: BatmanCandidate, underlying_price: float | None) -> BQIV4Components:
    """Calculate un-normalized BQI v4 estimated components."""

    bff = batman_forward_factor(candidate)
    temporal = temporal_greeks_score(candidate)
    stats = stats_heuristic_score(candidate)
    alt_skew = alternate_skew_score(candidate)
    geometry, left_ear, right_ear, ear_score, pnl_vod, evr = payoff_geometry_score(candidate, underlying_price)

    raw = (0.45 * bff) + (0.34 * temporal) + (0.10 * stats) + (0.05 * alt_skew) + (0.06 * geometry)

    return BQIV4Components(
        bqi_raw=raw,
        bff=bff,
        temporal_greeks=temporal,
        stats_heuristic=stats,
        alternate_skew=alt_skew,
        payoff_geometry=geometry,
        left_ear_height=left_ear,
        right_ear_height=right_ear,
        ear_score=ear_score,
        pnl_vod=pnl_vod,
        evr=evr,
    )


def batman_forward_factor(candidate: BatmanCandidate) -> float:
    """Return BFF = IV1 / IV_fwd - 1 using Batman leg IVs.

    IV1(front) = average(IV_K1, IV_K3) for both front-expiry wings.
    IV2(back) = IV_K2 for the back-expiry body.
    """

    iv_k1 = candidate.sc_high.quote.implied_vol
    iv_k2 = candidate.lc_mid.quote.implied_vol
    iv_k3 = candidate.sc_low.quote.implied_vol
    if not iv_k1 or not iv_k2 or not iv_k3:
        return 0.0

    iv1 = mean([float(iv_k1), float(iv_k3)])
    iv2 = float(iv_k2)
    t1 = max(candidate.front_dte / 365.0, 1e-9)
    t2 = max(candidate.back_dte / 365.0, t1 + 1e-9)
    if t2 <= t1:
        return 0.0

    forward_variance = ((iv2**2) * t2 - (iv1**2) * t1) / (t2 - t1)
    if forward_variance <= 0:
        return 0.0

    iv_forward = sqrt(forward_variance)
    if iv_forward <= 0:
        return 0.0
    return (iv1 / iv_forward) - 1.0


def temporal_greeks_score(candidate: BatmanCandidate) -> float:
    """Current BQI v4 temporal-greek input: theta of the back long calls.

    IBKR theta is usually negative for long options. Higher is better, so this
    returns the signed total theta of the two long K2 calls without inversion.
    """

    return 2.0 * float(candidate.lc_mid.quote.theta or 0.0)


def stats_heuristic_score(candidate: BatmanCandidate) -> float:
    """Estimated 10% stats/heuristics block.

    Exact sub-formula still needed from the presenter. Until then, use already
    transparent scanner diagnostics: DTE anchor, liquidity, shape and delta fit.
    """

    return mean(
        [
            float(candidate.dte_anchor_score),
            float(candidate.liquidity_score),
            float(candidate.shape_quality_score),
            float(candidate.delta_score or 0.0),
        ]
    )


def alternate_skew_score(candidate: BatmanCandidate) -> float:
    """Alternate vertical/horizontal skew measurement: IV_K1 / IV_K2."""

    iv_k1 = candidate.sc_high.quote.implied_vol
    iv_k2 = candidate.lc_mid.quote.implied_vol
    if not iv_k1 or not iv_k2:
        return 0.0
    return float(iv_k1) / max(float(iv_k2), 1e-9)


def payoff_geometry_score(
    candidate: BatmanCandidate,
    underlying_price: float | None,
) -> tuple[float, float, float, float, float, float]:
    """Return geometry score and components from T+0 payoff.

    Ear heights are converted from risk-graph dollars to absolute SPX points by
    dividing by the SPX contract multiplier, as described in the slide.
    """

    if underlying_price is None or underlying_price <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    try:
        frame = candidate_risk_frame(
            candidate,
            spot_price=underlying_price,
            price_points=121,
            projection_count=1,
            lower_price_multiplier=0.80,
            upper_price_multiplier=1.25,
        )
    except Exception:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    if frame.empty:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    t0 = frame[frame["projection_day"] == 0]
    if t0.empty:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    body_strike = candidate.lc_mid.quote.strike
    left_rows = t0[t0["underlying_price"] <= body_strike]
    right_rows = t0[t0["underlying_price"] >= body_strike]
    valley_rows = t0[
        (t0["underlying_price"] >= candidate.sc_high.quote.strike)
        & (t0["underlying_price"] <= candidate.sc_low.quote.strike)
    ]

    if left_rows.empty:
        left_rows = t0
    if right_rows.empty:
        right_rows = t0
    if valley_rows.empty:
        valley_rows = t0

    left_ear = max(float(left_rows["mid_normalized_pnl"].max()) / CONTRACT_MULTIPLIER, 0.0)
    right_ear = max(float(right_rows["mid_normalized_pnl"].max()) / CONTRACT_MULTIPLIER, 0.0)
    pnl_vod = float(valley_rows["mid_normalized_pnl"].min()) / CONTRACT_MULTIPLIER

    ear_score = sqrt(max(left_ear, 0.0) * max(right_ear, 0.0))
    evr = ear_score / (ear_score + max(-pnl_vod, 0.0)) if ear_score > 0 else 0.0

    return ear_score, left_ear, right_ear, ear_score, pnl_vod, evr
