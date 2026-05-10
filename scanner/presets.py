"""Strategy presets for common Batman scanner configurations."""

from __future__ import annotations

from dataclasses import replace

from scanner.models import ScanSettings


def apply_strategy_preset(settings: ScanSettings) -> ScanSettings:
    """Return settings with the selected strategy preset applied."""
    if settings.strategy_preset == "buddy_54_32_3":
        return replace(
            settings,
            sc_high_min_delta=54,
            sc_high_max_delta=54,
            sc_high_delta_step=1,
            lc_mid_min_offset=22,
            lc_mid_max_offset=22,
            lc_mid_offset_step=1,
            target_trade_delta=3.0,
            scoring_mode="theta_first",
            expiry_pairing_mode="first_valid_far",
        )
    if settings.strategy_preset == "live_conservative":
        return replace(
            settings,
            require_positive_theta=True,
            scoring_mode="theta_first",
            upside_strike_multiplier=max(settings.upside_strike_multiplier, 1.60),
        )
    return settings
