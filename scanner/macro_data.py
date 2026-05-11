"""Macro modelling inputs for risk-chart assumptions.

These helpers are intentionally isolated from scanner candidate generation.
They are ONLY used for optional risk-chart modelling assumptions.

Design goals:
- safe fallbacks
- deterministic defaults
- no scan failures if endpoints fail
- no dependency on IBKR permissions
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

CACHE_DIR = Path(".scanner_cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / "macro_cache.json"
CACHE_TTL_SECONDS = 60 * 60 * 24

DEFAULT_RISK_FREE_RATE = 0.045
DEFAULT_DIVIDEND_YIELD = 0.013


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def _save_cache(payload: dict) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass


def _format_timestamp(timestamp: float | None) -> str:
    if timestamp is None:
        return ""
    try:
        return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
    except Exception:
        return ""


def _is_cache_valid(timestamp: float | None) -> bool:
    if timestamp is None:
        return False
    return (time.time() - timestamp) < CACHE_TTL_SECONDS


def fetch_treasury_rate() -> float:
    """Fetch a reasonable long-duration risk-free proxy.

    Uses the US Treasury 10Y yield from the public treasury API.
    Falls back safely to cache/defaults.
    """
    cache = _load_cache()
    cached = cache.get("risk_free_rate")
    cached_ts = cache.get("risk_free_rate_ts")

    if _is_cache_valid(cached_ts) and isinstance(cached, (int, float)):
        return float(cached)

    try:
        url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/avg_interest_rates"
        with urlopen(url, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))

        rows = payload.get("data", [])
        ten_year_rows = [
            row for row in rows
            if row.get("security_desc", "").lower().startswith("10-year")
        ]
        if ten_year_rows:
            latest = ten_year_rows[0]
            value = float(latest["avg_interest_rate_amt"]) / 100.0
            cache["risk_free_rate"] = value
            cache["risk_free_rate_ts"] = time.time()
            _save_cache(cache)
            return value
    except Exception:
        pass

    if isinstance(cached, (int, float)):
        return float(cached)
    return DEFAULT_RISK_FREE_RATE


def fetch_spy_dividend_yield() -> float:
    """Fetch an approximate SPX dividend yield proxy.

    Uses a stable fallback-first approach.
    This affects ONLY risk-chart modelling assumptions.
    """
    cache = _load_cache()
    cached = cache.get("dividend_yield")
    cached_ts = cache.get("dividend_yield_ts")

    if _is_cache_valid(cached_ts) and isinstance(cached, (int, float)):
        return float(cached)

    # Intentionally conservative and stable.
    # Avoid adding large third-party dependencies or brittle scraping.
    value = DEFAULT_DIVIDEND_YIELD

    cache["dividend_yield"] = value
    cache["dividend_yield_ts"] = time.time()
    _save_cache(cache)
    return value


def resolve_macro_inputs(
    auto_fetch: bool,
    manual_risk_free_rate: float,
    manual_dividend_yield: float,
) -> tuple[float, float, str]:
    """Resolve modelling assumptions safely.

    Returns:
        risk_free_rate,
        dividend_yield,
        source_label
    """
    if not auto_fetch:
        return (
            manual_risk_free_rate,
            manual_dividend_yield,
            "manual",
        )

    return (
        fetch_treasury_rate(),
        fetch_spy_dividend_yield(),
        "auto_fetch",
    )


def macro_cache_status() -> dict[str, str]:
    """Return display-only cache timestamps for the Streamlit sidebar."""
    cache = _load_cache()
    return {
        "risk_free_rate_updated_at": _format_timestamp(cache.get("risk_free_rate_ts")),
        "dividend_yield_updated_at": _format_timestamp(cache.get("dividend_yield_ts")),
    }
