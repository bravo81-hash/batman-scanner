"""Risk-chart calculations for selected Batman candidates.

The chart uses a Black-Scholes style approximation calibrated to current option
mid prices. It is intended for quick scanner triage before manual review in a
separate options analysis tool.
"""

from __future__ import annotations

from functools import lru_cache
from math import erf, exp, isclose, log, pi, sqrt

import pandas as pd

from scanner.models import BatmanCandidate, BatmanLeg


RISK_FREE_RATE = 0.0
DIVIDEND_YIELD = 0.0
CONTRACT_MULTIPLIER = 100


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _norm_pdf(value: float) -> float:
    return exp(-0.5 * value * value) / sqrt(2.0 * pi)


def black_scholes_call_price(
    underlying_price: float,
    strike: float,
    years_to_expiry: float,
    implied_vol: float,
    risk_free_rate: float = RISK_FREE_RATE,
    dividend_yield: float = DIVIDEND_YIELD,
) -> float:
    """Return an approximate European call price using Black-Scholes-Merton."""
    if underlying_price <= 0 or strike <= 0:
        return 0.0
    if years_to_expiry <= 0 or implied_vol <= 0:
        return max(underlying_price - strike, 0.0)

    sigma_sqrt_t = implied_vol * sqrt(years_to_expiry)
    if sigma_sqrt_t <= 0:
        return max(underlying_price - strike, 0.0)

    d1 = (
        log(underlying_price / strike)
        + (risk_free_rate - dividend_yield + 0.5 * implied_vol**2) * years_to_expiry
    ) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    discounted_spot = underlying_price * exp(-dividend_yield * years_to_expiry)
    discounted_strike = strike * exp(-risk_free_rate * years_to_expiry)
    return discounted_spot * _norm_cdf(d1) - discounted_strike * _norm_cdf(d2)


def black_scholes_call_greeks(
    underlying_price: float,
    strike: float,
    years_to_expiry: float,
    implied_vol: float,
    risk_free_rate: float = RISK_FREE_RATE,
    dividend_yield: float = DIVIDEND_YIELD,
) -> dict[str, float]:
    """Return per-contract call Greeks in option-price units."""
    if underlying_price <= 0 or strike <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    if years_to_expiry <= 0 or implied_vol <= 0:
        delta = 1.0 if underlying_price > strike else 0.0
        return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    sigma_sqrt_t = implied_vol * sqrt(years_to_expiry)
    d1 = (
        log(underlying_price / strike)
        + (risk_free_rate - dividend_yield + 0.5 * implied_vol**2) * years_to_expiry
    ) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    spot_discount = exp(-dividend_yield * years_to_expiry)
    strike_discount = exp(-risk_free_rate * years_to_expiry)

    delta = spot_discount * _norm_cdf(d1)
    gamma = spot_discount * _norm_pdf(d1) / (underlying_price * sigma_sqrt_t)
    theta = (
        -underlying_price * spot_discount * _norm_pdf(d1) * implied_vol / (2 * sqrt(years_to_expiry))
        - risk_free_rate * strike * strike_discount * _norm_cdf(d2)
        + dividend_yield * underlying_price * spot_discount * _norm_cdf(d1)
    ) / 365
    vega = underlying_price * spot_discount * _norm_pdf(d1) * sqrt(years_to_expiry) / 100
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


def implied_vol_from_call_price(
    underlying_price: float,
    strike: float,
    years_to_expiry: float,
    call_price: float,
    fallback_iv: float,
    risk_free_rate: float = RISK_FREE_RATE,
    dividend_yield: float = DIVIDEND_YIELD,
) -> float:
    """Find the IV that reproduces an observed call price in this model."""
    intrinsic = max(underlying_price - strike, 0.0)
    if underlying_price <= 0 or strike <= 0 or years_to_expiry <= 0 or call_price <= intrinsic:
        return fallback_iv

    low = 0.0001
    high = 5.0
    for _ in range(80):
        mid = (low + high) / 2
        model_price = black_scholes_call_price(
            underlying_price,
            strike,
            years_to_expiry,
            mid,
            risk_free_rate,
            dividend_yield,
        )
        if isclose(model_price, call_price, rel_tol=1e-8, abs_tol=1e-8):
            return mid
        if model_price < call_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def projection_days(horizon_dte: int, points: int = 5) -> list[int]:
    """Return projection days from T+0 through the selected horizon."""
    if points <= 1 or horizon_dte <= 0:
        return [0]
    return sorted(set(round(horizon_dte * index / (points - 1)) for index in range(points)))


def candidate_risk_frame(
    candidate: BatmanCandidate,
    spot_price: float,
    price_points: int = 101,
    projection_count: int = 5,
    lower_price_multiplier: float = 0.70,
    upper_price_multiplier: float = 1.60,
    projection_horizon: str = "front",
) -> pd.DataFrame:
    """Build PnL and Greek rows across prices and projection dates."""
    if spot_price <= 0:
        return pd.DataFrame()

    low_price = max(spot_price * lower_price_multiplier, 1.0)
    high_price = max(spot_price * upper_price_multiplier, low_price + 1.0)
    if price_points <= 1:
        prices = [spot_price]
    else:
        step = (high_price - low_price) / (price_points - 1)
        prices = [low_price + (step * index) for index in range(price_points)]

    horizon_dte = candidate.back_dte if projection_horizon == "back" else candidate.front_dte
    projections = projection_days(horizon_dte, projection_count)
    entry_mid_mark_value = _candidate_mark_value(candidate, spot_price, 0, spot_price)
    executable_entry_credit_value = candidate.entry_credit * CONTRACT_MULTIPLIER
    t0_executable_pnl = executable_entry_credit_value + entry_mid_mark_value

    rows: list[dict[str, float | str | int]] = []
    for elapsed in projections:
        for price in prices:
            mark_value = _candidate_mark_value(candidate, price, elapsed, spot_price)
            greeks = _candidate_greeks(candidate, price, elapsed, spot_price)
            mid_normalized_pnl = mark_value - entry_mid_mark_value
            executable_pnl = executable_entry_credit_value + mark_value
            rows.append(
                {
                    "underlying_price": price,
                    "projection_day": elapsed,
                    "projection_label": f"T+{elapsed}",
                    "pnl": mid_normalized_pnl,
                    "mid_normalized_pnl": mid_normalized_pnl,
                    "executable_pnl": executable_pnl,
                    "t0_executable_pnl": t0_executable_pnl,
                    "delta": greeks["delta"],
                    "gamma": greeks["gamma"],
                    "theta": greeks["theta"],
                    "vega": greeks["vega"],
                }
            )
    return pd.DataFrame(rows)


def _leg_starting_dte(candidate: BatmanCandidate, leg: BatmanLeg) -> int:
    return candidate.back_dte if leg.name == "LC_Mid" else candidate.front_dte


def _leg_years_to_expiry(candidate: BatmanCandidate, leg: BatmanLeg, elapsed_days: int) -> float:
    remaining_days = max(_leg_starting_dte(candidate, leg) - elapsed_days, 0)
    return remaining_days / 365


def _leg_iv(leg: BatmanLeg) -> float:
    return leg.quote.implied_vol or 0.20


@lru_cache(maxsize=4096)
def _calibrated_leg_iv(
    strike: float,
    mid: float,
    starting_years_to_expiry: float,
    fallback_iv: float,
    spot_price: float,
) -> float:
    return implied_vol_from_call_price(
        spot_price,
        strike,
        starting_years_to_expiry,
        mid,
        fallback_iv,
    )


def _leg_calibrated_iv(candidate: BatmanCandidate, leg: BatmanLeg, spot_price: float) -> float:
    fallback_iv = _leg_iv(leg)
    observed_mid = leg.quote.mid
    if observed_mid is None or observed_mid <= 0:
        return fallback_iv
    return _calibrated_leg_iv(
        leg.quote.strike,
        observed_mid,
        _leg_years_to_expiry(candidate, leg, 0),
        fallback_iv,
        spot_price,
    )


def _scenario_leg_price(
    candidate: BatmanCandidate,
    leg: BatmanLeg,
    underlying_price: float,
    elapsed_days: int,
    spot_price: float,
) -> float:
    """Return a scenario option price using IV calibrated to observed mid."""
    years_to_expiry = _leg_years_to_expiry(candidate, leg, elapsed_days)
    intrinsic = max(underlying_price - leg.quote.strike, 0.0)
    if years_to_expiry <= 0:
        return intrinsic

    scenario_price = black_scholes_call_price(
        underlying_price,
        leg.quote.strike,
        years_to_expiry,
        _leg_calibrated_iv(candidate, leg, spot_price),
    )
    return max(scenario_price, intrinsic, 0.0)


def _candidate_mark_value(
    candidate: BatmanCandidate,
    underlying_price: float,
    elapsed_days: int,
    spot_price: float,
) -> float:
    total = 0.0
    for leg in candidate.legs:
        price = _scenario_leg_price(candidate, leg, underlying_price, elapsed_days, spot_price)
        total += leg.signed_quantity * price * CONTRACT_MULTIPLIER
    return total


def _candidate_greeks(
    candidate: BatmanCandidate,
    underlying_price: float,
    elapsed_days: int,
    spot_price: float,
) -> dict[str, float]:
    totals = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for leg in candidate.legs:
        greeks = black_scholes_call_greeks(
            underlying_price,
            leg.quote.strike,
            _leg_years_to_expiry(candidate, leg, elapsed_days),
            _leg_calibrated_iv(candidate, leg, spot_price),
        )
        totals["delta"] += leg.signed_quantity * greeks["delta"] * CONTRACT_MULTIPLIER
        totals["gamma"] += leg.signed_quantity * greeks["gamma"] * CONTRACT_MULTIPLIER
        totals["theta"] += leg.signed_quantity * greeks["theta"] * CONTRACT_MULTIPLIER
        totals["vega"] += leg.signed_quantity * greeks["vega"] * CONTRACT_MULTIPLIER
    return totals
