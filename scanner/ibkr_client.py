"""Read-only IBKR client wrapper for scanner data.

This module intentionally contains no order placement methods.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from typing import Any, Callable

from scanner.contracts import days_to_expiry
from scanner.greeks import quote_from_ticker
from scanner.models import OptionQuote, ScanSettings
from scanner.option_chain import select_candidate_strikes

IB = None
Index = None
Option = None
Stock = None
util = None
IB_IMPORT_ERROR: Exception | None = None


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    """Ensure the current thread has an asyncio event loop.

    Streamlit runs app code in a script thread. That thread may not have an
    event loop, but ib_insync expects one during setup.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def _load_ib_insync() -> None:
    """Import ib_insync lazily so Streamlit can recover after dependency installs."""
    global IB, Index, Option, Stock, util, IB_IMPORT_ERROR
    if IB is not None:
        return
    try:
        ensure_event_loop()
        module = importlib.import_module("ib_insync")
        IB = module.IB
        Index = module.Index
        Option = module.Option
        Stock = module.Stock
        util = module.util
        IB_IMPORT_ERROR = None
    except Exception as error:  # pragma: no cover - depends on local environment
        IB_IMPORT_ERROR = error


def runtime_diagnostics() -> dict[str, Any]:
    """Return Python and ib_insync import details for troubleshooting the UI."""
    _load_ib_insync()
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "ib_insync_available": IB is not None,
        "ib_insync_error": repr(IB_IMPORT_ERROR) if IB_IMPORT_ERROR else "",
    }


def resolve_underlying_price(ibkr_price: float | None, manual_override: float | None) -> float | None:
    """Use live IBKR price when present, otherwise use a positive manual fallback."""
    if ibkr_price is not None and ibkr_price > 0:
        return ibkr_price
    if manual_override is not None and manual_override > 0:
        return manual_override
    return None


def market_data_type_code(label: str) -> int:
    """Map UI labels to IBKR market data type codes."""
    return {
        "Live": 1,
        "Frozen": 2,
        "Delayed": 3,
        "Delayed frozen": 4,
    }.get(label, 1)


def chunk_items(items: list[Any], batch_size: int) -> list[list[Any]]:
    """Split items into batches, keeping at least one item per batch."""
    safe_size = max(int(batch_size), 1)
    return [items[index : index + safe_size] for index in range(0, len(items), safe_size)]


class IBKRClient:
    """Small read-only wrapper around ib_insync."""

    def __init__(self) -> None:
        ensure_event_loop()
        _load_ib_insync()
        if IB is None:
            details = repr(IB_IMPORT_ERROR) if IB_IMPORT_ERROR else "unknown import error"
            raise RuntimeError(
                "ib_insync is not available in the Python environment running Streamlit. "
                f"Python: {sys.executable}. Import error: {details}"
            )
        util.startLoop()
        self.ib = IB()

    @property
    def connected(self) -> bool:
        return bool(self.ib.isConnected())

    def connect(self, host: str, port: int, client_id: int) -> None:
        self.ib.connect(host, port, clientId=client_id, timeout=10)

    def set_market_data_type(self, label: str) -> None:
        """Request live/frozen/delayed data mode from TWS/Gateway."""
        self.ib.reqMarketDataType(market_data_type_code(label))

    def disconnect(self) -> None:
        if self.connected:
            self.ib.disconnect()

    def qualify_underlying(self, settings: ScanSettings) -> Any:
        if settings.symbol.upper() in {"SPX", "NDX", "RUT"}:
            contract = Index(settings.symbol, settings.exchange, settings.currency)
        else:
            contract = Stock(settings.symbol, "SMART", settings.currency)
        qualified = self.ib.qualifyContracts(contract)
        if not qualified:
            raise RuntimeError(f"Could not qualify underlying contract for {settings.symbol}.")
        return qualified[0]

    def option_chain(self, underlying: Any, settings: ScanSettings) -> Any:
        chains = self.ib.reqSecDefOptParams(
            underlying.symbol,
            "",
            underlying.secType,
            underlying.conId,
        )
        if not chains:
            raise RuntimeError("IBKR returned no option chains for this underlying.")
        preferred = [chain for chain in chains if chain.exchange == settings.exchange]
        return preferred[0] if preferred else chains[0]

    def get_underlying_price(self, underlying: Any) -> float | None:
        ticker = self.ib.reqMktData(underlying, "", False, False)
        self.ib.sleep(2)
        price = ticker.marketPrice()
        self.ib.cancelMktData(underlying)
        return float(price) if price and price > 0 else None

    def fetch_quotes_for_expiry(
        self,
        expiry: str,
        chain: Any,
        settings: ScanSettings,
        underlying_price: float | None,
        progress: Callable[[str], None] | None = None,
    ) -> list[OptionQuote]:
        progress = progress or (lambda message: None)
        dte = days_to_expiry(expiry)
        progress(f"requesting calls for {expiry} ({dte} DTE)")

        contracts = [
            Option(settings.symbol, expiry, strike, "C", settings.exchange, currency=settings.currency)
            for strike in select_candidate_strikes(
                list(chain.strikes),
                underlying_price,
                settings.max_contracts_per_expiry,
                settings.upside_strike_multiplier,
                settings.strike_increment,
            )
        ]
        quotes: list[OptionQuote] = []
        qualified = self.ib.qualifyContracts(*contracts)
        for batch_number, batch in enumerate(chunk_items(list(qualified), settings.market_data_batch_size), start=1):
            progress(f"requesting {len(batch)} contracts for {expiry}, batch {batch_number}")
            tickers = [self.ib.reqMktData(contract, "", False, False) for contract in batch]
            self.ib.sleep(4)
            for contract, ticker in zip(batch, tickers):
                quote = quote_from_ticker(settings.symbol, contract, ticker)
                if quote is not None:
                    quotes.append(quote)
                self.ib.cancelMktData(contract)
        return quotes


def summarize_chain(chain: Any, underlying_price: float | None, selected_strike_count: int) -> dict[str, Any]:
    """Return compact option-chain metadata for the UI preflight check."""
    expirations = getattr(chain, "expirations", []) or []
    strikes = getattr(chain, "strikes", []) or []
    return {
        "exchange": getattr(chain, "exchange", ""),
        "trading_class": getattr(chain, "tradingClass", ""),
        "expiration_count": len(expirations),
        "strike_count": len(strikes),
        "selected_strikes_per_expiry": selected_strike_count,
        "underlying_price": underlying_price,
    }
