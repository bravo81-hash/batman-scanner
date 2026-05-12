"""Clearly labelled mock data for UI testing without IBKR."""

from __future__ import annotations

from scanner.batman import build_candidates_from_quotes
from scanner.dte_neighborhoods import build_dte_neighborhoods
from scanner.efficiency import apply_candidate_efficiency
from scanner.market_regime import build_market_regime_snapshot
from scanner.models import OptionQuote, ScanResult, ScanSettings
from scanner.scoring import rank_candidates


def _quote(
    symbol: str,
    expiry: str,
    strike: float,
    delta: float,
    bid: float,
    ask: float,
    implied_vol: float | None = None,
) -> OptionQuote:
    return OptionQuote(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        right="C",
        bid=bid,
        ask=ask,
        mid=round((bid + ask) / 2, 2),
        delta=delta,
        theta=round(-0.04 - (delta / 1000), 4),
        vega=round(0.5 + (delta / 20), 4),
        gamma=round(0.001 + (delta / 100000), 5),
        implied_vol=implied_vol,
    )


def mock_scan(settings: ScanSettings) -> ScanResult:
    """Create plausible mock candidates so the UI can be tested offline."""
    symbol = settings.symbol
    quotes_by_expiry = {
        "2027-01-15": [
            _quote(symbol, "2027-01-15", 5200, 60, 50, 52, 0.19),
            _quote(symbol, "2027-01-15", 5300, 55, 40, 42, 0.185),
            _quote(symbol, "2027-01-15", 5400, 50, 33, 35, 0.18),
            _quote(symbol, "2027-01-15", 5900, 10, 5, 6, 0.205),
            _quote(symbol, "2027-01-15", 6000, 7, 3, 4, 0.21),
            _quote(symbol, "2027-01-15", 6100, 5, 2, 3, 0.215),
        ],
        "2027-04-16": [
            _quote(symbol, "2027-04-16", 5600, 38, 15, 16, 0.20),
            _quote(symbol, "2027-04-16", 5700, 34, 13, 14, 0.198),
            _quote(symbol, "2027-04-16", 5800, 32, 12, 13, 0.195),
            _quote(symbol, "2027-04-16", 5900, 29, 10, 11, 0.193),
        ],
    }
    dte_by_expiry = {"2027-01-15": 253, "2027-04-16": 344}
    candidates = build_candidates_from_quotes(symbol, quotes_by_expiry, dte_by_expiry, settings)
    ranked = rank_candidates(candidates, settings)
    ranked = [apply_candidate_efficiency(candidate) for candidate in ranked]
    dte_neighborhoods = build_dte_neighborhoods(quotes_by_expiry, dte_by_expiry, settings)
    market_regime = build_market_regime_snapshot(quotes_by_expiry, dte_by_expiry, ranked, dte_neighborhoods)
    return ScanResult(
        settings=settings,
        candidates=ranked[: settings.max_results],
        dte_neighborhoods=dte_neighborhoods,
        market_regime=market_regime,
        mock=True,
    )
