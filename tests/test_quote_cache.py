from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from scanner.models import OptionQuote, ScanSettings
from scanner.quote_cache import (
    cache_scan_result,
    load_cache_underlying_price,
    load_cache_sdex_snapshot,
    load_cached_quotes,
    quote_cache_stats,
    save_cache_underlying_price,
    save_cache_sdex_snapshot,
    save_quotes,
)


def make_quote(
    expiry: str,
    strike: float,
    delta: float | None = 10.0,
    bid: float = 1.0,
    ask: float = 2.0,
) -> OptionQuote:
    return OptionQuote(
        symbol="SPX",
        expiry=expiry,
        strike=strike,
        right="C",
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2,
        delta=delta,
        theta=-0.01,
        vega=0.25,
        gamma=0.001,
        implied_vol=0.22,
    )


class QuoteCacheTests(unittest.TestCase):
    def test_save_and_load_cached_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "quotes.db")
            save_quotes("SPX", [make_quote("20270115", 6000)], db_path=db_path)

            quotes = load_cached_quotes("SPX", "20270115", max_age_seconds=3600, db_path=db_path)

            self.assertEqual(len(quotes), 1)
            self.assertEqual(quotes[0].strike, 6000)
            self.assertEqual(quotes[0].delta, 10.0)
            self.assertEqual(quotes[0].implied_vol, 0.22)

    def test_load_cached_quotes_filters_stale_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "quotes.db")
            old_time = datetime.now() - timedelta(hours=3)
            save_quotes("SPX", [make_quote("20270115", 6000)], db_path=db_path, timestamp=old_time)

            quotes = load_cached_quotes("SPX", "20270115", max_age_seconds=60, db_path=db_path)

            self.assertEqual(quotes, [])

    def test_cache_stats_counts_expiries_and_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "quotes.db")
            save_quotes("SPX", [make_quote("20270115", 6000), make_quote("20270416", 6200)], db_path=db_path)

            stats = quote_cache_stats("SPX", db_path=db_path)

            self.assertEqual(stats["quote_count"], 2)
            self.assertEqual(stats["expiry_count"], 2)

    def test_save_and_load_cache_underlying_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "quotes.db")

            save_cache_underlying_price("SPX", 7275.5, db_path=db_path)

            self.assertEqual(load_cache_underlying_price("SPX", max_age_seconds=3600, db_path=db_path), 7275.5)
            stats = quote_cache_stats("SPX", db_path=db_path)
            self.assertEqual(stats["underlying_price"], 7275.5)

    def test_save_and_load_cache_sdex_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "quotes.db")

            save_cache_sdex_snapshot("SPX", 71.25, "IBKR SDEX previous close", db_path=db_path)

            value, source = load_cache_sdex_snapshot("SPX", max_age_seconds=3600, db_path=db_path)
            self.assertEqual(value, 71.25)
            self.assertEqual(source, "IBKR SDEX previous close")
            stats = quote_cache_stats("SPX", db_path=db_path)
            self.assertEqual(stats["sdex_value"], 71.25)
            self.assertEqual(stats["sdex_source"], "IBKR SDEX previous close")

    def test_cache_scan_result_builds_from_cached_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "quotes.db")
            front = [
                make_quote("20270115", 5200, 55, bid=35, ask=36),
                make_quote("20270115", 5900, 10, bid=5, ask=6),
                make_quote("20270115", 6000, 7, bid=3, ask=4),
            ]
            back = [make_quote("20270416", 5600, 33, bid=12, ask=13)]
            save_quotes("SPX", front + back, db_path=db_path)
            save_cache_underlying_price("SPX", 7275.5, db_path=db_path)
            save_cache_sdex_snapshot("SPX", 71.25, "IBKR SDEX previous close", db_path=db_path)

            result = cache_scan_result(ScanSettings(), max_age_seconds=3600, db_path=db_path)

            self.assertGreaterEqual(len(result.candidates), 1)
            self.assertEqual(result.underlying_price, 7275.5)
            self.assertEqual(result.sdex_value, 71.25)
            self.assertEqual(result.sdex_source, "IBKR SDEX previous close")
            self.assertTrue(result.warnings == [] or isinstance(result.warnings[0], str))


if __name__ == "__main__":
    unittest.main()
