from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from scanner.config import ibkr_config, load_config, settings_from_config
from scanner.collector import QuoteCacheCollector
from scanner.database import save_scan_history
from scanner.dte_neighborhoods import dte_neighborhood_rows
from scanner.efficiency import efficiency_rows
from scanner.export import candidates_to_csv
from scanner.ibkr_client import IBKRClient, resolve_underlying_price, runtime_diagnostics, summarize_chain
from scanner.macro_data import macro_cache_status, resolve_macro_inputs
from scanner.market_regime import market_regime_rows
from scanner.mock_data import mock_scan
from scanner.models import BatmanCandidate, ScanResult, ScanSettings
from scanner.option_chain import scan_from_quote_fetcher
from scanner.presets import apply_strategy_preset
from scanner.quote_cache import cache_scan_result, quote_cache_stats
from scanner.risk_chart import candidate_risk_frame


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
                "position delta": round(candidate.position_delta, 2),
                "position theta": round(candidate.position_theta, 2),
                "position vega": round(candidate.position_vega, 2),
                "position gamma": round(candidate.position_gamma, 4),
                "D/T ratio": round(candidate.delta_theta_ratio, 4),
                "estimated credit": round(candidate.entry_credit, 2),
                "spread penalty": round(candidate.spread_penalty, 4),
                "delta score": round(candidate.delta_score, 4),
                "theta score": round(candidate.theta_score, 4),
                "credit score": round(candidate.credit_score, 4),
                "D/T score": round(candidate.delta_theta_ratio_score, 4),
                "DTE anchor score": round(candidate.dte_anchor_score, 4),
                "liquidity score": round(candidate.liquidity_score, 4),
                "shape quality score": round(candidate.shape_quality_score, 4),
            }
        )
    return rows


def benchmark_candidate_rows(candidates: list[BatmanCandidate], label: str) -> list[dict[str, Any]]:
    """Return compact benchmark rows for scanner-vs-reference comparison."""
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rows.append(
            {
                "benchmark": label,
                "rank": candidate.rank,
                "front expiry": candidate.front_expiry,
                "front DTE": candidate.front_dte,
                "back expiry": candidate.back_expiry,
                "back DTE": candidate.back_dte,
                "SC_High": f"{candidate.sc_high.quote.strike:g} d={candidate.sc_high.quote.delta or 0:.2f}",
                "LC_Mid": f"{candidate.lc_mid.quote.strike:g} d={candidate.lc_mid.quote.delta or 0:.2f}",
                "SC_Low": f"{candidate.sc_low.quote.strike:g} d={candidate.sc_low.quote.delta or 0:.2f}",
                "credit": round(candidate.entry_credit, 2),
                "position delta": round(candidate.position_delta, 2),
                "position theta": round(candidate.position_theta, 2),
                "D/T ratio": round(candidate.delta_theta_ratio, 4),
                "score": round(candidate.score, 4),
            }
        )
    return rows


def rejection_reason_rows(result: ScanResult) -> list[dict[str, Any]]:
    """Return rejection diagnostics sorted by most common reason."""
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(result.rejection_reasons.items(), key=lambda item: item[1], reverse=True)
    ]


def show_market_regime(result: ScanResult) -> None:
    """Show the scanner-only market regime snapshot."""
    rows = market_regime_rows(result.market_regime)
    if rows:
        with st.expander("Market Regime", expanded=False):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_dte_neighborhoods(result: ScanResult) -> None:
    """Show ranked front/back DTE neighborhoods from the scan result."""
    rows = dte_neighborhood_rows(result.dte_neighborhoods)
    if rows:
        with st.expander("DTE Neighborhoods", expanded=False):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_candidate_efficiency(result: ScanResult) -> None:
    """Show pre-entry candidate efficiency metrics."""
    rows = efficiency_rows(result.candidates)
    if rows:
        with st.expander("Candidate Efficiency", expanded=False):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def macro_assumption_rows(
    risk_free_rate: float,
    dividend_yield: float,
    source_label: str,
    last_refresh: str,
) -> list[dict[str, str]]:
    """Return risk-chart modelling assumptions in a UI-friendly format."""
    return [
        {
            "assumption": "Risk-free rate",
            "value": f"{risk_free_rate * 100:.2f}%",
            "source": source_label,
            "last refresh": last_refresh,
        },
        {
            "assumption": "Dividend yield",
            "value": f"{dividend_yield * 100:.2f}%",
            "source": source_label,
            "last refresh": last_refresh,
        },
    ]


def candidate_picker_label(candidate: BatmanCandidate) -> str:
    """Return a compact label for quickly switching between ranked candidates."""
    strikes = (
        f"{candidate.sc_high.quote.strike:g}/"
        f"{candidate.lc_mid.quote.strike:g}/"
        f"{candidate.sc_low.quote.strike:g}"
    )
    return (
        f"#{candidate.rank} | score {candidate.score:.4f} | "
        f"{candidate.front_dte}d/{candidate.back_dte}d | "
        f"{strikes} | credit {candidate.entry_credit:.2f} | "
        f"delta {candidate.position_delta:.2f} | "
        f"theta {candidate.position_theta:.2f}"
    )


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
                "min usable strike": counts.get("min_usable_strike", 0),
                "max usable strike": counts.get("max_usable_strike", 0),
                "min usable delta": round(counts.get("min_usable_delta", 0), 2),
                "max usable delta": round(counts.get("max_usable_delta", 0), 2),
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
    risk_chart_spot = st.sidebar.number_input(
        "Risk chart spot price",
        min_value=0.0,
        value=float(manual_underlying_price),
        step=1.0,
        help="Used for selected-candidate risk charts when IBKR spot is unavailable.",
    )

    st.sidebar.header("Scanner")
    symbol = st.sidebar.text_input("Underlying symbol", value=defaults.symbol).upper()
    exchange = st.sidebar.text_input("Exchange", value=defaults.exchange)
    currency = st.sidebar.text_input("Currency", value=defaults.currency)
    strategy_preset_options = {
        "Dynamic Batman grid": "dynamic_batman_grid",
        "Buddy 54-32-3": "buddy_54_32_3",
        "Live conservative": "live_conservative",
    }
    default_preset_label = next(
        (label for label, value in strategy_preset_options.items() if value == defaults.strategy_preset),
        "Dynamic Batman grid",
    )
    strategy_preset_label = st.sidebar.selectbox(
        "Strategy preset",
        options=list(strategy_preset_options.keys()),
        index=list(strategy_preset_options.keys()).index(default_preset_label),
    )
    min_front_dte = st.sidebar.number_input("Min front DTE", min_value=1, value=defaults.min_front_dte)
    max_dte = st.sidebar.number_input("Max DTE", min_value=1, value=defaults.max_dte)
    min_dte_gap = st.sidebar.number_input("Min front/back DTE gap", min_value=1, value=defaults.min_dte_gap)
    max_dte_gap = st.sidebar.number_input("Max front/back DTE gap", min_value=1, value=defaults.max_dte_gap)
    expiry_pairing_options = {
        "All valid pairs": "all_pairs",
        "Adjacent only": "adjacent_only",
        "First valid far": "first_valid_far",
    }
    default_pairing_label = next(
        (label for label, value in expiry_pairing_options.items() if value == defaults.expiry_pairing_mode),
        "All valid pairs",
    )
    expiry_pairing_label = st.sidebar.selectbox(
        "Expiry pairing mode",
        options=list(expiry_pairing_options.keys()),
        index=list(expiry_pairing_options.keys()).index(default_pairing_label),
    )
    dte_selection_options = {
        "Range": "range",
        "Target front/back": "target",
    }
    default_dte_selection_label = next(
        (label for label, value in dte_selection_options.items() if value == defaults.dte_selection_mode),
        "Range",
    )
    dte_selection_label = st.sidebar.selectbox(
        "DTE selection mode",
        options=list(dte_selection_options.keys()),
        index=list(dte_selection_options.keys()).index(default_dte_selection_label),
    )
    front_target_dte = st.sidebar.number_input("Front target DTE", min_value=1, value=defaults.front_target_dte)
    back_target_dte = st.sidebar.number_input("Back target DTE", min_value=1, value=defaults.back_target_dte)
    dte_tolerance = st.sidebar.number_input("Target DTE tolerance", min_value=0, value=defaults.dte_tolerance)

    st.sidebar.header("Delta Targets")
    sc_high_min_delta = st.sidebar.number_input("SC_High min delta", min_value=1, max_value=100, value=defaults.sc_high_min_delta)
    sc_high_max_delta = st.sidebar.number_input("SC_High max delta", min_value=1, max_value=100, value=defaults.sc_high_max_delta)
    sc_high_delta_step = st.sidebar.number_input("SC_High delta step", min_value=1, max_value=20, value=defaults.sc_high_delta_step)
    lc_mid_min_offset = st.sidebar.number_input("LC_Mid min offset", min_value=1, max_value=50, value=defaults.lc_mid_min_offset)
    lc_mid_max_offset = st.sidebar.number_input("LC_Mid max offset", min_value=1, max_value=50, value=defaults.lc_mid_max_offset)
    lc_mid_offset_step = st.sidebar.number_input("LC_Mid offset step", min_value=1, max_value=20, value=defaults.lc_mid_offset_step)
    target_trade_delta = st.sidebar.slider("Target total trade delta", min_value=1.0, max_value=5.0, value=float(defaults.target_trade_delta), step=0.5)
    min_credit = st.sidebar.number_input("Minimum entry credit", value=float(defaults.min_credit), step=0.5)
    require_positive_theta = st.sidebar.checkbox("Require positive theta", value=defaults.require_positive_theta)
    max_results = st.sidebar.number_input("Max results", min_value=1, max_value=100, value=defaults.max_results)
    scoring_options = {
        "Theta-first Batman": "theta_first",
        "Balanced delta/credit": "balanced",
        "Delta/theta ratio": "delta_theta_ratio",
    }
    default_scoring_label = next(
        (label for label, value in scoring_options.items() if value == defaults.scoring_mode),
        "Theta-first Batman",
    )
    scoring_mode_label = st.sidebar.selectbox(
        "Scoring mode",
        options=list(scoring_options.keys()),
        index=list(scoring_options.keys()).index(default_scoring_label),
        help="Theta-first ranks mostly by position theta, then credit. Balanced keeps the original delta/credit/DTE score.",
    )

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
    upside_strike_multiplier = st.sidebar.number_input(
        "Upside strike multiplier",
        min_value=1.05,
        max_value=2.50,
        value=float(defaults.upside_strike_multiplier),
        step=0.05,
        help="Upper strike collection bound as a multiple of spot. Higher values include farther OTM calls.",
    )
    strike_increment_options = {
        "Any strike": 0,
        "5-point": 5,
        "10-point": 10,
        "25-point": 25,
    }
    default_strike_increment_label = next(
        (label for label, value in strike_increment_options.items() if value == defaults.strike_increment),
        "Any strike",
    )
    strike_increment_label = st.sidebar.selectbox(
        "Strike increment",
        options=list(strike_increment_options.keys()),
        index=list(strike_increment_options.keys()).index(default_strike_increment_label),
        help="Optional strike grid filter for cleaner OptionNet modelling and faster live quote collection.",
    )
    market_data_batch_size = st.sidebar.number_input(
        "Market data batch size",
        min_value=10,
        max_value=95,
        value=min(defaults.market_data_batch_size, 95),
        help="Maximum simultaneous option market-data requests. Keep below your IBKR line limit.",
    )

    st.sidebar.header("Risk Chart Assumptions")
    auto_fetch_macro = st.sidebar.checkbox(
        "Auto-fetch macro assumptions",
        value=False,
        help="Optional. Used only for risk chart modelling, never for candidate generation or IBKR orders.",
    )
    manual_risk_free_rate_pct = st.sidebar.number_input(
        "Risk-free rate %",
        min_value=0.0,
        max_value=20.0,
        value=float(defaults.risk_free_rate * 100),
        step=0.05,
    )
    manual_dividend_yield_pct = st.sidebar.number_input(
        "Dividend yield %",
        min_value=0.0,
        max_value=10.0,
        value=float(defaults.dividend_yield * 100),
        step=0.05,
    )
    try:
        risk_free_rate, dividend_yield, macro_source = resolve_macro_inputs(
            auto_fetch=auto_fetch_macro,
            manual_risk_free_rate=float(manual_risk_free_rate_pct) / 100,
            manual_dividend_yield=float(manual_dividend_yield_pct) / 100,
        )
    except Exception as error:
        risk_free_rate = float(manual_risk_free_rate_pct) / 100
        dividend_yield = float(manual_dividend_yield_pct) / 100
        macro_source = "manual_fallback"
        st.sidebar.warning(f"Macro assumptions fallback: {error}")
    macro_status = macro_cache_status()
    macro_last_refresh = max(
        macro_status.get("risk_free_rate_updated_at", ""),
        macro_status.get("dividend_yield_updated_at", ""),
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
        scoring_mode=scoring_options[scoring_mode_label],
        expiry_pairing_mode=expiry_pairing_options[expiry_pairing_label],
        require_positive_theta=bool(require_positive_theta),
        upside_strike_multiplier=float(upside_strike_multiplier),
        strike_increment=strike_increment_options[strike_increment_label],
        strategy_preset=strategy_preset_options[strategy_preset_label],
        dte_selection_mode=dte_selection_options[dte_selection_label],
        front_target_dte=int(front_target_dte),
        back_target_dte=int(back_target_dte),
        dte_tolerance=int(dte_tolerance),
        risk_free_rate=float(risk_free_rate),
        dividend_yield=float(dividend_yield),
    )
    settings = apply_strategy_preset(settings)
    return settings, {
        "host": host,
        "port": int(port),
        "client_id": int(client_id),
        "market_data_type": market_data_type,
        "manual_underlying_price": float(manual_underlying_price),
        "risk_chart_spot": float(risk_chart_spot),
        "use_quote_cache": bool(use_quote_cache),
        "cache_max_age_seconds": int(cache_max_age_minutes) * 60,
        "macro_source": macro_source,
        "macro_last_refresh": macro_last_refresh,
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
                    "position_delta": round(candidate.position_delta, 2),
                    "position_theta": round(candidate.position_theta, 2),
                    "position_vega": round(candidate.position_vega, 2),
                    "position_gamma": round(candidate.position_gamma, 4),
                    "delta_theta_ratio": round(candidate.delta_theta_ratio, 4),
                    "delta_score": round(candidate.delta_score, 4),
                    "theta_score": round(candidate.theta_score, 4),
                    "credit_score": round(candidate.credit_score, 4),
                    "delta_theta_ratio_score": round(candidate.delta_theta_ratio_score, 4),
                    "dte_anchor_score": round(candidate.dte_anchor_score, 4),
                    "liquidity_score": round(candidate.liquidity_score, 4),
                    "shape_quality_score": round(candidate.shape_quality_score, 4),
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
                        "implied_vol": quote.implied_vol,
                    }
                )
            st.dataframe(pd.DataFrame(leg_rows), use_container_width=True, hide_index=True)


def selected_candidate_detail_rows(candidate: BatmanCandidate) -> list[dict[str, Any]]:
    """Build leg rows for the currently selected candidate."""
    rows: list[dict[str, Any]] = []
    for leg in candidate.legs:
        quote = leg.quote
        rows.append(
            {
                "leg": leg.name,
                "action": leg.action,
                "quantity": leg.quantity,
                "expiry": quote.expiry,
                "strike": quote.strike,
                "bid": quote.bid,
                "ask": quote.ask,
                "mid": quote.mid,
                "delta": quote.delta,
                "theta": quote.theta,
                "vega": quote.vega,
                "gamma": quote.gamma,
                "implied_vol": quote.implied_vol,
            }
        )
    return rows


def selected_candidate_summary(candidate: BatmanCandidate) -> str:
    """Return a one-line summary that does not push the chart down."""
    return (
        f"Score {candidate.score:.4f} | "
        f"Credit {candidate.entry_credit:.2f} | "
        f"Delta {candidate.position_delta:.2f} | "
        f"Pos Theta {candidate.position_theta:.2f} | "
        f"D/T {candidate.delta_theta_ratio:.4f} | "
        f"Vega {candidate.position_vega:.2f}"
    )


def risk_chart_spot_price(
    manual_chart_price: float | None,
    result_underlying_price: float | None,
    manual_underlying_price: float | None,
) -> float:
    """Choose the best available spot price for the risk chart."""
    return float(manual_chart_price or result_underlying_price or manual_underlying_price or 0.0)


def show_risk_chart(candidate: BatmanCandidate, spot_price: float, settings: ScanSettings) -> None:
    """Render an approximate OptionNet-style risk chart for one candidate."""
    frame = candidate_risk_frame(
        candidate,
        spot_price=spot_price,
        price_points=121,
        projection_count=5,
        risk_free_rate=settings.risk_free_rate,
        dividend_yield=settings.dividend_yield,
    )
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.06,
        subplot_titles=("Projected PnL", "Greeks at T+0"),
    )

    for label, group in frame.groupby("projection_label"):
        fig.add_trace(
            go.Scatter(x=group["underlying_price"], y=group["pnl"], mode="lines", name=label),
            row=1,
            col=1,
        )

    current_greeks = frame[frame["projection_day"] == 0]
    for greek in ["delta", "gamma", "theta", "vega"]:
        values = current_greeks[greek] / 100 if greek == "vega" else current_greeks[greek]
        label = "vega/100" if greek == "vega" else greek
        fig.add_trace(
            go.Scatter(x=current_greeks["underlying_price"], y=values, mode="lines", name=label),
            row=2,
            col=1,
        )

    fig.add_vline(x=spot_price, line_dash="dash", line_color="white")
    fig.add_hline(y=0, row=1, col=1, line_color="gray")
    fig.update_layout(
        height=640,
        template="plotly_dark",
        margin={"l": 40, "r": 20, "t": 36, "b": 34},
        legend={"orientation": "h"},
    )
    fig.update_xaxes(title_text="Underlying Price", row=2, col=1)
    fig.update_yaxes(title_text="Profit/Loss", row=1, col=1)
    fig.update_yaxes(title_text="Greeks", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)


def show_results_workspace(
    result: ScanResult,
    spot_price: float,
    risk_settings: ScanSettings,
    macro_source: str,
    macro_last_refresh: str,
) -> None:
    """Show candidate list and selected risk chart side by side."""
    left, right = st.columns([0.34, 0.66], gap="large")
    label_by_rank = {candidate.rank: candidate_picker_label(candidate) for candidate in result.candidates}

    with left:
        st.subheader("Candidates")
        selected_rank = st.radio(
            "Ranked setups",
            options=[candidate.rank for candidate in result.candidates],
            format_func=lambda rank: label_by_rank[rank],
            label_visibility="collapsed",
        )

        with st.expander("Full Candidate Table", expanded=False):
            st.dataframe(pd.DataFrame(candidate_rows(result.candidates)), use_container_width=True, hide_index=True)

        csv_text = candidates_to_csv(result.candidates)
        st.download_button(
            "Export top candidates to CSV",
            data=csv_text,
            file_name=f"{result.candidates[0].symbol.lower()}_batman_candidates.csv",
            mime="text/csv",
        )

    selected_candidate = next(candidate for candidate in result.candidates if candidate.rank == selected_rank)
    with right:
        st.markdown(f"**Risk Chart** · {selected_candidate_summary(selected_candidate)}")
        if spot_price > 0:
            show_risk_chart(selected_candidate, float(spot_price), risk_settings)
        else:
            st.info("Enter a risk chart spot price in the sidebar to view projected PnL and Greeks.")

        with st.expander("Risk Chart Assumptions", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    macro_assumption_rows(
                        risk_settings.risk_free_rate,
                        risk_settings.dividend_yield,
                        macro_source,
                        macro_last_refresh,
                    )
                ),
                use_container_width=True,
                hide_index=True,
            )

        benchmark_rows: list[dict[str, Any]] = []
        if result.canonical_candidate is not None:
            benchmark_rows.extend(benchmark_candidate_rows([result.canonical_candidate], "canonical 54/32"))
        if result.sweep_candidates:
            benchmark_rows.extend(benchmark_candidate_rows(result.sweep_candidates, "constrained sweep"))
        if benchmark_rows:
            with st.expander("Benchmark Comparison", expanded=False):
                st.dataframe(pd.DataFrame(benchmark_rows), use_container_width=True, hide_index=True)

        with st.expander("Selected Candidate Legs", expanded=True):
            st.dataframe(
                pd.DataFrame(selected_candidate_detail_rows(selected_candidate)),
                use_container_width=True,
                hide_index=True,
            )


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
        result.underlying_price = underlying_price
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
                "underlying_price": cache_stats["underlying_price"],
                "underlying_price_updated_at": cache_stats["underlying_price_updated_at"],
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
            if result.rejection_reasons:
                st.write("Rejection reasons")
                st.dataframe(pd.DataFrame(rejection_reason_rows(result)), use_container_width=True, hide_index=True)

    if not result.candidates:
        st.error("No candidates matched the filters.")
        st.info(
            "If usable quotes are near zero, wait for market data/Greeks or check subscriptions. "
            "If usable quotes exist, loosen filters such as min credit, DTE gap, or delta ranges."
        )
        return

    spot_price = risk_chart_spot_price(
        connection.get("risk_chart_spot"),
        result.underlying_price,
        connection.get("manual_underlying_price"),
    )
    show_market_regime(result)
    show_dte_neighborhoods(result)
    show_candidate_efficiency(result)
    show_results_workspace(
        result,
        spot_price,
        settings,
        connection.get("macro_source", "manual"),
        connection.get("macro_last_refresh", ""),
    )

    with st.expander("All Candidate Details", expanded=False):
        show_candidate_details(result.candidates)


if __name__ == "__main__":
    main()
