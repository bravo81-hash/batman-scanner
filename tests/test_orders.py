import unittest
from typing import Any

from scanner.batman import build_batman_candidate
from scanner.models import OptionQuote, ScanResult, ScanSettings
from scanner.orders import (
    build_held_limit_order_payload,
    can_stage_result_orders,
    combo_leg_descriptors,
    combo_leg_preview_rows,
    combo_mid_credit,
    validate_combo_order_inputs,
)


DEFAULT_MID = object()


def quote(
    expiry: str,
    strike: float,
    delta: float,
    bid: float,
    ask: float,
    mid: float | None | object = DEFAULT_MID,
) -> OptionQuote:
    actual_mid = (bid + ask) / 2 if mid is DEFAULT_MID else mid
    return OptionQuote(
        symbol="SPX",
        expiry=expiry,
        strike=strike,
        right="C",
        bid=bid,
        ask=ask,
        mid=actual_mid,  # type: ignore[arg-type]
        delta=delta,
        theta=-0.1,
        vega=1.0,
        gamma=0.01,
    )


def candidate_with_mids(
    sc_high_mid: float | None = 10.02,
    lc_mid_mid: float | None = 4.01,
    sc_low_mid: float | None = 1.26,
) -> Any:
    candidate = build_batman_candidate(
        symbol="SPX",
        front_expiry="2027-01-15",
        back_expiry="2027-04-16",
        front_dte=253,
        back_dte=344,
        sc_high=quote("2027-01-15", 5200, 55, 9.5, 10.5, sc_high_mid),
        lc_mid=quote("2027-04-16", 5600, 33, 3.5, 4.5, lc_mid_mid),
        front_quotes=[quote("2027-01-15", 6000, 8, 1.0, 1.5, sc_low_mid)],
        target_total_delta=3,
        settings=ScanSettings(),
    )
    assert candidate is not None
    return candidate


class OrderHelperTests(unittest.TestCase):
    def test_combo_mid_credit_uses_signed_leg_quantities_and_rounds_to_five_cents(self) -> None:
        candidate = candidate_with_mids(sc_high_mid=10.02, lc_mid_mid=4.01, sc_low_mid=1.26)

        credit = combo_mid_credit(candidate)

        self.assertEqual(credit, 3.25)

    def test_combo_mid_credit_requires_all_leg_mids(self) -> None:
        candidate = candidate_with_mids()
        candidate.lc_mid.quote.mid = None

        with self.assertRaisesRegex(ValueError, "LC_Mid"):
            combo_mid_credit(candidate)

    def test_validate_combo_order_inputs_requires_positive_quantity_and_limit_credit(self) -> None:
        validate_combo_order_inputs(quantity=1, limit_credit=3.25)

        with self.assertRaisesRegex(ValueError, "quantity"):
            validate_combo_order_inputs(quantity=0, limit_credit=3.25)
        with self.assertRaisesRegex(ValueError, "limit credit"):
            validate_combo_order_inputs(quantity=1, limit_credit=0)

    def test_combo_leg_preview_rows_show_one_whole_combo(self) -> None:
        candidate = candidate_with_mids()

        rows = combo_leg_preview_rows(candidate)

        self.assertEqual([row["leg"] for row in rows], ["SC_High", "LC_Mid", "SC_Low"])
        self.assertEqual([row["action"] for row in rows], ["SELL", "BUY", "SELL"])
        self.assertEqual([row["ratio"] for row in rows], [1, 2, 1])
        self.assertEqual(rows[1]["expiry"], "2027-04-16")
        self.assertEqual(rows[1]["strike"], 5600)

    def test_build_held_limit_order_payload_is_limit_and_not_transmitted(self) -> None:
        payload = build_held_limit_order_payload(quantity=2, limit_credit=3.25)

        self.assertEqual(payload.action, "BUY")
        self.assertEqual(payload.totalQuantity, 2)
        self.assertEqual(payload.orderType, "LMT")
        self.assertEqual(payload.lmtPrice, -3.25)
        self.assertFalse(payload.transmit)

    def test_can_stage_result_orders_rejects_mock_results(self) -> None:
        candidate = candidate_with_mids()

        live_result = ScanResult(settings=ScanSettings(), candidates=[candidate], mock=False)
        mock_result = ScanResult(settings=ScanSettings(), candidates=[candidate], mock=True)

        self.assertTrue(can_stage_result_orders(live_result))
        self.assertFalse(can_stage_result_orders(mock_result))

    def test_combo_leg_descriptors_match_selected_candidate_contracts(self) -> None:
        candidate = candidate_with_mids()

        descriptors = combo_leg_descriptors(candidate)

        self.assertEqual(
            descriptors,
            [
                {
                    "leg": "SC_High",
                    "action": "SELL",
                    "ratio": 1,
                    "symbol": "SPX",
                    "expiry": "2027-01-15",
                    "strike": 5200,
                    "right": "C",
                },
                {
                    "leg": "LC_Mid",
                    "action": "BUY",
                    "ratio": 2,
                    "symbol": "SPX",
                    "expiry": "2027-04-16",
                    "strike": 5600,
                    "right": "C",
                },
                {
                    "leg": "SC_Low",
                    "action": "SELL",
                    "ratio": 1,
                    "symbol": "SPX",
                    "expiry": "2027-01-15",
                    "strike": 6000,
                    "right": "C",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
