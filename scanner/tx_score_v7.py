"""Estimated TX_SCORE v7 implementation.

Based on the supplied TX_SCORE slides:

Component 1 (75%):
- mean area under T+X lines
- evaluated in +4%, +6%, +8% upside zone
- weighted by DTE

Component 2 (25%):
- slope/improvement of the T+X lines through time
"""

from __future__ import annotations

from dataclasses import dataclass

from scanner.models import BatmanCandidate
from scanner.risk_chart import candidate_risk_frame


@dataclass(frozen=True)
class TXScoreV7Components:
    tx_score_raw: float
    tx_component_1: float
    tx_component_2: float
    tx_4pct_avg: float
    tx_6pct_avg: float
    tx_8pct_avg: float
    tx_time_slope: float


def calculate_tx_score_v7(candidate: BatmanCandidate, underlying_price: float | None) -> TXScoreV7Components:
    if underlying_price is None or underlying_price <= 0:
        return TXScoreV7Components(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    try:
        frame = candidate_risk_frame(
            candidate,
            spot_price=underlying_price,
            price_points=91,
            projection_count=5,
            lower_price_multiplier=0.95,
            upper_price_multiplier=1.12,
        )
    except Exception:
        return TXScoreV7Components(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    if frame.empty:
        return TXScoreV7Components(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    target_levels = [1.04, 1.06, 1.08]
    weighted_zone_values: list[float] = []
    time_values: list[tuple[int, float]] = []
    zone_averages: list[float] = []

    for projection_day in sorted(frame["projection_day"].unique()):
        day_rows = frame[frame["projection_day"] == projection_day]
        zone_day_values: list[float] = []

        for level in target_levels:
            target_price = underlying_price * level
            level_rows = day_rows[
                (day_rows["underlying_price"] >= target_price * 0.995)
                & (day_rows["underlying_price"] <= target_price * 1.005)
            ]
            if level_rows.empty:
                continue
            value = float(level_rows["mid_normalized_pnl"].mean())
            zone_day_values.append(value)

        if zone_day_values:
            average_zone_value = sum(zone_day_values) / len(zone_day_values)
            zone_averages.append(average_zone_value)
            dte_weight = max(candidate.back_dte - projection_day, 1) / max(candidate.back_dte, 1)
            weighted_zone_values.append(average_zone_value * dte_weight)
            time_values.append((projection_day, average_zone_value))

    component_1 = sum(weighted_zone_values) / len(weighted_zone_values) if weighted_zone_values else 0.0

    component_2 = 0.0
    if len(time_values) >= 2:
        start_day, start_value = time_values[0]
        end_day, end_value = time_values[-1]
        day_diff = max(end_day - start_day, 1)
        component_2 = (end_value - start_value) / day_diff

    tx_raw = (0.75 * component_1) + (0.25 * component_2)

    zone_4 = zone_averages[0] if len(zone_averages) >= 1 else 0.0
    zone_6 = zone_averages[1] if len(zone_averages) >= 2 else 0.0
    zone_8 = zone_averages[2] if len(zone_averages) >= 3 else 0.0

    return TXScoreV7Components(
        tx_score_raw=tx_raw,
        tx_component_1=component_1,
        tx_component_2=component_2,
        tx_4pct_avg=zone_4,
        tx_6pct_avg=zone_6,
        tx_8pct_avg=zone_8,
        tx_time_slope=component_2,
    )
