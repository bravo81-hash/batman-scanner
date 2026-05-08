"""SQLite quote cache for faster scans.

The cache stores option quotes received from IBKR so a scan can rank candidates
from local data instead of waiting for every market-data request again.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from scanner.models import OptionQuote, ScanResult, ScanSettings
from scanner.option_chain import scan_from_quote_fetcher


DEFAULT_QUOTE_CACHE_PATH = "data/quote_cache.db"


def init_quote_cache(db_path: str = DEFAULT_QUOTE_CACHE_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS option_quote_cache (
                symbol TEXT NOT NULL,
                expiry TEXT NOT NULL,
                strike REAL NOT NULL,
                right TEXT NOT NULL,
                bid REAL,
                ask REAL,
                mid REAL,
                delta REAL,
                theta REAL,
                vega REAL,
                gamma REAL,
                implied_vol REAL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (symbol, expiry, strike, right)
            )
            """
        )
        existing_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(option_quote_cache)").fetchall()
        }
        if "implied_vol" not in existing_columns:
            connection.execute("ALTER TABLE option_quote_cache ADD COLUMN implied_vol REAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quote_cache_meta (
                symbol TEXT PRIMARY KEY,
                underlying_price REAL,
                updated_at TEXT NOT NULL
            )
            """
        )


def save_quotes(
    symbol: str,
    quotes: list[OptionQuote],
    db_path: str = DEFAULT_QUOTE_CACHE_PATH,
    timestamp: datetime | None = None,
) -> int:
    """Upsert quotes into the local cache and return the number saved."""
    init_quote_cache(db_path)
    updated_at = (timestamp or datetime.now()).isoformat(timespec="seconds")
    rows = [
        (
            symbol,
            quote.expiry,
            quote.strike,
            quote.right,
            quote.bid,
            quote.ask,
            quote.mid,
            quote.delta,
            quote.theta,
            quote.vega,
            quote.gamma,
            quote.implied_vol,
            updated_at,
        )
        for quote in quotes
    ]
    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO option_quote_cache
            (symbol, expiry, strike, right, bid, ask, mid, delta, theta, vega, gamma, implied_vol, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, expiry, strike, right) DO UPDATE SET
                bid = excluded.bid,
                ask = excluded.ask,
                mid = excluded.mid,
                delta = excluded.delta,
                theta = excluded.theta,
                vega = excluded.vega,
                gamma = excluded.gamma,
                implied_vol = excluded.implied_vol,
                updated_at = excluded.updated_at
            """,
            rows,
        )
    return len(rows)


def save_cache_underlying_price(
    symbol: str,
    underlying_price: float | None,
    db_path: str = DEFAULT_QUOTE_CACHE_PATH,
    timestamp: datetime | None = None,
) -> None:
    """Store the spot price used when refreshing the quote cache."""
    if underlying_price is None or underlying_price <= 0:
        return
    init_quote_cache(db_path)
    updated_at = (timestamp or datetime.now()).isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO quote_cache_meta (symbol, underlying_price, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                underlying_price = excluded.underlying_price,
                updated_at = excluded.updated_at
            """,
            (symbol, float(underlying_price), updated_at),
        )


def _is_fresh(updated_at: str, max_age_seconds: int) -> bool:
    try:
        timestamp = datetime.fromisoformat(updated_at)
    except ValueError:
        return False
    age = datetime.now() - timestamp
    return age.total_seconds() <= max_age_seconds


def load_cache_underlying_price(
    symbol: str,
    max_age_seconds: int,
    db_path: str = DEFAULT_QUOTE_CACHE_PATH,
) -> float | None:
    """Load a fresh cached spot price for the symbol."""
    init_quote_cache(db_path)
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT underlying_price, updated_at FROM quote_cache_meta WHERE symbol = ?",
            (symbol,),
        ).fetchone()
    if row is None:
        return None
    underlying_price, updated_at = row
    if not _is_fresh(str(updated_at), max_age_seconds):
        return None
    return float(underlying_price) if underlying_price and underlying_price > 0 else None


def load_cached_quotes(
    symbol: str,
    expiry: str,
    max_age_seconds: int,
    db_path: str = DEFAULT_QUOTE_CACHE_PATH,
) -> list[OptionQuote]:
    """Load fresh cached quotes for one expiry."""
    init_quote_cache(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT * FROM option_quote_cache
            WHERE symbol = ? AND expiry = ?
            ORDER BY strike
            """,
            (symbol, expiry),
        ).fetchall()

    quotes: list[OptionQuote] = []
    for row in rows:
        if not _is_fresh(str(row["updated_at"]), max_age_seconds):
            continue
        quotes.append(
            OptionQuote(
                symbol=str(row["symbol"]),
                expiry=str(row["expiry"]),
                strike=float(row["strike"]),
                right=str(row["right"]),
                bid=row["bid"],
                ask=row["ask"],
                mid=row["mid"],
                delta=row["delta"],
                theta=row["theta"],
                vega=row["vega"],
                gamma=row["gamma"],
                implied_vol=row["implied_vol"] if "implied_vol" in row.keys() else None,
            )
        )
    return quotes


def list_cached_expiries(
    symbol: str,
    max_age_seconds: int,
    db_path: str = DEFAULT_QUOTE_CACHE_PATH,
) -> list[str]:
    """Return expiries that have at least one fresh cached quote."""
    init_quote_cache(db_path)
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT expiry, MAX(updated_at) FROM option_quote_cache WHERE symbol = ? GROUP BY expiry",
            (symbol,),
        ).fetchall()
    return sorted(expiry for expiry, updated_at in rows if _is_fresh(str(updated_at), max_age_seconds))


def quote_cache_stats(symbol: str, db_path: str = DEFAULT_QUOTE_CACHE_PATH) -> dict[str, int | float | str | None]:
    """Return lightweight cache statistics for the UI."""
    init_quote_cache(db_path)
    with sqlite3.connect(db_path) as connection:
        quote_count = connection.execute(
            "SELECT COUNT(*) FROM option_quote_cache WHERE symbol = ?",
            (symbol,),
        ).fetchone()[0]
        expiry_count = connection.execute(
            "SELECT COUNT(DISTINCT expiry) FROM option_quote_cache WHERE symbol = ?",
            (symbol,),
        ).fetchone()[0]
        newest = connection.execute(
            "SELECT MAX(updated_at) FROM option_quote_cache WHERE symbol = ?",
            (symbol,),
        ).fetchone()[0]
        meta = connection.execute(
            "SELECT underlying_price, updated_at FROM quote_cache_meta WHERE symbol = ?",
            (symbol,),
        ).fetchone()
    return {
        "quote_count": int(quote_count or 0),
        "expiry_count": int(expiry_count or 0),
        "newest_update": newest or "",
        "underlying_price": float(meta[0]) if meta and meta[0] else None,
        "underlying_price_updated_at": meta[1] if meta else "",
    }


def cache_scan_result(
    settings: ScanSettings,
    max_age_seconds: int,
    db_path: str = DEFAULT_QUOTE_CACHE_PATH,
) -> ScanResult:
    """Build a scan result from fresh cached quotes."""
    expiries = list_cached_expiries(settings.symbol, max_age_seconds, db_path)
    if not expiries:
        return ScanResult(
            settings=settings,
            candidates=[],
            warnings=["No fresh cached quotes are available. Refresh the quote cache first."],
        )

    def fetch_quotes(expiry: str) -> list[OptionQuote]:
        return load_cached_quotes(settings.symbol, expiry, max_age_seconds, db_path)

    result = scan_from_quote_fetcher(settings, expiries, fetch_quotes)
    result.underlying_price = load_cache_underlying_price(settings.symbol, max_age_seconds, db_path)
    if not result.candidates:
        result.warnings.append("Cached quotes were available, but no candidates matched the filters.")
    return result
