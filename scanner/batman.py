"""Build Batman-style three-leg call candidates."""

from __future__ import annotations

from datetime import date

from scanner.models import BatmanCandidate, BatmanLeg, OptionQuote, ScanSettings


def add_rejection(rejection_reasons: dict[str, int] | None, reason: str) -> None:
    """Increment a rejection reason counter when diagnostics are enabled."""
    if rejection_reasons is None:
        return
    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1


def nearest_by_delta(quotes: list[OptionQuote], target_delta: float) -> OptionQuote | None:
    """Find the quote whose model delta is closest to the target."""
    usable = [quote for quote in quotes if quote.has_required_data()]
    if not usable:
        return None
    return min(usable, key=lambda quote: abs((quote.delta or 0.0) - target_delta))


def calculate_average_spread_ratio(legs: list[BatmanLeg]) -> float:
    ratios: list[float] = []
    for leg in legs:
        quote = leg.quote
        if quote.mid and quote.mid > 0:
            ratios.append(quote.spread / quote.mid)
    if not ratios:
        return 0.0
    return sum(ratios) / len(ratios)


def build_batman_candidate(
    symbol: str,
    front_expiry: str,
    back_expiry: str,
    front_dte: int,
    back_dte: int,
    sc_high: OptionQuote,
    lc_mid: OptionQuote,
    front_quotes: list[OptionQuote],
    target_total_delta: float,
    settings: ScanSettings,
    as_of: date | None = None,
) -> BatmanCandidate | None:
    """Create one candidate and choose SC_Low to land near target total delta."""
    candidate, _reason = build_batman_candidate_with_reason(
        symbol=symbol,
        front_expiry=front_expiry,
        back_expiry=back_expiry,
        front_dte=front_dte,
        back_dte=back_dte,
        sc_high=sc_high,
        lc_mid=lc_mid,
        front_quotes=front_quotes,
        target_total_delta=target_total_delta,
        settings=settings,
    )
    return candidate


def build_batman_candidate_with_reason(
    symbol: str,
    front_expiry: str,
    back_expiry: str,
    front_dte: int,
    back_dte: int,
    sc_high: OptionQuote,
    lc_mid: OptionQuote,
    front_quotes: list[OptionQuote],
    target_total_delta: float,
    settings: ScanSettings,
) -> tuple[BatmanCandidate | None, str | None]:
    """Create one candidate and return a rejection reason when it fails."""
    if not sc_high.has_required_data() or not lc_mid.has_required_data():
        return None, "missing_quote_data"

    base_delta = -(sc_high.delta or 0.0) + (2 * (lc_mid.delta or 0.0))
    low_candidates = [quote for quote in front_quotes if quote.has_required_data() and quote.strike > sc_high.strike]
    if not low_candidates:
        return None, "no_sc_low"

    sc_low = min(low_candidates, key=lambda quote: abs(base_delta - (quote.delta or 0.0) - target_total_delta))

    legs = [
        BatmanLeg("SC_High", "SELL", 1, sc_high),
        BatmanLeg("LC_Mid", "BUY", 2, lc_mid),
        BatmanLeg("SC_Low", "SELL", 1, sc_low),
    ]

    short_proceeds = (sc_high.bid or 0.0) + (sc_low.bid or 0.0)
    long_cost = 2 * (lc_mid.ask or 0.0)
    entry_credit = short_proceeds - long_cost

    candidate = BatmanCandidate(
        symbol=symbol,
        front_expiry=front_expiry,
        back_expiry=back_expiry,
        front_dte=front_dte,
        back_dte=back_dte,
        sc_high=legs[0],
        lc_mid=legs[1],
        sc_low=legs[2],
        entry_credit=entry_credit,
        total_delta=sum(leg.delta_contribution for leg in legs),
        total_theta=sum(leg.theta_contribution for leg in legs),
        total_vega=sum(leg.vega_contribution for leg in legs),
        total_gamma=sum(leg.gamma_contribution for leg in legs),
        average_spread_ratio=calculate_average_spread_ratio(legs),
    )

    if candidate.entry_credit <= settings.min_credit:
        return None, "negative_or_zero_credit"
    if candidate.total_delta <= 0:
        return None, "negative_or_zero_total_delta"
    if settings.require_positive_theta and candidate.position_theta <= 0:
        return None, "negative_or_zero_theta"
    return candidate, None


def back_expiries_for_front(
    front_expiry: str,
    expiries: list[str],
    dte_by_expiry: dict[str, int],
    settings: ScanSettings,
) -> list[str]:
    """Return valid back expiries for one front expiry using the configured pairing mode."""
    front_dte = dte_by_expiry.get(front_expiry, 0)
    later_expiries: list[str] = []
    for expiry in expiries:
        back_dte = dte_by_expiry.get(expiry, 0)
        dte_gap = back_dte - front_dte
        if back_dte <= front_dte or back_dte > settings.max_dte:
            continue
        if dte_gap < settings.min_dte_gap or dte_gap > settings.max_dte_gap:
            continue
        later_expiries.append(expiry)

    if settings.expiry_pairing_mode == "first_valid_far":
        return later_expiries[:1]
    if settings.expiry_pairing_mode == "adjacent_only":
        try:
            front_index = expiries.index(front_expiry)
        except ValueError:
            return []
        adjacent_index = front_index + 1
        if adjacent_index >= len(expiries):
            return []
        adjacent_expiry = expiries[adjacent_index]
        return [adjacent_expiry] if adjacent_expiry in later_expiries else []
    return later_expiries


def candidate_identity_key(candidate: BatmanCandidate) -> tuple[str, str, float, float, float]:
    """Return the expiry/strike identity for a concrete three-leg setup."""
    return (
        candidate.front_expiry,
        candidate.back_expiry,
        candidate.sc_high.quote.strike,
        candidate.lc_mid.quote.strike,
        candidate.sc_low.quote.strike,
    )


def build_candidates_from_quotes(
    symbol: str,
    quotes_by_expiry: dict[str, list[OptionQuote]],
    dte_by_expiry: dict[str, int],
    settings: ScanSettings,
    rejection_reasons: dict[str, int] | None = None,
) -> list[BatmanCandidate]:
    """Build candidates from already-fetched quotes grouped by expiry."""
    candidates: list[BatmanCandidate] = []
    seen_candidates: set[tuple[str, str, float, float, float]] = set()
    expiries = sorted(quotes_by_expiry.keys())

    sc_targets = range(
        settings.sc_high_min_delta,
        settings.sc_high_max_delta + 1,
        settings.sc_high_delta_step,
    )
    lc_offsets = range(
        settings.lc_mid_min_offset,
        settings.lc_mid_max_offset + 1,
        settings.lc_mid_offset_step,
    )

    for front_expiry in expiries:
        front_dte = dte_by_expiry.get(front_expiry, 0)
        if front_dte < settings.min_front_dte or front_dte > settings.max_dte:
            continue

        front_quotes = quotes_by_expiry[front_expiry]
        for back_expiry in back_expiries_for_front(front_expiry, expiries, dte_by_expiry, settings):
            back_dte = dte_by_expiry.get(back_expiry, 0)

            back_quotes = quotes_by_expiry[back_expiry]
            for sc_target in sc_targets:
                sc_high = nearest_by_delta(front_quotes, float(sc_target))
                if sc_high is None:
                    add_rejection(rejection_reasons, "no_sc_high")
                    continue
                for offset in lc_offsets:
                    lc_target = max((sc_high.delta or sc_target) - offset, 1.0)
                    lc_mid = nearest_by_delta(back_quotes, lc_target)
                    if lc_mid is None:
                        add_rejection(rejection_reasons, "no_lc_mid")
                        continue
                    candidate, reason = build_batman_candidate_with_reason(
                        symbol=symbol,
                        front_expiry=front_expiry,
                        back_expiry=back_expiry,
                        front_dte=front_dte,
                        back_dte=back_dte,
                        sc_high=sc_high,
                        lc_mid=lc_mid,
                        front_quotes=front_quotes,
                        target_total_delta=settings.target_trade_delta,
                        settings=settings,
                    )
                    if candidate is not None:
                        key = candidate_identity_key(candidate)
                        if key in seen_candidates:
                            add_rejection(rejection_reasons, "duplicate_candidate")
                            continue
                        seen_candidates.add(key)
                        candidates.append(candidate)
                    elif reason is not None:
                        add_rejection(rejection_reasons, reason)
    return candidates
