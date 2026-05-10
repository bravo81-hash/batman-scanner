import unittest

from scanner.greeks import quote_from_ticker
from scanner.models import OptionQuote, ScanSettings
from scanner.option_chain import quote_diagnostic_counts, scan_from_quote_fetcher


class FakeContract:
    lastTradeDateOrContractMonth = "20270115"
    strike = 6000
    right = "C"


class FakeTicker:
    bid = None
    ask = None
    modelGreeks = None
    bidGreeks = None
    askGreeks = None


class MarketDataDiagnosticsTests(unittest.TestCase):
    def test_quote_from_ticker_keeps_invalid_quote_for_diagnostics(self) -> None:
        quote = quote_from_ticker("SPX", FakeContract(), FakeTicker())

        self.assertIsInstance(quote, OptionQuote)
        self.assertFalse(quote.has_required_data())
        self.assertEqual(quote.expiry, "20270115")
        self.assertEqual(quote.strike, 6000)

    def test_scan_result_records_quote_counts_by_expiry(self) -> None:
        settings = ScanSettings(min_front_dte=1, max_dte=700)

        def fetch_quotes(expiry: str) -> list[OptionQuote]:
            return [
                OptionQuote("SPX", expiry, 6000, "C", None, None, None, None),
                OptionQuote("SPX", expiry, 6100, "C", 1.0, 2.0, 1.5, 10.0),
            ]

        result = scan_from_quote_fetcher(settings, ["20270115"], fetch_quotes)

        self.assertEqual(result.skipped_missing_data, 1)
        self.assertEqual(result.quote_counts_by_expiry["20270115"]["total"], 2)
        self.assertEqual(result.quote_counts_by_expiry["20270115"]["usable"], 1)
        self.assertEqual(result.quote_counts_by_expiry["20270115"]["missing"], 1)

    def test_scan_result_records_rejection_reasons(self) -> None:
        settings = ScanSettings(
            min_front_dte=1,
            max_dte=700,
            min_dte_gap=1,
            sc_high_min_delta=55,
            sc_high_max_delta=55,
            lc_mid_min_offset=22,
            lc_mid_max_offset=22,
        )

        def fetch_quotes(expiry: str) -> list[OptionQuote]:
            if expiry == "20270115":
                return [OptionQuote("SPX", expiry, 5200, "C", 35, 36, 35.5, 55)]
            return [OptionQuote("SPX", expiry, 5600, "C", 12, 13, 12.5, 33)]

        result = scan_from_quote_fetcher(settings, ["20270115", "20270416"], fetch_quotes)

        self.assertEqual(result.rejection_reasons["no_sc_low"], 1)

    def test_quote_diagnostic_counts_split_missing_reasons(self) -> None:
        quotes = [
            OptionQuote("SPX", "20270115", 6000, "C", None, None, None, None),
            OptionQuote("SPX", "20270115", 6100, "C", 1.0, 2.0, 1.5, None),
            OptionQuote("SPX", "20270115", 6200, "C", 1.0, 2.0, 1.5, 10.0),
        ]

        counts = quote_diagnostic_counts(quotes)

        self.assertEqual(counts["total"], 3)
        self.assertEqual(counts["usable"], 1)
        self.assertEqual(counts["missing_bid_ask"], 1)
        self.assertEqual(counts["missing_delta"], 2)
        self.assertEqual(counts["min_usable_strike"], 6200)
        self.assertEqual(counts["max_usable_strike"], 6200)
        self.assertEqual(counts["min_usable_delta"], 10.0)
        self.assertEqual(counts["max_usable_delta"], 10.0)


if __name__ == "__main__":
    unittest.main()
