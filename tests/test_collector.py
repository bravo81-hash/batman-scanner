import time
import unittest

from scanner.collector import QuoteCacheCollector
from scanner.models import ScanSettings


class CollectorTests(unittest.TestCase):
    def test_collector_runs_in_background_and_records_status(self) -> None:
        def collect(settings, connection, db_path, update_status):
            update_status(message=f"collecting {settings.symbol}")
            return 7

        collector = QuoteCacheCollector(collect_func=collect)

        started = collector.start(ScanSettings(symbol="SPX"), {"host": "127.0.0.1"}, db_path=":memory:")
        collector.wait(timeout=2)
        status = collector.status()

        self.assertTrue(started)
        self.assertFalse(status["running"])
        self.assertEqual(status["quotes_saved"], 7)
        self.assertEqual(status["error"], "")

    def test_collector_rejects_second_start_while_running(self) -> None:
        def collect(settings, connection, db_path, update_status):
            time.sleep(0.2)
            return 1

        collector = QuoteCacheCollector(collect_func=collect)

        first = collector.start(ScanSettings(), {}, db_path=":memory:")
        second = collector.start(ScanSettings(), {}, db_path=":memory:")
        collector.wait(timeout=2)

        self.assertTrue(first)
        self.assertFalse(second)


if __name__ == "__main__":
    unittest.main()
