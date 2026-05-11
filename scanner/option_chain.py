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
    upside_multiplier: float = 1.45,
    strike_increment: int = 0,
) -> list[float]:
    """Return a bounded strike list so live scans do not request too much data.

    When an underlying price is available, keep strikes in a broad call-focused
    window and then choose the closest strikes around the underlying. If no
    price is available, keep a centered slice from the full chain.
    """
    clean = sorted(float(strike) for strike in strikes if float(strike) > 0)
    if strike_increment > 0:
        clean = [strike for strike in clean if round(strike) % strike_increment == 0]
    if not clean or max_contracts <= 0:
        return []

    if underlying_price is not None and underlying_price > 0:
        lower = underlying_price * 0.75
        upper = underlying_price * max(upside_multiplier, 1.0)
        window = [strike for strike in clean if lower <= strike <= upper]
        if not window:
            window = clean
        below_or_at_spot = [strike for strike in window if strike <= underlying_price]
        above_spot = [strike for strike in window if strike > underlying_price]

        below_count = min(len(below_or_at_spot), max(1, int(max_contracts * 0.30)))
        above_count = min(len(above_spot), max_contracts - below_count)
        selected = _evenly_spaced_values(below_or_at_spot, below_count)
        selected.extend(_evenly_spaced_values(above_spot, above_count))

        if len(selected) < max_contracts:
            selected_values = set(selected)
            remaining = [strike for strike in window if strike not in selected_values]
            selected.extend(_evenly_spaced_values(remaining, max_contracts - len(selected)))

        closest_to_spot = min(window, key=lambda strike: abs(strike - underlying_price))
        selected.append(closest_to_spot)
        final = sorted(set(selected))
        while len(final) > max_contracts:
            removable = [strike for strike in final if strike != closest_to_spot]
            if not removable:
                break
            final.remove(min(removable))
        return final

    midpoint = len(clean) // 2
    half = max_contracts // 2
    start = max(midpoint - half, 0)
    end = min(start + max_contracts, len(clean))
    start = max(end - max_contracts, 0)
    return clean[start:end]


def _evenly_spaced_values(values: list[float], count: int) -> list[float]:
    """Select up to count values spread across the full input range."""
    if count <= 0 or not values:
        return []
    if count >= len(values):
        return list(values)
    if count == 1:
        return [values[len(values) // 2]]

    last_index = len(values) - 1
    indexes = [round(index * last_index / (count - 1)) for index in range(count)]
    return [values[index] for index in indexes]


def _within_target_dte(dte: int, target: int, tolerance: int) -> bool:
    return abs(dte - target) <= tolerance


def filter_expiries(expiries: list[str], settings: ScanSettings, as_of: date | None = None) -> dict[str, int]:
    """Return expiries whose DTE may participate in the scan."""
    dte_by_expiry: dict[str, int] = {}
    for expiry in expiries:
        dte = days_to_expiry(expiry, as_of)
        if settings.dte_selection_mode == "target":
            if _within_target_dte(dte, settings.front_target_dte, settings.dte_tolerance) or _within_target_dte(
                dte, settings.back_target_dte, settings.dte_tolerance
            ):
                dte_by_expiry[expiry] = dte
            continue
        if settings.min_front_dte <= dte <= settings.max_dte:
            dte_by_expiry[expiry] = dte
    return dte_by_expiry


def quote_diagnostic_counts(quotes: list[OptionQuote]) -> dict[str, int | float]:
    """Count usable quotes and common missing-data reasons."""
    counts = {
        "total": len(quotes),
        "usable": 0,
        "missing": 0,
        "missing_bid_ask": 0,
        "invalid_bid_ask": 0,
        "missing_delta": 0,
        "min_usable_strike": 0.0,
        "max_usable_strike": 0.0,
        "min_usable_delta": 0.0,
        "max_usable_delta": 0.0,
    }
    usable_strikes: list[float] = []
    usable_deltas: list[float] = []
    for quote in quotes:
        if quote.has_required_data():
            counts["usable"] += 1
            usable_strikes.append(quote.strike)
            usable_deltas.append(quote.delta or 0.0)
            continue
        counts["missing"] += 1
        for reason in quote.missing_data_reasons():
            counts[reason] += 1
    if usable_strikes:
        counts["min_usable_strike"] = min(usable_strikes)
        counts["max_usable_strike"] = max(usable_strikes)
    if usable_deltas:
        counts["min_usable_delta"] = min(usable_deltas)
        counts["max_usable_delta"] = max(usable_deltas)
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
    quote_counts_by_expiry: dict[str, dict[str, int | float]] = {}
    rejection_reasons: dict[str, int] = {}
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
    candidates = build_candidates_from_quotes(
        settings.symbol,
        quotes_by_expiry,
        dte_by_expiry,
        settings,
        rejection_reasons=rejection_reasons,
    )
    progress("scoring candidates")
    ranked = rank_candidates(candidates, settings)
    warnings: list[str] = []
    usable_delta_mins = [
        counts["min_usable_delta"]
        for counts in quote_counts_by_expiry.values()
        if counts["usable"] > 0
    ]
    if usable_delta_mins and min(usable_delta_mins) > 20:
        warnings.append(
            "Usable cached quotes do not include low-delta calls. "
            "Refresh the quote cache with the latest strike selector so far-OTM Batman legs are available."
        )
    return ScanResult(
        settings=settings,
        candidates=ranked[: settings.max_results],
        skipped_missing_data=skipped_missing_data,
        skipped_filters=max(len(candidates) - len(ranked), 0),
        quote_counts_by_expiry=quote_counts_by_expiry,
        rejection_reasons=rejection_reasons,
        warnings=warnings,
    )
