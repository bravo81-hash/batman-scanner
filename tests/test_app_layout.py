import unittest

from app import candidate_picker_label
from scanner.batman import build_batman_candidate
from scanner.models import OptionQuote, ScanSettings


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


if __name__ == "__main__":
    unittest.main()
