from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from scanner.config import ibkr_config, load_config, settings_from_config
from scanner.collector import QuoteCacheCollector
from scanner.database import save_scan_history
from scanner.export import candidates_to_csv
from scanner.ibkr_client import IBKRClient, resolve_underlying_price, runtime_diagnostics, summarize_chain
from scanner.mock_data import mock_scan
from scanner.models import BatmanCandidate, ScanResult, ScanSettings
from scanner.option_chain import scan_from_quote_fetcher
from scanner.quote_cache import cache_scan_result, quote_cache_stats


st.set_page_config(page_title="Batman Scanner", layout="wide")


@st.cache_resource
def get_quote_collector() -> QuoteCacheCollector:
    return QuoteCacheCollector()


def candidate_rows(candidates: list[BatmanCandidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rows.append(
            {
                "rank": candidate.rank,
                "score": round(candidate.score, 4),
                "symbol": candidate.symbol,
                "front expiry": candidate.front_expiry,
                "front DTE": candidate.front_dte,
                "back expiry": candidate.back_expiry,
                "back DTE": candidate.back_dte,
                "SC_High strike": candidate.sc_high.quote.strike,
                "SC_High delta": round(candidate.sc_high.quote.delta or 0, 2),
                "LC_Mid strike": candidate.lc_mid.quote.strike,
                "LC_Mid delta": round(candidate.lc_mid.quote.delta or 0, 2),
                "SC_Low strike": candidate.sc_low.quote.strike,
                "SC_Low delta": round(candidate.sc_low.quote.delta or 0, 2),
                "total delta": round(candidate.total_delta, 2),
                "total theta": round(candidate.total_theta, 4),
                "total vega": round(candidate.total_vega, 4),
                "total gamma": round(candidate.total_gamma, 5),
                "estimated credit": round(candidate.entry_credit, 2),
                "spread penalty": round(candidate.spread_penalty, 4),
                "delta score": round(candidate.delta_score, 4),
                "credit score": round(candidate.credit_score, 4),
                "DTE anchor score": round(candidate.dte_anchor_score, 4),
            }
        )
    return rows


def quote_count_rows(result: ScanResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for expiry, counts in sorted(result.quote_counts_by_expiry.items()):
        total = counts.get("total", 0)
        usable = counts.get("usable", 0)
        missing = counts.get("missing", 0)
        usable_rate = usable / total if total else 0
        rows.append(
            {
                "expiry": expiry,
                "contracts returned": total,
                "usable quotes": usable,
                "missing/invalid quotes": missing,
                "missing bid/ask": counts.get("missing_bid_ask", 0),
                "invalid bid/ask": counts.get("invalid_bid_ask", 0),
                "missing delta": counts.get("missing_delta", 0),
                "usable rate": round(usable_rate, 3),
            }
        )
    return rows


def sidebar_settings(defaults: ScanSettings, ib_defaults: dict[str, Any]) -> tuple[ScanSettings, dict[str, Any]]:
    st.sidebar.header("Connection")
    host = st.sidebar.text_input("Host", value=str(ib_defaults["host"]))
    port = st.sidebar.selectbox("Port", options=[7497, 7496, 4001, 4002], index=[7497, 7496, 4001, 4002].index(int(ib_defaults["port"])))
    client_id = st.sidebar.number_input("Client ID", min_value=1, max_value=999, value=int(ib_defaults["client_id"]))
    market_data_type = st.sidebar.selectbox(
        "Market data type",
        options=["Live", "Frozen", "Delayed", "Delayed frozen"],
        index=0,
        help="Use Frozen or Delayed frozen outside market hours if your IBKR permissions allow it.",
    )
    manual_underlying_price = st.sidebar.number_input(
        "Manual underlying price",
        min_value=0.0,
        value=0.0,
        step=1.0,
        help="Optional off-hours fallback for strike filtering when IBKR cannot provide an underlying price.",
    )

    st.sidebar.header("Scanner")
    symbol = st.sidebar.text_input("Underlying symbol", value=defaults.symbol).upper()
    exchange = st.sidebar.text_input("Exchange", value=defaults.exchange)
    currency = st.sidebar.text_input("Currency", value=defaults.currency)
    min_front_dte = st.sidebar.number_input("Min front DTE", min_value=1, value=defaults.min_front_dte)
    max_dte = st.sidebar.number_input("Max DTE", min_value=1, value=defaults.max_dte)
    min_dte_gap = st.sidebar.number_input("Min front/back DTE gap", min_value=1, value=defaults.min_dte_gap)
    max_dte_gap = st.sidebar.number_input("Max front/back DTE gap", min_value=1, value=defaults.max_dte_gap)

    st.sidebar.header("Delta Targets")
    sc_high_min_delta = st.sidebar.number_input("SC_High min delta", min_value=1, max_value=100, value=defaults.sc_high_min_delta)
    sc_high_max_delta = st.sidebar.number_input("SC_High max delta", min_value=1, max_value=100, value=defaults.sc_high_max_delta)
    sc_high_delta_step = st.sidebar.number_input("SC_High delta step", min_value=1, max_value=20, value=defaults.sc_high_delta_step)
    lc_mid_min_offset = st.sidebar.number_input("LC_Mid min offset", min_value=1, max_value=50, value=defaults.lc_mid_min_offset)
    lc_mid_max_offset = st.sidebar.number_input("LC_Mid max offset", min_value=1, max_value=50, value=defaults.lc_mid_max_offset)
    lc_mid_offset_step = st.sidebar.number_input("LC_Mid offset step", min_value=1, max_value=20, value=defaults.lc_mid_offset_step)
    target_trade_delta = st.sidebar.slider("Target total trade delta", min_value=1.0, max_value=5.0, value=float(defaults.target_trade_delta), step=0.5)
    min_credit = st.sidebar.number_input("Minimum entry credit", value=float(defaults.min_credit), step=0.5)
    max_results = st.sidebar.number_input("Max results", min_value=1, max_value=100, value=defaults.max_results)

    st.sidebar.header("Quote Cache")
    use_quote_cache = st.sidebar.checkbox(
        "Run scan from quote cache",
        value=True,
        help="Use locally cached quotes for faster ranking. Refresh the cache separately from IBKR.",
    )
    cache_max_age_minutes = st.sidebar.number_input(
        "Cache max age minutes",
        min_value=1,
        max_value=1440,
        value=30,
    )
    max_contracts_per_expiry = st.sidebar.number_input(
        "Max contracts per expiry",
        min_value=20,
        max_value=250,
        value=defaults.max_contracts_per_expiry,
        help="Total strike count to inspect for each expiry.",
    )
    market_data_batch_size = st.sidebar.number_input(
        "Market data batch size",
        min_value=10,
        max_value=95,
        value=min(defaults.market_data_batch_size, 95),
        help="Maximum simultaneous option market-data requests. Keep below your IBKR line limit.",
    )

    settings = ScanSettings(
        symbol=symbol,
        exchange=exchange,
        currency=currency,
        min_front_dte=int(min_front_dte),
        max_dte=int(max_dte),
        min_dte_gap=int(min_dte_gap),
        max_dte_gap=int(max_dte_gap),
        sc_high_min_delta=int(sc_high_min_delta),
        sc_high_max_delta=int(sc_high_max_delta),
        sc_high_delta_step=int(sc_high_delta_step),
        lc_mid_min_offset=int(lc_mid_min_offset),
        lc_mid_max_offset=int(lc_mid_max_offset),
        lc_mid_offset_step=int(lc_mid_offset_step),
        target_trade_delta=float(target_trade_delta),
        min_credit=float(min_credit),
        max_results=int(max_results),
        max_contracts_per_expiry=int(max_contracts_per_expiry),
        market_data_batch_size=int(market_data_batch_size),
    )
    return settings, {
        "host": host,
        "port": int(port),
        "client_id": int(client_id),
        "market_data_type": market_data_type,
        "manual_underlying_price": float(manual_underlying_price),
        "use_quote_cache": bool(use_quote_cache),
        "cache_max_age_seconds": int(cache_max_age_minutes) * 60,
    }


def show_candidate_details(candidates: list[BatmanCandidate]) -> None:
    for candidate in candidates:
        with st.expander(f"Rank {candidate.rank}: {candidate.front_expiry} / {candidate.back_expiry} score {candidate.score:.4f}"):
            st.write(
                {
                    "entry_credit": round(candidate.entry_credit, 2),
                    "total_delta": round(candidate.total_delta, 2),
                    "total_theta": round(candidate.total_theta, 4),
                    "total_vega": round(candidate.total_vega, 4),
                    "total_gamma": round(candidate.total_gamma, 5),
                    "delta_score": round(candidate.delta_score, 4),
                    "credit_score": round(candidate.credit_score, 4),
                    "dte_anchor_score": round(candidate.dte_anchor_score, 4),
                    "spread_penalty": round(candidate.spread_penalty, 4),
                }
            )
            leg_rows = []
            for leg in candidate.legs:
                quote = leg.quote
                leg_rows.append(
                    {
                        "leg": leg.name,
                        "action": leg.action,
                        "quantity": leg.quantity,
                        "expiry": quote.expiry,
                        "strike": quote.strike,
                        "right": "CALL",
                        "bid": quote.bid,
                        "ask": quote.ask,
                        "mid": quote.mid,
                        "delta": quote.delta,
                        "theta": quote.theta,
                        "vega": quote.vega,
                        "gamma": quote.gamma,
                    }
                )
            st.dataframe(pd.DataFrame(leg_rows), use_container_width=True, hide_index=True)


def run_ibkr_scan(settings: ScanSettings, connection: dict[str, Any], status_box: Any) -> ScanResult:
    client = IBKRClient()
    try:
        status_box.info("fetching underlying")
        client.connect(connection["host"], connection["port"], connection["client_id"])
        client.set_market_data_type(connection["market_data_type"])
        underlying = client.qualify_underlying(settings)

        status_box.info("fetching option chains")
        chain = client.option_chain(underlying, settings)
        ibkr_underlying_price = client.get_underlying_price(underlying)
        underlying_price = resolve_underlying_price(
            ibkr_underlying_price,
            connection.get("manual_underlying_price"),
        )
        if underlying_price is None:
            st.warning("Could not read an underlying price. Strike filtering will use a centered chain slice.")
        elif ibkr_underlying_price is None:
            st.warning(f"Using manual underlying price {underlying_price:.2f} for strike filtering.")

        expiries = sorted(chain.expirations)

        def fetch_quotes(expiry: str):
            return client.fetch_quotes_for_expiry(expiry, chain, settings, underlying_price, status_box.info)

        result = scan_from_quote_fetcher(settings, expiries, fetch_quotes, status_box.info)
        status_box.info("saving scan")
        save_scan_history(settings, result.candidates[:20])
        return result
    finally:
        client.disconnect()


def run_ibkr_preflight(settings: ScanSettings, connection: dict[str, Any], status_box: Any) -> dict[str, Any]:
    """Connect and fetch lightweight IBKR metadata before requesting option Greeks."""
    client = IBKRClient()
    try:
        status_box.info("connecting to IBKR")
        client.connect(connection["host"], connection["port"], connection["client_id"])
        client.set_market_data_type(connection["market_data_type"])
        status_box.info("qualifying underlying")
        underlying = client.qualify_underlying(settings)
        status_box.info("fetching option-chain metadata")
        chain = client.option_chain(underlying, settings)
        status_box.info("fetching underlying price")
        ibkr_underlying_price = client.get_underlying_price(underlying)
        underlying_price = resolve_underlying_price(
            ibkr_underlying_price,
            connection.get("manual_underlying_price"),
        )
        summary = summarize_chain(chain, underlying_price, settings.max_contracts_per_expiry)
        summary["ibkr_underlying_price"] = ibkr_underlying_price
        summary["manual_underlying_price"] = connection.get("manual_underlying_price") or None
        return summary
    finally:
        client.disconnect()


def main() -> None:
    config = load_config()
    settings, connection = sidebar_settings(settings_from_config(config), ibkr_config(config))
    collector = get_quote_collector()

    st.title("Batman Scanner")
    st.caption("Scanner only. No order placement, no live trade modification.")

    with st.expander("Runtime diagnostics"):
        st.write(runtime_diagnostics())

    if "scan_result" not in st.session_state:
        st.session_state.scan_result = None
    if "ibkr_preflight_summary" not in st.session_state:
        st.session_state.ibkr_preflight_summary = None

    status_box = st.empty()
    cache_stats = quote_cache_stats(settings.symbol)
    collector_status = collector.status()
    with st.expander("Quote cache status", expanded=collector_status["running"]):
        st.write(
            {
                "symbol": settings.symbol,
                "cached_quotes": cache_stats["quote_count"],
                "cached_expiries": cache_stats["expiry_count"],
                "newest_update": cache_stats["newest_update"],
                "collector": collector_status,
            }
        )

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        connect_clicked = st.button("Connect to IBKR")
    with col2:
        preflight_clicked = st.button("Preflight IBKR")
    with col3:
        refresh_cache_clicked = st.button("Refresh Quote Cache")
    with col4:
        run_clicked = st.button("Run Scan")

    mock_mode = st.checkbox("Use MOCK DATA for UI testing", value=False)

    if connect_clicked:
        try:
            client = IBKRClient()
            client.connect(connection["host"], connection["port"], connection["client_id"])
            client.set_market_data_type(connection["market_data_type"])
            status_box.success(f"Connected to IBKR at {connection['host']}:{connection['port']} as clientId {connection['client_id']}.")
            client.disconnect()
        except Exception as error:
            status_box.warning(f"Not connected to IBKR: {error}")
            st.info("Start TWS or IB Gateway, enable API access, then retry. The app can still be tested with MOCK DATA.")

    if refresh_cache_clicked:
        started = collector.start(settings, connection)
        if started:
            status_box.success("Quote cache refresh started in the background.")
            st.info("You can keep the page open and refresh periodically to see cache progress.")
        else:
            status_box.warning("Quote cache refresh is already running.")

    if preflight_clicked:
        try:
            summary = run_ibkr_preflight(settings, connection, status_box)
            st.session_state.ibkr_preflight_summary = summary
            status_box.success("IBKR preflight finished.")
            st.write(summary)
            if summary["ibkr_underlying_price"] is None and summary["underlying_price"] is None:
                st.warning("Underlying price is unavailable because live market data is not active yet. This is common off-hours.")
            elif summary["ibkr_underlying_price"] is None:
                st.warning("IBKR price is unavailable, so the manual underlying price will be used for strike filtering.")
        except Exception as error:
            status_box.error(f"IBKR preflight failed: {error}")
            st.info("Confirm TWS/Gateway is running, API access is enabled, and the selected port matches your session.")

    if run_clicked:
        try:
            if mock_mode:
                status_box.info("building candidates from MOCK DATA")
                result = mock_scan(settings)
                save_scan_history(settings, result.candidates[:20])
            elif connection["use_quote_cache"]:
                status_box.info("building candidates from quote cache")
                result = cache_scan_result(
                    settings,
                    max_age_seconds=connection["cache_max_age_seconds"],
                )
                save_scan_history(settings, result.candidates[:20])
            else:
                result = run_ibkr_scan(settings, connection, status_box)
            st.session_state.scan_result = result
            status_box.success("Scan finished.")
        except Exception as error:
            status_box.error(f"Scan failed: {error}")
            st.info("If IBKR is not connected or Greeks are missing, use MOCK DATA to test the UI.")

    result: ScanResult | None = st.session_state.scan_result
    if result is None:
        if st.session_state.ibkr_preflight_summary is not None:
            st.info("IBKR preflight passed. Run a scan after market data is available, or enter a manual underlying price for off-hours strike filtering.")
        else:
            st.warning("IBKR is not connected yet. Use the sidebar settings, connect to TWS/IB Gateway, or enable MOCK DATA.")
        return

    if result.mock:
        st.warning("MOCK DATA results. Do not treat these as market data.")
    if result.skipped_missing_data:
        st.warning(f"Skipped {result.skipped_missing_data} contracts with missing bid/ask/model delta.")
    for warning in result.warnings:
        st.warning(warning)

    if result.quote_counts_by_expiry:
        with st.expander("Scan diagnostics", expanded=not result.candidates):
            st.dataframe(pd.DataFrame(quote_count_rows(result)), use_container_width=True, hide_index=True)

    if not result.candidates:
        st.error("No candidates matched the filters.")
        st.info(
            "If usable quotes are near zero, wait for market data/Greeks or check subscriptions. "
            "If usable quotes exist, loosen filters such as min credit, DTE gap, or delta ranges."
        )
        return

    st.subheader("Top Ranked Candidates")
    st.dataframe(pd.DataFrame(candidate_rows(result.candidates)), use_container_width=True, hide_index=True)

    csv_text = candidates_to_csv(result.candidates)
    st.download_button(
        "Export top candidates to CSV",
        data=csv_text,
        file_name=f"{settings.symbol.lower()}_batman_candidates.csv",
        mime="text/csv",
    )

    st.subheader("Candidate Details")
    show_candidate_details(result.candidates)


if __name__ == "__main__":
    main()
