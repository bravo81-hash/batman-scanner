import unittest

from app import candidate_picker_label, candidate_rows, rejection_reason_rows, risk_chart_spot_price, selected_candidate_summary
from scanner.batman import build_batman_candidate
from scanner.models import OptionQuote, ScanResult, ScanSettings


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
        theta=-0.1,
        vega=1.0,
        gamma=0.01,
    )


class AppLayoutTests(unittest.TestCase):
    def test_candidate_picker_label_includes_key_scan_fields(self) -> None:
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
            settings=ScanSettings(),
        )
        assert candidate is not None
        candidate.rank = 2
        candidate.score = 0.7654

        label = candidate_picker_label(candidate)

        self.assertIn("#2", label)
        self.assertIn("0.7654", label)
        self.assertIn("253d/344d", label)
        self.assertIn("5200", label)
        self.assertIn("5600", label)
        self.assertIn("6000", label)
        self.assertIn("credit", label)
        self.assertIn("delta", label)

    def test_selected_candidate_summary_is_single_line(self) -> None:
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
            settings=ScanSettings(),
        )
        assert candidate is not None

        summary = selected_candidate_summary(candidate)

        self.assertNotIn("\n", summary)
        self.assertIn("Score", summary)
        self.assertIn("Credit", summary)
        self.assertIn("Delta", summary)
        self.assertIn("Theta", summary)
        self.assertIn("Vega", summary)

    def test_candidate_rows_include_theta_first_ranking_fields(self) -> None:
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
            settings=ScanSettings(),
        )
        assert candidate is not None

        row = candidate_rows([candidate])[0]

        self.assertIn("position delta", row)
        self.assertIn("position theta", row)
        self.assertIn("D/T ratio", row)
        self.assertIn("theta score", row)
        self.assertIn("D/T score", row)
        self.assertIn("liquidity score", row)
        self.assertIn("shape quality score", row)

    def test_risk_chart_spot_prefers_manual_then_result_then_connection_manual(self) -> None:
        self.assertEqual(risk_chart_spot_price(10, 20, 30), 10)
        self.assertEqual(risk_chart_spot_price(0, 20, 30), 20)
        self.assertEqual(risk_chart_spot_price(0, None, 30), 30)

    def test_rejection_reason_rows_sort_by_count(self) -> None:
        result = ScanResult(
            settings=ScanSettings(),
            candidates=[],
            rejection_reasons={"no_sc_low": 2, "negative_or_zero_theta": 5},
        )

        rows = rejection_reason_rows(result)

        self.assertEqual(rows[0], {"reason": "negative_or_zero_theta", "count": 5})


if __name__ == "__main__":
    unittest.main()
