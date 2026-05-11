"""Market regime analysis for Batman candidate discovery.

This module classifies the current option-chain environment using quotes that
have already been fetched by the scanner. It is informational only: no position
sizing, no capital allocation, no trade management, and no broker actions.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from scanner.dte_neighborhoods import DteNeighborhood
from scanner.models import BatmanCandidate, OptionQuote


@dataclass
class MarketRegimeSnapshot:
    label: str
    iv_level: float
    iv_percentile_proxy: float
    term_structure_slope: float
    skew_proxy: float
    premium_richness: float
    theta_richness: float
    liquidity_quality: float
    dynamic_structures_favored: bool
    canonical_structures_favored: bool
    notes: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["notes"] = " | ".join(self.notes)
        return data


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _spread_ratio(quote: OptionQuote) -> float:
    if quote.mid is None or quote.mid <= 0 or quote.bid is None or quote.ask is None:
        return 1.0
    return max((quote.ask - quote.bid) / quote.mid, 0.0)


def build_market_regime_snapshot(
    quotes_by_expiry: dict[str, list[OptionQuote]],
    dte_by_expiry: dict[str, int],
    candidates: list[BatmanCandidate],
    neighborhoods: list[DteNeighborhood],
) -> MarketRegimeSnapshot:
    """Classify the option-chain environment from already-fetched scanner data."""
    usable_quotes = [
        quote
        for quotes in quotes_by_expiry.values()
        for quote in quotes
        if quote.has_required_data()
    ]
    ivs = [quote.implied_vol for quote in usable_quotes if quote.implied_vol is not None and quote.implied_vol > 0]
    mids = [quote.mid or 0.0 for quote in usable_quotes if quote.mid is not None and quote.mid > 0]
    thetas = [abs(quote.theta or 0.0) for quote in usable_quotes]
    spreads = [_spread_ratio(quote) for quote in usable_quotes]

    iv_level = _average(ivs)
    # Proxy only: without history, classify current chain IV relative to broad SPX-like bands.
    iv_percentile_proxy = _bounded((iv_level - 0.10) / 0.25) if iv_level else 0.0
    premium_richness = _bounded(_average(mids) / 250.0)
    theta_richness = _bounded(_average(thetas) / 1.0)
    liquidity_quality = _bounded(1.0 - _average(spreads) / 0.20)

    term_structure_slope = 0.0
    if neighborhoods:
        term_structure_slope = _average([
            item.back_avg_iv - item.front_avg_iv
            for item in neighborhoods
            if item.front_avg_iv > 0 and item.back_avg_iv > 0
        ])

    low_delta_ivs: list[float] = []
    high_delta_ivs: list[float] = []
    for quote in usable_quotes:
        if quote.implied_vol is None or quote.delta is None:
            continue
        if 5 <= quote.delta <= 20:
            low_delta_ivs.append(quote.implied_vol)
        elif 45 <= quote.delta <= 60:
            high_delta_ivs.append(quote.implied_vol)
    skew_proxy = _average(low_delta_ivs) - _average(high_delta_ivs) if low_delta_ivs and high_delta_ivs else 0.0

    avg_shape = _average([candidate.shape_quality_score for candidate in candidates])
    avg_liquidity = _average([candidate.liquidity_score for candidate in candidates])
    avg_theta = _average([candidate.position_theta for candidate in candidates])

    notes: list[str] = []
    if iv_percentile_proxy >= 0.70:
        label = "Premium-rich / elevated IV"
        notes.append("Option IV proxy is elevated; credit and theta may be richer but expansion/compression risk matters.")
    elif iv_percentile_proxy <= 0.30:
        label = "Compressed volatility"
        notes.append("Option IV proxy is compressed; prefer cleaner shapes and avoid overpaying for long legs.")
    else:
        label = "Neutral volatility"
        notes.append("Volatility proxy is mid-range; candidate structure quality and liquidity should drive selection.")

    if term_structure_slope > 0.02:
        notes.append("Back-expiry IV is materially above front-expiry IV in available quotes.")
    elif term_structure_slope < -0.02:
        notes.append("Front-expiry IV is materially above back-expiry IV in available quotes.")

    if skew_proxy > 0.02:
        notes.append("Low-delta call IV appears richer than high-delta call IV; inspect upside short-call quality carefully.")

    if liquidity_quality < 0.50:
        notes.append("Average spread quality is weak; use stricter liquidity filtering before OptionNet modelling.")
    elif liquidity_quality > 0.80:
        notes.append("Average spread quality is strong across fetched quotes.")

    dynamic_structures_favored = avg_shape >= 0.65 and avg_liquidity >= 0.50 and avg_theta > 0
    canonical_structures_favored = not dynamic_structures_favored and liquidity_quality >= 0.50
    if dynamic_structures_favored:
        notes.append("Dynamic structures appear favored by current candidate shape/liquidity/theta mix.")
    elif canonical_structures_favored:
        notes.append("Dynamic edge is not obvious; compare against canonical and constrained-sweep benchmarks.")
    else:
        notes.append("Low-quality regime for this scanner snapshot; be selective before modelling in OptionNet.")

    return MarketRegimeSnapshot(
        label=label,
        iv_level=iv_level,
        iv_percentile_proxy=iv_percentile_proxy,
        term_structure_slope=term_structure_slope,
        skew_proxy=skew_proxy,
        premium_richness=premium_richness,
        theta_richness=theta_richness,
        liquidity_quality=liquidity_quality,
        dynamic_structures_favored=dynamic_structures_favored,
        canonical_structures_favored=canonical_structures_favored,
        notes=notes,
    )


def market_regime_rows(snapshot: MarketRegimeSnapshot | None) -> list[dict[str, str | float | bool]]:
    """Return a compact one-row representation for Streamlit."""
    if snapshot is None:
        return []
    return [
        {
            "label": snapshot.label,
            "iv_level": round(snapshot.iv_level, 4),
            "iv_percentile_proxy": round(snapshot.iv_percentile_proxy, 4),
            "term_structure_slope": round(snapshot.term_structure_slope, 4),
            "skew_proxy": round(snapshot.skew_proxy, 4),
            "premium_richness": round(snapshot.premium_richness, 4),
            "theta_richness": round(snapshot.theta_richness, 4),
            "liquidity_quality": round(snapshot.liquidity_quality, 4),
            "dynamic_favored": snapshot.dynamic_structures_favored,
            "canonical_favored": snapshot.canonical_structures_favored,
            "notes": " | ".join(snapshot.notes),
        }
    ]
