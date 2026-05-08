import asyncio
import unittest

from scanner.ibkr_client import (
    chunk_items,
    ensure_event_loop,
    market_data_type_code,
    resolve_underlying_price,
    runtime_diagnostics,
    summarize_chain,
)
from scanner.option_chain import select_candidate_strikes


class LiveScanHelperTests(unittest.TestCase):
    def test_select_candidate_strikes_limits_contract_count_around_underlying(self) -> None:
        strikes = list(range(4000, 7001, 5))

        selected = select_candidate_strikes(strikes, underlying_price=5500, max_contracts=41)

        self.assertEqual(len(selected), 41)
        self.assertIn(5500.0, selected)
        self.assertEqual(selected, sorted(selected))
        self.assertGreaterEqual(min(selected), 5500 * 0.75)
        self.assertLessEqual(max(selected), 5500 * 1.45)

    def test_select_candidate_strikes_keeps_far_otm_calls_for_batman_low_short(self) -> None:
        strikes = list(range(4000, 10001, 5))

        selected = select_candidate_strikes(strikes, underlying_price=7275, max_contracts=120)

        self.assertEqual(len(selected), 120)
        self.assertIn(7275.0, selected)
        self.assertGreaterEqual(max(selected), 9000)
        self.assertGreater(
            len([strike for strike in selected if strike > 7275]),
            len([strike for strike in selected if strike < 7275]),
        )

    def test_select_candidate_strikes_without_price_still_limits_contract_count(self) -> None:
        strikes = list(range(100, 1000, 5))

        selected = select_candidate_strikes(strikes, underlying_price=None, max_contracts=20)

        self.assertEqual(len(selected), 20)
        self.assertEqual(selected, sorted(selected))

    def test_summarize_chain_returns_readable_metadata(self) -> None:
        class Chain:
            exchange = "CBOE"
            tradingClass = "SPX"
            expirations = {"20270115", "20270416"}
            strikes = {5000, 5100, 5200}

        summary = summarize_chain(Chain(), underlying_price=5500.25, selected_strike_count=80)

        self.assertEqual(summary["exchange"], "CBOE")
        self.assertEqual(summary["trading_class"], "SPX")
        self.assertEqual(summary["expiration_count"], 2)
        self.assertEqual(summary["strike_count"], 3)
        self.assertEqual(summary["selected_strikes_per_expiry"], 80)
        self.assertEqual(summary["underlying_price"], 5500.25)

    def test_runtime_diagnostics_include_python_and_ib_status(self) -> None:
        diagnostics = runtime_diagnostics()

        self.assertIn("python_executable", diagnostics)
        self.assertIn("ib_insync_available", diagnostics)
        self.assertIn("python_version", diagnostics)

    def test_ensure_event_loop_creates_loop_when_thread_has_none(self) -> None:
        asyncio.set_event_loop(None)

        loop = ensure_event_loop()

        self.assertIs(loop, asyncio.get_event_loop())
        self.assertFalse(loop.is_closed())

    def test_resolve_underlying_price_prefers_ibkr_price(self) -> None:
        self.assertEqual(resolve_underlying_price(5501.25, 5500.0), 5501.25)

    def test_resolve_underlying_price_uses_manual_override_when_ibkr_missing(self) -> None:
        self.assertEqual(resolve_underlying_price(None, 5500.0), 5500.0)

    def test_resolve_underlying_price_ignores_empty_manual_override(self) -> None:
        self.assertIsNone(resolve_underlying_price(None, 0.0))

    def test_market_data_type_code_maps_ui_labels_to_ibkr_codes(self) -> None:
        self.assertEqual(market_data_type_code("Live"), 1)
        self.assertEqual(market_data_type_code("Frozen"), 2)
        self.assertEqual(market_data_type_code("Delayed"), 3)
        self.assertEqual(market_data_type_code("Delayed frozen"), 4)
        self.assertEqual(market_data_type_code("unknown"), 1)

    def test_chunk_items_limits_each_batch(self) -> None:
        batches = list(chunk_items(list(range(205)), 80))

        self.assertEqual([len(batch) for batch in batches], [80, 80, 45])

    def test_chunk_items_uses_one_item_minimum(self) -> None:
        batches = list(chunk_items([1, 2], 0))

        self.assertEqual(batches, [[1], [2]])


if __name__ == "__main__":
    unittest.main()
