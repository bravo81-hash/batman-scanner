"""Entry-selection benchmark helpers.

These helpers build reference structures from already-fetched quotes. They do
not place orders and do not manage open trades. Their purpose is to improve
pre-entry candidate selection by comparing the enhanced scanner against simple
canonical and constrained-sweep structures.
"""

from __future__ import annotations

from dataclasses import replace

from scanner.batman import build_batman_candidate_with_reason, nearest_by_delta
from scanner.models import BatmanCandidate, OptionQuote, ScanSettings
from scanner.scoring import rank_candidates


def _nearest_expiry_by_target(
    dte_by_expiry: dict[str, int],
    target_dte: int,
    tolerance: int,
) -> str | None:
    """Return the expiry closest to a target DTE within tolerance."""
    eligible = [
        (expiry, dte, abs(dte - target_dte))
        for expiry, dte in dte_by_expiry.items()
        if abs(dte - target_dte) <= tolerance
    ]
    if not eligible:
        return None
    eligible.sort(key=lambda item: item[2])
    return eligible[0][0]


def build_canonical_candidate(
    symbol: str,
    quotes_by_expiry: dict[str, list[OptionQuote]],
    dte_by_expiry: dict[str, int],
    settings: ScanSettings,
) -> BatmanCandidate | None:
    """Build a canonical 54/32/target-delta reference candidate.

    This is a benchmark only. It lets the trader compare the dynamic scanner's
    candidates against a familiar 54/32 structure around the target DTEs.
    """
    front_expiry = _nearest_expiry_by_target(dte_by_expiry, settings.front_target_dte, settings.dte_tolerance)
    back_expiry = _nearest_expiry_by_target(dte_by_expiry, settings.back_target_dte, settings.dte_tolerance)
    if front_expiry is None or back_expiry is None or front_expiry == back_expiry:
        return None

    front_dte = dte_by_expiry[front_expiry]
    back_dte = dte_by_expiry[back_expiry]
    if back_dte <= front_dte:
        return None

    front_quotes = quotes_by_expiry.get(front_expiry, [])
    back_quotes = quotes_by_expiry.get(back_expiry, [])
    sc_high = nearest_by_delta(front_quotes, 54.0)
    lc_mid = nearest_by_delta(back_quotes, 32.0)
    if sc_high is None or lc_mid is None:
        return None

    canonical_settings = replace(settings, min_credit=-1_000_000, require_positive_theta=False)
    candidate, _reason = build_batman_candidate_with_reason(
        symbol=symbol,
        front_expiry=front_expiry,
        back_expiry=back_expiry,
        front_dte=front_dte,
        back_dte=back_dte,
        sc_high=sc_high,
        lc_mid=lc_mid,
        front_quotes=front_quotes,
        target_total_delta=settings.target_trade_delta,
        settings=canonical_settings,
    )
    if candidate is None:
        return None
    candidate.rank = 0
    return rank_candidates([candidate], settings)[0]


def build_constrained_sweep_candidates(
    symbol: str,
    quotes_by_expiry: dict[str, list[OptionQuote]],
    dte_by_expiry: dict[str, int],
    settings: ScanSettings,
    limit: int = 25,
) -> list[BatmanCandidate]:
    """Build a benchmark sweep inspired by the reference Flask analyzer.

    It fixes the long leg near sweep_long_delta on the target back expiry, then
    sweeps front-expiry high and low short delta ranges. This is intentionally a
    benchmark/research shortlist, not the primary live scanner.
    """
    front_expiry = _nearest_expiry_by_target(dte_by_expiry, settings.front_target_dte, settings.dte_tolerance)
    back_expiry = _nearest_expiry_by_target(dte_by_expiry, settings.back_target_dte, settings.dte_tolerance)
    if front_expiry is None or back_expiry is None or front_expiry == back_expiry:
        return []

    front_dte = dte_by_expiry[front_expiry]
    back_dte = dte_by_expiry[back_expiry]
    if back_dte <= front_dte:
        return []

    front_quotes = [quote for quote in quotes_by_expiry.get(front_expiry, []) if quote.has_required_data()]
    back_quotes = [quote for quote in quotes_by_expiry.get(back_expiry, []) if quote.has_required_data()]
    lc_mid = nearest_by_delta(back_quotes, settings.sweep_long_delta)
    if lc_mid is None:
        return []

    short_hi_quotes = [
        quote for quote in front_quotes
        if settings.sweep_short_hi_min_delta <= (quote.delta or 0.0) <= settings.sweep_short_hi_max_delta
    ]
    short_lo_quotes = [
        quote for quote in front_quotes
        if settings.sweep_short_lo_min_delta <= (quote.delta or 0.0) <= settings.sweep_short_lo_max_delta
    ]

    sweep_settings = replace(settings, min_credit=-1_000_000, require_positive_theta=False)
    candidates: list[BatmanCandidate] = []
    for sc_high in short_hi_quotes:
        for sc_low in short_lo_quotes:
            if sc_low.strike <= sc_high.strike:
                continue
            # Reuse the builder by providing a front quote universe that allows
            # the chosen low-short to be selected by total delta. Then verify it
            # matched the intended sweep leg.
            candidate, _reason = build_batman_candidate_with_reason(
                symbol=symbol,
                front_expiry=front_expiry,
                back_expiry=back_expiry,
                front_dte=front_dte,
                back_dte=back_dte,
                sc_high=sc_high,
                lc_mid=lc_mid,
                front_quotes=[sc_low],
                target_total_delta=settings.target_trade_delta,
                settings=sweep_settings,
            )
            if candidate is None:
                continue
            if abs(candidate.total_delta) > settings.sweep_max_abs_delta:
                continue
            candidates.append(candidate)

    ranked = rank_candidates(candidates, settings)
    for index, candidate in enumerate(ranked[:limit], start=1):
        candidate.rank = index
    return ranked[:limit]
