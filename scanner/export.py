"""CSV export helpers."""

from __future__ import annotations

import csv
from io import StringIO

from scanner.models import BatmanCandidate


def _rounded_optional(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def candidates_to_csv(candidates: list[BatmanCandidate]) -> str:
    """Return CSV text with one row per leg."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "rank",
            "candidate_score",
            "symbol",
            "leg",
            "action",
            "quantity",
            "expiry",
            "strike",
            "right",
            "bid",
            "ask",
            "mid",
            "delta",
            "theta",
            "vega",
            "gamma",
            "implied_vol",
            "bqi_v4_proxy",
            "bqi_v4_percentile",
            "tx_score_v7_proxy",
            "tx_score_v7_percentile",
            "research_quality",
        ]
    )
    for candidate in candidates:
        for leg in candidate.legs:
            quote = leg.quote
            writer.writerow(
                [
                    candidate.rank,
                    round(candidate.score, 4),
                    candidate.symbol,
                    leg.name,
                    leg.action,
                    leg.quantity,
                    quote.expiry,
                    quote.strike,
                    "CALL",
                    quote.bid,
                    quote.ask,
                    quote.mid,
                    quote.delta,
                    quote.theta,
                    quote.vega,
                    quote.gamma,
                    quote.implied_vol,
                    _rounded_optional(candidate.bqi_v4_proxy, 4),
                    _rounded_optional(candidate.bqi_v4_percentile, 1),
                    _rounded_optional(candidate.tx_score_v7_proxy, 4),
                    _rounded_optional(candidate.tx_score_v7_percentile, 1),
                    candidate.research_quality_bucket,
                ]
            )
    return output.getvalue()
