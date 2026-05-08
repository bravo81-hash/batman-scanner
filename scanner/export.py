"""CSV export helpers."""

from __future__ import annotations

import csv
from io import StringIO

from scanner.models import BatmanCandidate


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
                ]
            )
    return output.getvalue()

