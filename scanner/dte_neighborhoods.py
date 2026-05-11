"""DTE neighborhood analysis for Batman candidate discovery.

This module ranks front/back expiry neighborhoods after quotes have already
been fetched. It is intentionally heuristic and deterministic. It does not place
orders, manage open trades, or perform heavy optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from scanner.models import OptionQuote, ScanSettings


@dataclass
class DteNeighborhood:
    front_expiry: str
    back_expiry: str
    front_dte: int
    back_dte: int
    dte_gap: int
    front_usable_quotes: int
    back_usable_quotes: int
    front_avg_spread_ratio: float
    back_avg_spread_ratio: float
    front_avg_theta: float
    back_avg_theta: float
    front_avg_iv: float
    back_avg_iv: float
    liquidity_score: float
    theta_richness_score: float
    premium_richness_score: float
    term_structure_score: float
    score: float

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


def _average(values: list[float]) -> float:
    valid = [value for value in values if value is not None]
    return sum(valid) / len(valid) if valid else 0.0


def _spread_ratio(quote: OptionQuote) -> float:
    if quote.mid is None or quote.mid <= 0 or quote.bid is None or quote.ask is None:
        return 1.0
    return max((quote.ask - quote.bid) / quote.mid, 0.0)


def _expiry_summary(quotes: list[OptionQuote]) -> dict[str, float | int]:
    usable = [quote for quote in quotes if quote.has_required_data()]
    return {
        "usable_count": len(usable),
        "avg_spread_ratio": _average([_spread_ratio(quote) for quote in usable]),
        "avg_theta": _average([abs(quote.theta or 0.0) for quote in usable]),
        "avg_mid": _average([quote.mid or 0.0 for quote in usable]),
        "avg_iv": _average([quote.implied_vol or 0.0 for quote in usable if quote.implied_vol is not None]),
    }


def _bounded_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_dte_neighborhoods(
    quotes_by_expiry: dict[str, list[OptionQuote]],
    dte_by_expiry: dict[str, int],
    settings: ScanSettings,
    limit: int = 20,
) -> list[DteNeighborhood]:
    """Rank expiry-pair neighborhoods using already-fetched quote summaries."""
    summaries = {
        expiry: _expiry_summary(quotes)
        for expiry, quotes in quotes_by_expiry.items()
    }
    neighborhoods: list[DteNeighborhood] = []
    expiries = sorted(dte_by_expiry, key=lambda item: dte_by_expiry[item])

    for front_expiry in expiries:
        front_dte = dte_by_expiry[front_expiry]
        for back_expiry in expiries:
            back_dte = dte_by_expiry[back_expiry]
            dte_gap = back_dte - front_dte
            if dte_gap < settings.min_dte_gap or dte_gap > settings.max_dte_gap:
                continue
            if front_expiry == back_expiry or back_dte <= front_dte:
                continue

            front = summaries.get(front_expiry, {})
            back = summaries.get(back_expiry, {})
            front_count = int(front.get("usable_count", 0))
            back_count = int(back.get("usable_count", 0))
            if front_count == 0 or back_count == 0:
                continue

            front_spread = float(front.get("avg_spread_ratio", 1.0))
            back_spread = float(back.get("avg_spread_ratio", 1.0))
            avg_spread = (front_spread + back_spread) / 2
            liquidity = _bounded_score(1.0 - avg_spread / 0.20)

            front_theta = float(front.get("avg_theta", 0.0))
            back_theta = float(back.get("avg_theta", 0.0))
            theta_richness = _bounded_score((front_theta + back_theta) / 2 / 1.0)

            front_mid = float(front.get("avg_mid", 0.0))
            back_mid = float(back.get("avg_mid", 0.0))
            premium_richness = _bounded_score((front_mid + back_mid) / 2 / 250.0)

            front_iv = float(front.get("avg_iv", 0.0))
            back_iv = float(back.get("avg_iv", 0.0))
            # Calendar/diagonal structures are often more interesting when term
            # structure is not completely flat. This is an informational score,
            # not a hard rule.
            term_structure = _bounded_score(0.5 + (back_iv - front_iv) * 5.0)

            dte_anchor = 1.0 - (
                (abs(front_dte - 250) / 250 + abs(back_dte - 350) / 350) / 2
            )
            dte_anchor = _bounded_score(dte_anchor)

            score = (
                0.35 * liquidity
                + 0.25 * theta_richness
                + 0.20 * premium_richness
                + 0.10 * term_structure
                + 0.10 * dte_anchor
            )
            neighborhoods.append(
                DteNeighborhood(
                    front_expiry=front_expiry,
                    back_expiry=back_expiry,
                    front_dte=front_dte,
                    back_dte=back_dte,
                    dte_gap=dte_gap,
                    front_usable_quotes=front_count,
                    back_usable_quotes=back_count,
                    front_avg_spread_ratio=front_spread,
                    back_avg_spread_ratio=back_spread,
                    front_avg_theta=front_theta,
                    back_avg_theta=back_theta,
                    front_avg_iv=front_iv,
                    back_avg_iv=back_iv,
                    liquidity_score=liquidity,
                    theta_richness_score=theta_richness,
                    premium_richness_score=premium_richness,
                    term_structure_score=term_structure,
                    score=score,
                )
            )

    neighborhoods.sort(key=lambda item: item.score, reverse=True)
    return neighborhoods[:limit]


def dte_neighborhood_rows(neighborhoods: list[DteNeighborhood]) -> list[dict]:
    """Return rounded rows for Streamlit display/export."""
    rows: list[dict] = []
    for rank, item in enumerate(neighborhoods, start=1):
        rows.append(
            {
                "rank": rank,
                "score": round(item.score, 4),
                "front_expiry": item.front_expiry,
                "front_dte": item.front_dte,
                "back_expiry": item.back_expiry,
                "back_dte": item.back_dte,
                "gap": item.dte_gap,
                "front_quotes": item.front_usable_quotes,
                "back_quotes": item.back_usable_quotes,
                "liquidity": round(item.liquidity_score, 4),
                "theta_richness": round(item.theta_richness_score, 4),
                "premium_richness": round(item.premium_richness_score, 4),
                "term_structure": round(item.term_structure_score, 4),
                "front_avg_spread": round(item.front_avg_spread_ratio, 4),
                "back_avg_spread": round(item.back_avg_spread_ratio, 4),
                "front_avg_iv": round(item.front_avg_iv, 4),
                "back_avg_iv": round(item.back_avg_iv, 4),
            }
        )
    return rows
