import unittest

from app import (
    benchmark_candidate_rows,
    build_diagnostic_input,
    candidate_decision_rows,
    candidate_diagnosis_defaults,
    candidate_order_defaults,
    candidate_picker_label,
    candidate_rows,
    diagnosis_market_points_from_rows,
    diagnosis_summary_rows,
    exception_detail,
    macro_assumption_rows,
    rejection_reason_rows,
    risk_chart_spot_price,
    sdex_regime_summary,
    selected_candidate_summary,
)
from scanner.batman import build_batman_candidate
from scanner.models import OptionQuote, ScanResult, ScanSettings
from scanner.trade_diagnostics import DiagnosticInput, diagnose


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

    def test_candidate_rows_include_phase_1_research_score_fields(self) -> None:
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
        candidate.bqi_v4_proxy = 1.23456
        candidate.bqi_v4_percentile = 80.0
        candidate.tx_score_v7_proxy = 2.34567
        candidate.tx_score_v7_percentile = 70.0
        candidate.put_skew_own = 3.45678
        candidate.sdex_percentile = 60.0
        candidate.research_quality_bucket = "strong"

        row = candidate_rows([candidate])[0]

        self.assertEqual(row["BQI v4 proxy"], 1.2346)
        self.assertEqual(row["BQI v4 percentile"], 80.0)
        self.assertEqual(row["TX_SCORE v7 proxy"], 2.3457)
        self.assertEqual(row["TX_SCORE v7 percentile"], 70.0)
        self.assertNotIn("put skew proxy", row)
        self.assertNotIn("SDEX percentile", row)
        self.assertEqual(row["research quality"], "strong")

    def test_candidate_decision_rows_are_compact_for_pre_entry_selection(self) -> None:
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
        candidate.rank = 1
        candidate.bqi_v4_percentile = 82.0
        candidate.tx_score_v7_percentile = 88.0
        candidate.research_quality_bucket = "strong"

        row = candidate_decision_rows([candidate])[0]

        self.assertEqual(row["rank"], 1)
        self.assertEqual(row["quality"], "strong")
        self.assertEqual(row["BQI %"], 82.0)
        self.assertEqual(row["TX %"], 88.0)
        self.assertIn("strikes", row)
        self.assertNotIn("put skew proxy", row)
        self.assertNotIn("SDEX percentile", row)
        self.assertNotIn("total gamma", row)

    def test_sdex_regime_summary_labels_live_regime_without_candidate_proxy(self) -> None:
        favorable = sdex_regime_summary(82.25, "IBKR SDEX")
        unavailable = sdex_regime_summary(None, "")

        self.assertEqual(favorable["SDEX"], "82.25")
        self.assertEqual(favorable["source"], "IBKR SDEX")
        self.assertEqual(favorable["regime"], "high skew")
        self.assertEqual(favorable["entry bias"], "favorable")
        self.assertEqual(unavailable["SDEX"], "unavailable")
        self.assertEqual(unavailable["entry bias"], "no SDEX read")

    def test_exception_detail_keeps_blank_timeout_errors_visible(self) -> None:
        self.assertEqual(exception_detail(TimeoutError()), "TimeoutError()")

    def test_candidate_diagnosis_defaults_prefill_selected_candidate_context(self) -> None:
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

        defaults = candidate_diagnosis_defaults(candidate)

        self.assertEqual(defaults["strategy"], "batman")
        self.assertAlmostEqual(float(defaults["entry_delta"]), candidate.position_delta)
        self.assertAlmostEqual(float(defaults["current_delta"]), candidate.position_delta)
        self.assertAlmostEqual(float(defaults["entry_vega"]), candidate.position_vega)
        self.assertAlmostEqual(float(defaults["current_vega"]), candidate.position_vega)

    def test_diagnosis_market_points_from_rows_keeps_partial_symbols(self) -> None:
        points = diagnosis_market_points_from_rows(
            {
                "spx": {"open": 7415.0, "now": 7374.0},
                "vix": {"open": 19.25, "now": None},
                "vvix": {"open": None, "now": None},
            }
        )

        self.assertEqual(points["SPX"].open, 7415.0)
        self.assertEqual(points["SPX"].now, 7374.0)
        self.assertEqual(points["VIX"].open, 19.25)
        self.assertIsNone(points["VIX"].now)
        self.assertNotIn("VVIX", points)

    def test_diagnosis_summary_rows_include_report_headline_fields(self) -> None:
        report = diagnose(
            DiagnosticInput(
                strategy="batman",
                trade_pnl=-450,
                market_points=diagnosis_market_points_from_rows(
                    {
                        "SPX": {"open": 7415.0, "now": 7374.0},
                        "VIX9D": {"open": 16.81, "now": 17.45},
                        "VIX1D": {"open": 10.51, "now": 12.07},
                    }
                ),
            )
        )

        rows = diagnosis_summary_rows(report)

        self.assertEqual(rows[0]["field"], "Verdict")
        self.assertEqual(rows[0]["value"], "red trade")
        self.assertIn({"field": "Primary driver", "value": report.primary_driver}, rows)
        self.assertIn({"field": "Bias", "value": report.bias}, rows)

    def test_diagnosis_helpers_build_report_with_incomplete_snapshot(self) -> None:
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
        defaults = candidate_diagnosis_defaults(candidate)

        diagnostic_input = build_diagnostic_input(
            strategy=str(defaults["strategy"]),
            trade_pnl=0.0,
            entry_delta=float(defaults["entry_delta"]),
            current_delta=float(defaults["current_delta"]),
            entry_vega=float(defaults["entry_vega"]),
            current_vega=float(defaults["current_vega"]),
            market_rows={"SPX": {"open": 7415.0, "now": None}},
        )
        report = diagnose(diagnostic_input)

        self.assertEqual(report.verdict, "flat trade")
        self.assertGreaterEqual(len(report.signals), 1)
        self.assertGreaterEqual(len(diagnosis_summary_rows(report)), 4)

    def test_candidate_order_defaults_use_combo_mid_credit(self) -> None:
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote("2027-01-15", 5200, 55, 9.5, 10.5),
            lc_mid=quote("2027-04-16", 5600, 33, 3.5, 4.5),
            front_quotes=[quote("2027-01-15", 6000, 8, 1.0, 1.5)],
            target_total_delta=3,
            settings=ScanSettings(),
        )
        assert candidate is not None

        defaults = candidate_order_defaults(candidate)

        self.assertEqual(defaults["quantity"], 1)
        self.assertEqual(defaults["limit_credit"], 3.25)
        self.assertIn("conservative_credit", defaults)

    def test_benchmark_candidate_rows_include_comparison_fields(self) -> None:
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
        candidate.rank = 1

        row = benchmark_candidate_rows([candidate], label="canonical")[0]

        self.assertEqual(row["benchmark"], "canonical")
        self.assertEqual(row["rank"], 1)
        self.assertIn("position delta", row)
        self.assertIn("position theta", row)
        self.assertIn("D/T ratio", row)
        self.assertIn("credit", row)

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

    def test_macro_assumption_rows_are_display_ready(self) -> None:
        rows = macro_assumption_rows(
            risk_free_rate=0.0525,
            dividend_yield=0.014,
            source_label="manual",
            last_refresh="2026-05-11T09:30:00",
        )

        self.assertEqual(rows[0]["assumption"], "Risk-free rate")
        self.assertEqual(rows[0]["value"], "5.25%")
        self.assertEqual(rows[0]["source"], "manual")
        self.assertEqual(rows[1]["assumption"], "Dividend yield")
        self.assertEqual(rows[1]["value"], "1.40%")


if __name__ == "__main__":
    unittest.main()
