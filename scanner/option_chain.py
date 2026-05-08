"""Option chain scanning orchestration."""

from __future__ import annotations

from datetime import date
from typing import Callable

from scanner.batman import build_candidates_from_quotes
from scanner.contracts import days_to_expiry
from scanner.models import OptionQuote, ScanResult, ScanSettings
from scanner.scoring import rank_candidates


ProgressCallback = Callable[[str], None]


def select_candidate_strikes(
    strikes: list[float],
    underlying_price: float | None,
    max_contracts: int,
) -> list[float]:
    """Return a bounded strike list so live scans do not request too much data.

    When an underlying price is available, keep strikes in a broad call-focused
    window and then choose the closest strikes around the underlying. If no
    price is available, keep a centered slice from the full chain.
    """
    clean = sorted(float(strike) for strike in strikes if float(strike) > 0)
    if not clean or max_contracts <= 0:
        return []

    if underlying_price is not None and underlying_price > 0:
        lower = underlying_price * 0.75
        upper = underlying_price * 1.45
        window = [strike for strike in clean if lower <= strike <= upper]
        if not window:
            window = clean
        closest = sorted(window, key=lambda strike: abs(strike - underlying_price))
        return sorted(closest[:max_contracts])

    midpoint = len(clean) // 2
    half = max_contracts // 2
    start = max(midpoint - half, 0)
    end = min(start + max_contracts, len(clean))
    start = max(end - max_contracts, 0)
    return clean[start:end]


def filter_expiries(expiries: list[str], settings: ScanSettings, as_of: date | None = None) -> dict[str, int]:
    """Return expiries whose DTE may participate in the scan."""
    dte_by_expiry: dict[str, int] = {}
    for expiry in expiries:
        dte = days_to_expiry(expiry, as_of)
        if settings.min_front_dte <= dte <= settings.max_dte:
            dte_by_expiry[expiry] = dte
    return dte_by_expiry


def quote_diagnostic_counts(quotes: list[OptionQuote]) -> dict[str, int]:
    """Count usable quotes and common missing-data reasons."""
    counts = {
        "total": len(quotes),
        "usable": 0,
        "missing": 0,
        "missing_bid_ask": 0,
        "invalid_bid_ask": 0,
        "missing_delta": 0,
    }
    for quote in quotes:
        if quote.has_required_data():
            counts["usable"] += 1
            continue
        counts["missing"] += 1
        for reason in quote.missing_data_reasons():
            counts[reason] += 1
    return counts


def scan_from_quote_fetcher(
    settings: ScanSettings,
    expiries: list[str],
    fetch_quotes_for_expiry: Callable[[str], list[OptionQuote]],
    progress: ProgressCallback | None = None,
) -> ScanResult:
    """Scan using a caller-provided quote fetch function."""
    progress = progress or (lambda message: None)
    progress("filtering expiries")
    dte_by_expiry = filter_expiries(expiries, settings)
    if not dte_by_expiry:
        return ScanResult(settings=settings, candidates=[], warnings=["No expiries matched the DTE filters."])

    quotes_by_expiry: dict[str, list[OptionQuote]] = {}
    quote_counts_by_expiry: dict[str, dict[str, int]] = {}
    skipped_missing_data = 0
    for expiry in sorted(dte_by_expiry):
        progress(f"requesting market data for {expiry}")
        quotes = fetch_quotes_for_expiry(expiry)
        valid_quotes = [quote for quote in quotes if quote.has_required_data()]
        counts = quote_diagnostic_counts(quotes)
        missing_count = counts["missing"]
        skipped_missing_data += missing_count
        quote_counts_by_expiry[expiry] = counts
        if valid_quotes:
            quotes_by_expiry[expiry] = valid_quotes

    progress("building candidates")
    candidates = build_candidates_from_quotes(settings.symbol, quotes_by_expiry, dte_by_expiry, settings)
    progress("scoring candidates")
    ranked = rank_candidates(candidates, settings)
    return ScanResult(
        settings=settings,
        candidates=ranked[: settings.max_results],
        skipped_missing_data=skipped_missing_data,
        skipped_filters=max(len(candidates) - len(ranked), 0),
        quote_counts_by_expiry=quote_counts_by_expiry,
    )
