import unittest

from scanner.models import ScanSettings
from scanner.presets import apply_strategy_preset


class StrategyPresetTests(unittest.TestCase):
    def test_buddy_54_32_3_preset_applies_exact_targets(self) -> None:
        settings = apply_strategy_preset(ScanSettings(strategy_preset="buddy_54_32_3"))

        self.assertEqual(settings.sc_high_min_delta, 54)
        self.assertEqual(settings.sc_high_max_delta, 54)
        self.assertEqual(settings.lc_mid_min_offset, 22)
        self.assertEqual(settings.lc_mid_max_offset, 22)
        self.assertEqual(settings.target_trade_delta, 3.0)
        self.assertEqual(settings.scoring_mode, "theta_first")
        self.assertEqual(settings.expiry_pairing_mode, "first_valid_far")

    def test_live_conservative_requires_positive_theta(self) -> None:
        settings = apply_strategy_preset(ScanSettings(strategy_preset="live_conservative"))

        self.assertTrue(settings.require_positive_theta)
        self.assertEqual(settings.scoring_mode, "theta_first")
        self.assertGreaterEqual(settings.upside_strike_multiplier, 1.60)


if __name__ == "__main__":
    unittest.main()
