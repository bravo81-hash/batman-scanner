"""Candidate scoring rules."""

from __future__ import annotations

from scanner.models import BatmanCandidate, ScanSettings


def dte_anchor_score(front_dte: int, back_dte: int) -> float:
    """Gently favor the 250/350 DTE area without making it a hard filter."""
    front_distance = abs(front_dte - 250) / 250
    back_distance = abs(back_dte - 350) / 350
    average_distance = (front_distance + back_distance) / 2
    return max(0.0, 1.0 - average_distance)


def spread_penalty(candidate: BatmanCandidate) -> float:
    """Penalize candidates whose option spreads are wide relative to mid."""
    penalty = candidate.average_spread_ratio * 0.50
    return min(max(penalty, 0.0), 0.50)


def score_candidate(candidate: BatmanCandidate, settings: ScanSettings) -> BatmanCandidate:
    """Apply score components to a candidate and return the same object."""
    delta_distance = abs(candidate.total_delta - settings.target_trade_delta)
    candidate.delta_score = max(0.0, 1.0 - delta_distance / settings.allowed_delta_deviation)
    candidate.credit_score = min(max(candidate.entry_credit / settings.target_credit, 0.0), 1.0)
    candidate.dte_anchor_score = dte_anchor_score(candidate.front_dte, candidate.back_dte)
    candidate.spread_penalty = spread_penalty(candidate)
    candidate.score = max(
        0.0,
        (candidate.delta_score * 0.60)
        + (candidate.credit_score * 0.25)
        + (candidate.dte_anchor_score * 0.15)
        - candidate.spread_penalty,
    )
    return candidate


def rank_candidates(candidates: list[BatmanCandidate], settings: ScanSettings) -> list[BatmanCandidate]:
    scored = [score_candidate(candidate, settings) for candidate in candidates]
    scored.sort(key=lambda item: item.score, reverse=True)
    for index, candidate in enumerate(scored, start=1):
        candidate.rank = index
    return scored

