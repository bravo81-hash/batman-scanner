from datetime import date
import unittest

from scanner.batman import build_batman_candidate, build_candidates_from_quotes, back_expiries_for_front
from scanner.export import candidates_to_csv
from scanner.models import OptionQuote, ScanSettings
from scanner.scoring import rank_candidates, score_candidate


def quote(expiry: str, strike: float, delta: float, bid: float, ask: float) -> OptionQuote:
    return OptionQuote(
        symbol="SPX",
        expiry=expiry,
        strike=strike,
        right="C",
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2,
        delta=delta,
        theta=-0.10,
        vega=1.0,
        gamma=0.01,
    )


def quote_with_theta(expiry: str, strike: float, delta: float, bid: float, ask: float, theta: float) -> OptionQuote:
    option_quote = quote(expiry, strike, delta, bid, ask)
    option_quote.theta = theta
    return option_quote


class BatmanCoreTests(unittest.TestCase):
    def test_build_candidate_uses_low_short_call_to_target_total_delta(self) -> None:
        settings = ScanSettings()
        sc_high = quote("2026-10-16", 5200, 54, 30, 32)
        lc_mid = quote("2027-01-15", 5600, 32, 10, 11)
        low_quotes = [
            quote("2026-10-16", 5900, 4, 2, 2.5),
            quote("2026-10-16", 6000, 7, 1.5, 2.0),
            quote("2026-10-16", 6100, 10, 1.0, 1.5),
        ]

        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2026-10-16",
            back_expiry="2027-01-15",
            front_dte=162,
            back_dte=253,
            sc_high=sc_high,
            lc_mid=lc_mid,
            front_quotes=low_quotes,
            target_total_delta=settings.target_trade_delta,
            settings=settings,
            as_of=date(2026, 5, 7),
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.sc_low.quote.strike, 6000)
        self.assertAlmostEqual(candidate.total_delta, 3.0)
        self.assertAlmostEqual(candidate.entry_credit, 9.5)

    def test_score_rewards_delta_near_target_and_positive_credit(self) -> None:
        settings = ScanSettings(target_trade_delta=3, min_credit=0)
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2026-10-16",
            back_expiry="2027-04-16",
            front_dte=250,
            back_dte=344,
            sc_high=quote("2026-10-16", 5200, 54, 35, 36),
            lc_mid=quote("2027-04-16", 5600, 32, 12, 13),
            front_quotes=[quote("2026-10-16", 6000, 7, 3, 3.5)],
            target_total_delta=3,
            settings=settings,
            as_of=date(2026, 5, 7),
        )

        assert candidate is not None
        scored = score_candidate(candidate, settings)

        self.assertGreater(scored.score, 0.7)
        self.assertAlmostEqual(scored.delta_score, 1.0)
        self.assertGreater(scored.credit_score, 0)
        self.assertGreater(scored.dte_anchor_score, 0.9)

    def test_theta_first_ranking_prefers_better_position_theta(self) -> None:
        settings = ScanSettings(scoring_mode="theta_first")
        better_theta = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote_with_theta("2027-01-15", 5200, 55, 35, 36, -0.20),
            lc_mid=quote_with_theta("2027-04-16", 5600, 33, 12, 13, -0.05),
            front_quotes=[quote_with_theta("2027-01-15", 6000, 8, 3, 4, -0.20)],
            target_total_delta=3,
            settings=settings,
        )
        worse_theta = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote_with_theta("2027-01-15", 5200, 55, 40, 41, -0.10),
            lc_mid=quote_with_theta("2027-04-16", 5600, 33, 13, 14, -0.25),
            front_quotes=[quote_with_theta("2027-01-15", 6000, 8, 5, 6, -0.10)],
            target_total_delta=3,
            settings=settings,
        )

        assert better_theta is not None
        assert worse_theta is not None
        ranked = rank_candidates([worse_theta, better_theta], settings)

        self.assertIs(ranked[0], better_theta)
        self.assertGreater(ranked[0].theta_score, ranked[1].theta_score)
        self.assertGreater(ranked[0].score, ranked[1].score)
        self.assertGreater(ranked[0].liquidity_score, 0)
        self.assertGreater(ranked[0].shape_quality_score, 0)

    def test_candidate_exposes_position_dollar_greeks_and_delta_theta_ratio(self) -> None:
        settings = ScanSettings()
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote_with_theta("2027-01-15", 5200, 55, 35, 36, -0.20),
            lc_mid=quote_with_theta("2027-04-16", 5600, 33, 12, 13, -0.05),
            front_quotes=[quote_with_theta("2027-01-15", 6000, 8, 3, 4, -0.20)],
            target_total_delta=3,
            settings=settings,
        )

        assert candidate is not None
        self.assertAlmostEqual(candidate.position_delta, 3)
        self.assertAlmostEqual(candidate.position_theta, 30)
        self.assertAlmostEqual(candidate.delta_theta_ratio, 0.1)

    def test_csv_export_includes_each_leg(self) -> None:
        settings = ScanSettings()
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2026-10-16",
            back_expiry="2027-01-15",
            front_dte=162,
            back_dte=253,
            sc_high=quote("2026-10-16", 5200, 54, 30, 32),
            lc_mid=quote("2027-01-15", 5600, 32, 10, 11),
            front_quotes=[quote("2026-10-16", 6000, 7, 1.5, 2.0)],
            target_total_delta=3,
            settings=settings,
            as_of=date(2026, 5, 7),
        )

        assert candidate is not None
        csv_text = candidates_to_csv([candidate])

        self.assertIn("SC_High,SELL,1", csv_text)
        self.assertIn("LC_Mid,BUY,2", csv_text)
        self.assertIn("SC_Low,SELL,1", csv_text)

    def test_expiry_pairing_modes_choose_expected_back_expiries(self) -> None:
        expiries = ["20270115", "20270219", "20270416", "20270618"]
        dte_by_expiry = {
            "20270115": 250,
            "20270219": 285,
            "20270416": 341,
            "20270618": 404,
        }

        all_pairs = back_expiries_for_front("20270115", expiries, dte_by_expiry, ScanSettings(min_dte_gap=50))
        adjacent = back_expiries_for_front(
            "20270115",
            expiries,
            dte_by_expiry,
            ScanSettings(min_dte_gap=50, expiry_pairing_mode="adjacent_only"),
        )
        first_valid = back_expiries_for_front(
            "20270115",
            expiries,
            dte_by_expiry,
            ScanSettings(min_dte_gap=50, expiry_pairing_mode="first_valid_far"),
        )

        self.assertEqual(all_pairs, ["20270416", "20270618"])
        self.assertEqual(adjacent, [])
        self.assertEqual(first_valid, ["20270416"])

    def test_require_positive_theta_rejects_theta_negative_candidates(self) -> None:
        settings = ScanSettings(
            require_positive_theta=True,
            sc_high_min_delta=55,
            sc_high_max_delta=55,
            lc_mid_min_offset=22,
            lc_mid_max_offset=22,
        )
        front_quotes = [
            quote_with_theta("2027-01-15", 5200, 55, 35, 36, -0.01),
            quote_with_theta("2027-01-15", 6000, 8, 3, 4, -0.01),
        ]
        back_quotes = [quote_with_theta("2027-04-16", 5600, 33, 12, 13, -0.30)]
        rejection_reasons: dict[str, int] = {}

        candidates = build_candidates_from_quotes(
            "SPX",
            {"2027-01-15": front_quotes, "2027-04-16": back_quotes},
            {"2027-01-15": 253, "2027-04-16": 344},
            settings,
            rejection_reasons=rejection_reasons,
        )

        self.assertEqual(candidates, [])
        self.assertEqual(rejection_reasons["negative_or_zero_theta"], 1)

    def test_rejection_reasons_count_missing_low_short_call(self) -> None:
        settings = ScanSettings(
            sc_high_min_delta=55,
            sc_high_max_delta=55,
            lc_mid_min_offset=22,
            lc_mid_max_offset=22,
        )
        rejection_reasons: dict[str, int] = {}

        candidates = build_candidates_from_quotes(
            "SPX",
            {
                "2027-01-15": [quote("2027-01-15", 5200, 55, 35, 36)],
                "2027-04-16": [quote("2027-04-16", 5600, 33, 12, 13)],
            },
            {"2027-01-15": 253, "2027-04-16": 344},
            settings,
            rejection_reasons=rejection_reasons,
        )

        self.assertEqual(candidates, [])
        self.assertEqual(rejection_reasons["no_sc_low"], 1)


if __name__ == "__main__":
    unittest.main()
