import unittest
from types import SimpleNamespace
from typing import Any

import scanner.ibkr_client as ibkr_client
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


def candidate() -> Any:
    built = build_batman_candidate(
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
    assert built is not None
    return built


class FakeIB:
    def __init__(self) -> None:
        self.placed_combo: Any | None = None
        self.placed_order: Any | None = None
        self.cancelled_contract: Any | None = None
        self.live_market_price = 72.5
        self.historical_close = 71.25
        self.raise_live_market_data = False
        self.raise_trades_history = False
        self.historical_requests: list[dict[str, Any]] = []

    def qualifyContracts(self, *contracts: Any) -> list[Any]:
        qualified = []
        for index, contract in enumerate(contracts):
            contract.conId = index + 100
            qualified.append(contract)
        return qualified

    def placeOrder(self, combo: Any, order: Any) -> Any:
        self.placed_combo = combo
        self.placed_order = order
        return SimpleNamespace(order=order, orderStatus=SimpleNamespace(status="PendingSubmit"))

    def reqMktData(self, contract: Any, *_args: Any) -> Any:
        if self.raise_live_market_data:
            raise TimeoutError()
        self.requested_contract = contract
        return SimpleNamespace(marketPrice=lambda: self.live_market_price)

    def cancelMktData(self, contract: Any) -> None:
        self.cancelled_contract = contract

    def reqHistoricalData(self, contract: Any, **kwargs: Any) -> list[Any]:
        self.historical_contract = contract
        self.historical_kwargs = kwargs
        self.historical_requests.append(kwargs)
        if self.raise_trades_history and kwargs.get("whatToShow") == "TRADES":
            raise TimeoutError()
        return [SimpleNamespace(close=self.historical_close)]

    def sleep(self, _seconds: int) -> None:
        return None


class KeywordOnlyBag:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)
        self.comboLegs: list[Any] = []


class FakeOption:
    def __init__(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str,
        *,
        currency: str,
    ) -> None:
        self.symbol = symbol
        self.expiry = expiry
        self.strike = strike
        self.right = right
        self.exchange = exchange
        self.currency = currency


class FakeLimitOrder:
    def __init__(self, action: str, totalQuantity: int, lmtPrice: float) -> None:
        self.action = action
        self.totalQuantity = totalQuantity
        self.lmtPrice = lmtPrice
        self.transmit = True
        self.orderId = 123


class FakeIndex:
    def __init__(self, symbol: str, exchange: str, currency: str) -> None:
        self.symbol = symbol
        self.exchange = exchange
        self.currency = currency
        self.secType = "IND"


class IbkrClientOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_bag = ibkr_client.Bag
        self.original_option = ibkr_client.Option
        self.original_combo_leg = ibkr_client.ComboLeg
        self.original_index = ibkr_client.Index
        self.original_limit_order = ibkr_client.LimitOrder
        ibkr_client.Bag = KeywordOnlyBag
        ibkr_client.Option = FakeOption
        ibkr_client.ComboLeg = SimpleNamespace
        ibkr_client.Index = FakeIndex
        ibkr_client.LimitOrder = FakeLimitOrder

    def tearDown(self) -> None:
        ibkr_client.Bag = self.original_bag
        ibkr_client.Option = self.original_option
        ibkr_client.ComboLeg = self.original_combo_leg
        ibkr_client.Index = self.original_index
        ibkr_client.LimitOrder = self.original_limit_order

    def test_stage_held_combo_order_builds_bag_with_keyword_arguments(self) -> None:
        client = ibkr_client.IBKRClient.__new__(ibkr_client.IBKRClient)
        client.ib = FakeIB()

        payload = client.stage_held_combo_order(
            candidate(),
            ScanSettings(exchange="CBOE", currency="USD"),
            quantity=2,
            limit_credit=3.25,
        )

        self.assertEqual(client.ib.placed_combo.symbol, "SPX")
        self.assertEqual(client.ib.placed_combo.exchange, "CBOE")
        self.assertEqual(client.ib.placed_combo.currency, "USD")
        self.assertEqual(payload["order_id"], 123)
        self.assertFalse(client.ib.placed_order.transmit)

    def test_get_sdex_value_qualifies_nasdaq_index_and_returns_market_price(self) -> None:
        client = ibkr_client.IBKRClient.__new__(ibkr_client.IBKRClient)
        client.ib = FakeIB()

        sdex_value = client.get_sdex_value()

        self.assertEqual(sdex_value, 72.5)
        self.assertEqual(client.ib.requested_contract.symbol, "SDEX")
        self.assertEqual(client.ib.requested_contract.exchange, "NASDAQ")
        self.assertEqual(client.ib.requested_contract.currency, "USD")
        self.assertIs(client.ib.cancelled_contract, client.ib.requested_contract)

    def test_get_sdex_snapshot_falls_back_to_ibkr_previous_close_when_live_unavailable(self) -> None:
        client = ibkr_client.IBKRClient.__new__(ibkr_client.IBKRClient)
        client.ib = FakeIB()
        client.ib.live_market_price = None

        sdex_value, source = client.get_sdex_snapshot()

        self.assertEqual(sdex_value, 71.25)
        self.assertEqual(source, "IBKR SDEX previous close")
        self.assertEqual(client.ib.historical_contract.symbol, "SDEX")
        self.assertEqual(client.ib.historical_kwargs["durationStr"], "5 D")
        self.assertEqual(client.ib.historical_kwargs["barSizeSetting"], "1 day")

    def test_get_sdex_snapshot_still_tries_previous_close_when_live_request_times_out(self) -> None:
        client = ibkr_client.IBKRClient.__new__(ibkr_client.IBKRClient)
        client.ib = FakeIB()
        client.ib.raise_live_market_data = True

        sdex_value, source = client.get_sdex_snapshot()

        self.assertEqual(sdex_value, 71.25)
        self.assertEqual(source, "IBKR SDEX previous close")

    def test_get_sdex_snapshot_tries_midpoint_history_when_trades_history_times_out(self) -> None:
        client = ibkr_client.IBKRClient.__new__(ibkr_client.IBKRClient)
        client.ib = FakeIB()
        client.ib.live_market_price = None
        client.ib.raise_trades_history = True

        sdex_value, source = client.get_sdex_snapshot()

        self.assertEqual(sdex_value, 71.25)
        self.assertEqual(source, "IBKR SDEX previous close")
        self.assertEqual([request["whatToShow"] for request in client.ib.historical_requests], ["TRADES", "MIDPOINT"])


if __name__ == "__main__":
    unittest.main()
