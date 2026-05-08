import unittest

from scanner.batman import build_batman_candidate
from scanner.models import OptionQuote, ScanSettings
from scanner.risk_chart import (
    black_scholes_call_price,
    candidate_risk_frame,
    projection_days,
)


def quote(expiry: str, strike: float, delta: float, bid: float, ask: float, iv: float = 0.20) -> OptionQuote:
    return OptionQuote(
        symbol="SPX",
        expiry=expiry,
        strike=strike,
        right="C",
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2,
        delta=delta,
        theta=-0.1,
        vega=1.0,
        gamma=0.01,
        implied_vol=iv,
    )


class RiskChartTests(unittest.TestCase):
    def test_black_scholes_call_price_is_intrinsic_at_expiry(self) -> None:
        self.assertAlmostEqual(black_scholes_call_price(110, 100, 0, 0.2), 10)
        self.assertAlmostEqual(black_scholes_call_price(90, 100, 0, 0.2), 0)

    def test_projection_days_include_now_midpoints_and_final_expiry(self) -> None:
        self.assertEqual(projection_days(84, points=5), [0, 21, 42, 63, 84])

    def test_candidate_risk_frame_outputs_pnl_and_greek_columns(self) -> None:
        settings = ScanSettings()
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote("2027-01-15", 5200, 55, 35, 36),
            lc_mid=quote("2027-04-16", 5600, 33, 12, 13),
            front_quotes=[quote("2027-01-15", 6000, 8, 3, 4)],
            target_total_delta=3,
            settings=settings,
        )
        assert candidate is not None

        frame = candidate_risk_frame(candidate, spot_price=5500, price_points=11, projection_count=3)

        self.assertFalse(frame.empty)
        self.assertIn("underlying_price", frame.columns)
        self.assertIn("projection_label", frame.columns)
        self.assertIn("pnl", frame.columns)
        self.assertIn("delta", frame.columns)
        self.assertIn("theta", frame.columns)
        self.assertEqual(frame["projection_label"].nunique(), 3)

    def test_candidate_risk_frame_anchors_current_pnl_to_entry_credit_and_mid_marks(self) -> None:
        settings = ScanSettings()
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote("2027-01-15", 5200, 55, 35, 36),
            lc_mid=quote("2027-04-16", 5600, 33, 12, 13),
            front_quotes=[quote("2027-01-15", 6000, 8, 3, 4)],
            target_total_delta=3,
            settings=settings,
        )
        assert candidate is not None

        frame = candidate_risk_frame(candidate, spot_price=5000, price_points=1, projection_count=1)
        expected_mark = (-35.5 + 2 * 12.5 - 3.5) * 100
        expected_pnl = (candidate.entry_credit * 100) + expected_mark

        self.assertAlmostEqual(float(frame.iloc[0]["pnl"]), expected_pnl, places=3)


if __name__ == "__main__":
    unittest.main()
