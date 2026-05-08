"""Risk-chart calculations for selected Batman candidates.

These functions use a simple Black-Scholes approximation. They are for scanner
visualisation only and are not a substitute for final OptionNet Explorer checks.
"""

from __future__ import annotations

from math import erf, exp, log, pi, sqrt

import pandas as pd

from scanner.models import BatmanCandidate, BatmanLeg


RISK_FREE_RATE = 0.0
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
) -> float:
    """Return an approximate European call price."""
    if years_to_expiry <= 0 or implied_vol <= 0:
        return max(underlying_price - strike, 0.0)

    sigma_sqrt_t = implied_vol * sqrt(years_to_expiry)
    if sigma_sqrt_t <= 0:
        return max(underlying_price - strike, 0.0)

    d1 = (log(underlying_price / strike) + (risk_free_rate + 0.5 * implied_vol**2) * years_to_expiry) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    return underlying_price * _norm_cdf(d1) - strike * exp(-risk_free_rate * years_to_expiry) * _norm_cdf(d2)


def black_scholes_call_greeks(
    underlying_price: float,
    strike: float,
    years_to_expiry: float,
    implied_vol: float,
    risk_free_rate: float = RISK_FREE_RATE,
) -> dict[str, float]:
    """Return approximate per-contract call Greeks in option-price units."""
    if years_to_expiry <= 0 or implied_vol <= 0:
        delta = 1.0 if underlying_price > strike else 0.0
        return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    sigma_sqrt_t = implied_vol * sqrt(years_to_expiry)
    d1 = (log(underlying_price / strike) + (risk_free_rate + 0.5 * implied_vol**2) * years_to_expiry) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    delta = _norm_cdf(d1)
    gamma = _norm_pdf(d1) / (underlying_price * sigma_sqrt_t)
    theta = (
        -(underlying_price * _norm_pdf(d1) * implied_vol) / (2 * sqrt(years_to_expiry))
        - risk_free_rate * strike * exp(-risk_free_rate * years_to_expiry) * _norm_cdf(d2)
    ) / 365
    vega = underlying_price * _norm_pdf(d1) * sqrt(years_to_expiry) / 100
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


def projection_days(final_dte: int, points: int = 5) -> list[int]:
    """Return evenly spaced projection days from T+0 through final expiry."""
    if points <= 1:
        return [0]
    if final_dte <= 0:
        return [0]
    return [round(final_dte * index / (points - 1)) for index in range(points)]


def candidate_risk_frame(
    candidate: BatmanCandidate,
    spot_price: float,
    price_points: int = 101,
    projection_count: int = 5,
) -> pd.DataFrame:
    """Build PnL and Greek rows across prices and projection dates."""
    low_price = max(spot_price * 0.70, 1.0)
    high_price = spot_price * 1.30
    if price_points <= 1:
        prices = [spot_price]
    else:
        step = (high_price - low_price) / (price_points - 1)
        prices = [low_price + (step * index) for index in range(price_points)]

    final_dte = max(candidate.front_dte, candidate.back_dte)
    projections = projection_days(final_dte, projection_count)
    opening_value = _candidate_mark_value(candidate, spot_price, elapsed_days=0)
    rows: list[dict[str, float | str | int]] = []

    for elapsed in projections:
        for price in prices:
            mark_value = _candidate_mark_value(candidate, price, elapsed)
            greeks = _candidate_greeks(candidate, price, elapsed)
            rows.append(
                {
                    "underlying_price": price,
                    "projection_day": elapsed,
                    "projection_label": f"T+{elapsed}",
                    "pnl": mark_value - opening_value,
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


def _candidate_mark_value(candidate: BatmanCandidate, underlying_price: float, elapsed_days: int) -> float:
    total = 0.0
    for leg in candidate.legs:
        price = black_scholes_call_price(
            underlying_price,
            leg.quote.strike,
            _leg_years_to_expiry(candidate, leg, elapsed_days),
            _leg_iv(leg),
        )
        total += leg.signed_quantity * price * CONTRACT_MULTIPLIER
    return total


def _candidate_greeks(candidate: BatmanCandidate, underlying_price: float, elapsed_days: int) -> dict[str, float]:
    totals = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for leg in candidate.legs:
        greeks = black_scholes_call_greeks(
            underlying_price,
            leg.quote.strike,
            _leg_years_to_expiry(candidate, leg, elapsed_days),
            _leg_iv(leg),
        )
        totals["delta"] += leg.signed_quantity * greeks["delta"] * CONTRACT_MULTIPLIER
        totals["gamma"] += leg.signed_quantity * greeks["gamma"] * CONTRACT_MULTIPLIER
        totals["theta"] += leg.signed_quantity * greeks["theta"] * CONTRACT_MULTIPLIER
        totals["vega"] += leg.signed_quantity * greeks["vega"] * CONTRACT_MULTIPLIER
    return totals
