"""Convert IBKR ticker data into OptionQuote models."""

from __future__ import annotations

from math import isfinite
from typing import Any

from scanner.models import OptionQuote


def _number_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return number


def quote_from_ticker(symbol: str, contract: Any, ticker: Any) -> OptionQuote | None:
    """Build an OptionQuote from an ib_insync ticker.

    IBKR may provide Greeks through modelGreeks, bidGreeks, or askGreeks. For
    scanning, modelGreeks are preferred because they are more stable.
    """
    bid = _number_or_none(getattr(ticker, "bid", None))
    ask = _number_or_none(getattr(ticker, "ask", None))

    greeks = (
        getattr(ticker, "modelGreeks", None)
        or getattr(ticker, "bidGreeks", None)
        or getattr(ticker, "askGreeks", None)
    )
    delta = _number_or_none(getattr(greeks, "delta", None))
    # IBKR option deltas are usually decimals. The scanner displays 54, not 0.54.
    if delta is not None and abs(delta) <= 1:
        delta *= 100

    mid = (bid + ask) / 2 if bid is not None and ask is not None and ask >= bid else None
    return OptionQuote(
        symbol=symbol,
        expiry=str(getattr(contract, "lastTradeDateOrContractMonth", "")),
        strike=float(getattr(contract, "strike", 0.0)),
        right=str(getattr(contract, "right", "C")),
        bid=bid,
        ask=ask,
        mid=mid,
        delta=delta,
        theta=_number_or_none(getattr(greeks, "theta", None)),
        vega=_number_or_none(getattr(greeks, "vega", None)),
        gamma=_number_or_none(getattr(greeks, "gamma", None)),
        contract=contract,
    )
