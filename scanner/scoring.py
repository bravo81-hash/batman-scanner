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


def normalize_high_is_good(values: list[float]) -> list[float]:
    """Normalize values from 0.0 to 1.0 where higher is better."""
    if not values:
        return []
    lowest = min(values)
    highest = max(values)
    if highest == lowest:
        return [1.0 for _ in values]
    return [(value - lowest) / (highest - lowest) for value in values]


def score_candidate(candidate: BatmanCandidate, settings: ScanSettings) -> BatmanCandidate:
    """Apply the original balanced score to one candidate and return it."""
    delta_distance = abs(candidate.total_delta - settings.target_trade_delta)
    candidate.delta_score = max(0.0, 1.0 - delta_distance / settings.allowed_delta_deviation)
    candidate.credit_score = min(max(candidate.entry_credit / settings.target_credit, 0.0), 1.0)
    candidate.dte_anchor_score = dte_anchor_score(candidate.front_dte, candidate.back_dte)
    candidate.spread_penalty = spread_penalty(candidate)
    candidate.theta_score = 0.0
    candidate.delta_theta_ratio_score = 0.0
    candidate.score = max(
        0.0,
        (candidate.delta_score * 0.60)
        + (candidate.credit_score * 0.25)
        + (candidate.dte_anchor_score * 0.15)
        - candidate.spread_penalty,
    )
    return candidate


def score_theta_first_candidates(candidates: list[BatmanCandidate]) -> list[BatmanCandidate]:
    """Score candidates mostly by position theta, then by entry credit."""
    theta_scores = normalize_high_is_good([candidate.position_theta for candidate in candidates])
    credit_scores = normalize_high_is_good([candidate.entry_credit for candidate in candidates])
    for candidate, theta_score, credit_score in zip(candidates, theta_scores, credit_scores):
        candidate.theta_score = theta_score
        candidate.credit_score = credit_score
        candidate.delta_score = 0.0
        candidate.delta_theta_ratio_score = 0.0
        candidate.dte_anchor_score = dte_anchor_score(candidate.front_dte, candidate.back_dte)
        candidate.spread_penalty = spread_penalty(candidate)
        candidate.score = max(0.0, (0.75 * theta_score) + (0.25 * credit_score) - candidate.spread_penalty)
    return candidates


def score_delta_theta_ratio_candidates(candidates: list[BatmanCandidate]) -> list[BatmanCandidate]:
    """Score candidates by delta/theta efficiency, then theta and credit."""
    ratio_scores = normalize_high_is_good([candidate.delta_theta_ratio for candidate in candidates])
    theta_scores = normalize_high_is_good([candidate.position_theta for candidate in candidates])
    credit_scores = normalize_high_is_good([candidate.entry_credit for candidate in candidates])
    for candidate, ratio_score, theta_score, credit_score in zip(candidates, ratio_scores, theta_scores, credit_scores):
        candidate.delta_theta_ratio_score = ratio_score
        candidate.theta_score = theta_score
        candidate.credit_score = credit_score
        candidate.delta_score = 0.0
        candidate.dte_anchor_score = dte_anchor_score(candidate.front_dte, candidate.back_dte)
        candidate.spread_penalty = spread_penalty(candidate)
        candidate.score = max(
            0.0,
            (0.60 * ratio_score) + (0.25 * theta_score) + (0.15 * credit_score) - candidate.spread_penalty,
        )
    return candidates


def rank_candidates(candidates: list[BatmanCandidate], settings: ScanSettings) -> list[BatmanCandidate]:
    if settings.scoring_mode == "balanced":
        scored = [score_candidate(candidate, settings) for candidate in candidates]
        scored.sort(key=lambda item: item.score, reverse=True)
    elif settings.scoring_mode == "delta_theta_ratio":
        scored = score_delta_theta_ratio_candidates(candidates)
        scored.sort(
            key=lambda item: (
                item.score,
                item.delta_theta_ratio,
                item.position_theta,
                item.entry_credit,
                item.position_delta,
            ),
            reverse=True,
        )
    else:
        scored = score_theta_first_candidates(candidates)
        scored.sort(
            key=lambda item: (
                item.score,
                item.position_theta,
                item.entry_credit,
                item.position_delta,
            ),
            reverse=True,
        )
    for index, candidate in enumerate(scored, start=1):
        candidate.rank = index
    return scored
