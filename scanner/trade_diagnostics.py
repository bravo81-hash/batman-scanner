"""Strategy-agnostic trade outcome diagnostics.

This module turns an open-to-now market snapshot plus optional trade PnL/Greeks
into a deterministic explanation of why a trade is red or green.  The logic is
intentionally rules-based so the same engine can be reused from Streamlit, the
CLI, tests, and future strategy modules without relying on an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable


DEFAULT_SYMBOLS: tuple[str, ...] = (
    "SPX",
    "VIX",
    "VIX9D",
    "VIX1D",
    "VIX3M",
    "VIX6M",
    "VVIX",
)


@dataclass(frozen=True)
class MarketPoint:
    """Open and current value for one market or volatility index."""

    symbol: str
    open: float | None = None
    now: float | None = None

    @property
    def change(self) -> float | None:
        if self.open is None or self.now is None:
            return None
        return self.now - self.open

    @property
    def pct_change(self) -> float | None:
        if self.open is None or self.now is None or self.open == 0:
            return None
        return (self.now / self.open - 1.0) * 100.0


@dataclass(frozen=True)
class DiagnosticInput:
    """Inputs required to diagnose a strategy outcome."""

    strategy: str = "batman"
    as_of: str = field(default_factory=lambda: datetime.now().isoformat(timespec="minutes"))
    trade_pnl: float | None = None
    entry_delta: float | None = None
    current_delta: float | None = None
    entry_theta: float | None = None
    current_theta: float | None = None
    entry_vega: float | None = None
    current_vega: float | None = None
    notes: str = ""
    market_points: dict[str, MarketPoint] = field(default_factory=dict)


@dataclass(frozen=True)
class DiagnosticSignal:
    """One explainable rule fired by the diagnostics engine."""

    title: str
    severity: str
    detail: str
    driver: str


@dataclass(frozen=True)
class DiagnosticReport:
    """Human-readable diagnosis plus structured rows for Streamlit/CSV."""

    verdict: str
    regime: str
    primary_driver: str
    bias: str
    summary: str
    signals: list[DiagnosticSignal]
    snapshot_rows: list[dict[str, object]]
    ratio_rows: list[dict[str, object]]
    action_rows: list[dict[str, object]]


def _clean_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(" ", "")


def build_market_points(raw: dict[str, tuple[float | None, float | None]]) -> dict[str, MarketPoint]:
    """Create normalized market points from ``{symbol: (open, now)}`` input."""

    points: dict[str, MarketPoint] = {}
    for symbol, values in raw.items():
        open_value, now_value = values
        clean = _clean_symbol(symbol)
        if clean:
            points[clean] = MarketPoint(clean, open_value, now_value)
    return points


def market_snapshot_rows(points: dict[str, MarketPoint]) -> list[dict[str, object]]:
    """Return UI-friendly open/now/change rows."""

    rows: list[dict[str, object]] = []
    ordered_symbols = list(DEFAULT_SYMBOLS) + sorted(set(points) - set(DEFAULT_SYMBOLS))
    for symbol in ordered_symbols:
        point = points.get(symbol)
        if point is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "open": point.open,
                "now": point.now,
                "change": round(point.change, 4) if point.change is not None else None,
                "pct_change": round(point.pct_change, 2) if point.pct_change is not None else None,
            }
        )
    return rows


def _ratio(points: dict[str, MarketPoint], numerator: str, denominator: str) -> tuple[float | None, float | None, float | None]:
    top = points.get(numerator)
    bottom = points.get(denominator)
    if top is None or bottom is None:
        return None, None, None
    if top.open is None or bottom.open is None or top.now is None or bottom.now is None:
        return None, None, None
    if bottom.open == 0 or bottom.now == 0:
        return None, None, None
    open_ratio = top.open / bottom.open
    now_ratio = top.now / bottom.now
    return open_ratio, now_ratio, now_ratio - open_ratio


def term_structure_rows(points: dict[str, MarketPoint]) -> list[dict[str, object]]:
    """Return front/back volatility ratio rows used by calendar diagnostics."""

    pairs = [
        ("VIX1D", "VIX9D"),
        ("VIX9D", "VIX"),
        ("VIX", "VIX3M"),
        ("VIX3M", "VIX6M"),
    ]
    rows: list[dict[str, object]] = []
    for numerator, denominator in pairs:
        open_ratio, now_ratio, change = _ratio(points, numerator, denominator)
        rows.append(
            {
                "pair": f"{numerator}/{denominator}",
                "open": round(open_ratio, 3) if open_ratio is not None else None,
                "now": round(now_ratio, 3) if now_ratio is not None else None,
                "change": round(change, 3) if change is not None else None,
            }
        )
    return rows


def _point(points: dict[str, MarketPoint], symbol: str) -> MarketPoint:
    return points.get(symbol, MarketPoint(symbol))


def _pct(points: dict[str, MarketPoint], symbol: str) -> float | None:
    return _point(points, symbol).pct_change


def _change(points: dict[str, MarketPoint], symbol: str) -> float | None:
    return _point(points, symbol).change


def classify_regime(points: dict[str, MarketPoint]) -> str:
    """Classify the open-to-now market/volatility regime."""

    spx = _pct(points, "SPX")
    vix = _pct(points, "VIX")
    vix9d = _pct(points, "VIX9D")
    vix1d = _pct(points, "VIX1D")
    vix3m = _pct(points, "VIX3M")

    front_pop = any(value is not None and value >= 8.0 for value in (vix1d, vix9d))
    back_soft = vix3m is not None and vix3m <= 0.0
    spot_down = spx is not None and spx <= -0.35
    spot_up = spx is not None and spx >= 0.35
    vix_down = vix is not None and vix < 0.0
    vix_up = vix is not None and vix > 0.0

    if front_pop and back_soft:
        return "front-end vol pop / back-end vol soft"
    if spot_down and vix_down:
        return "spot down with headline VIX down"
    if spot_down and vix_up:
        return "classic risk-off selloff"
    if spot_up and vix_down:
        return "risk-on grind"
    if front_pop:
        return "short-dated event-risk vol pop"
    return "mixed or low-signal regime"


def _strategy_family(strategy: str) -> str:
    value = strategy.strip().lower().replace(" ", "_").replace("-", "_")
    if value in {"batman", "calendar", "double_calendar", "triple_calendar", "diagonal"}:
        return "calendar_like"
    if value in {"bwb", "butterfly", "broken_wing_butterfly", "fly"}:
        return "tent_like"
    if value in {"pcs", "put_credit_spread", "credit_spread"}:
        return "credit_spread"
    return "generic"


def diagnose(input_data: DiagnosticInput) -> DiagnosticReport:
    """Build a deterministic diagnosis for the supplied trade outcome."""

    points = input_data.market_points
    strategy_family = _strategy_family(input_data.strategy)
    signals: list[DiagnosticSignal] = []

    spx_pct = _pct(points, "SPX")
    vix_pct = _pct(points, "VIX")
    vix9d_pct = _pct(points, "VIX9D")
    vix1d_pct = _pct(points, "VIX1D")
    vix3m_pct = _pct(points, "VIX3M")
    vix6m_pct = _pct(points, "VIX6M")
    vvix_pct = _pct(points, "VVIX")

    _, _, vix9d_vix_change = _ratio(points, "VIX9D", "VIX")
    _, _, vix1d_vix9d_change = _ratio(points, "VIX1D", "VIX9D")
    _, _, vix_vix3m_change = _ratio(points, "VIX", "VIX3M")

    if spx_pct is not None and abs(spx_pct) >= 0.4:
        direction = "lower" if spx_pct < 0 else "higher"
        signals.append(
            DiagnosticSignal(
                title="Meaningful underlying move",
                severity="medium" if abs(spx_pct) < 0.8 else "high",
                detail=f"SPX moved {direction} by {spx_pct:.2f}% from the open, which can move the position away from its preferred zone.",
                driver="spot",
            )
        )

    if vix1d_pct is not None and vix1d_pct >= 8.0:
        signals.append(
            DiagnosticSignal(
                title="1-day volatility exploded",
                severity="high",
                detail=f"VIX1D rose {vix1d_pct:.2f}%, showing immediate tape/event risk increased intraday.",
                driver="front_vol",
            )
        )

    if vix9d_pct is not None and vix9d_pct >= 3.0:
        signals.append(
            DiagnosticSignal(
                title="Front-week volatility expanded",
                severity="high" if vix9d_pct >= 6.0 else "medium",
                detail=f"VIX9D rose {vix9d_pct:.2f}%, which is usually hostile to short-front calendar/Batman structures.",
                driver="front_vol",
            )
        )

    if vix3m_pct is not None and vix3m_pct <= -0.25:
        signals.append(
            DiagnosticSignal(
                title="Back-end volatility softened",
                severity="medium",
                detail=f"VIX3M fell {vix3m_pct:.2f}%, reducing support for longer-dated long optionality.",
                driver="back_vol",
            )
        )

    if vix6m_pct is not None and vix6m_pct <= -0.25:
        signals.append(
            DiagnosticSignal(
                title="Six-month volatility softened",
                severity="low",
                detail=f"VIX6M fell {vix6m_pct:.2f}%, confirming the back of the curve was not helping long-vega exposure.",
                driver="back_vol",
            )
        )

    if vix9d_vix_change is not None and vix9d_vix_change >= 0.04:
        signals.append(
            DiagnosticSignal(
                title="VIX9D/VIX ratio moved against calendar mean reversion",
                severity="high",
                detail=f"The VIX9D/VIX ratio increased by {vix9d_vix_change:.3f}; calendar-like trades usually prefer this ratio to mean-revert lower after entry.",
                driver="term_structure",
            )
        )

    if vix1d_vix9d_change is not None and vix1d_vix9d_change >= 0.04:
        signals.append(
            DiagnosticSignal(
                title="Very front of curve inverted higher",
                severity="high",
                detail=f"The VIX1D/VIX9D ratio increased by {vix1d_vix9d_change:.3f}, pointing to acute same-day risk pricing.",
                driver="term_structure",
            )
        )

    if vix_vix3m_change is not None and vix_vix3m_change <= -0.025 and strategy_family == "calendar_like":
        signals.append(
            DiagnosticSignal(
                title="Middle/back curve did not follow front stress",
                severity="medium",
                detail=f"The VIX/VIX3M ratio fell by {abs(vix_vix3m_change):.3f}, so the back leg likely lagged the front-end stress move.",
                driver="term_structure",
            )
        )

    if spx_pct is not None and vix_pct is not None and spx_pct < -0.3 and vix_pct < 0:
        signals.append(
            DiagnosticSignal(
                title="Unusual spot-down / VIX-down combination",
                severity="medium",
                detail=f"SPX fell {spx_pct:.2f}% while VIX fell {vix_pct:.2f}%, suggesting headline 30-day vol decay masked short-dated risk.",
                driver="vol_curve",
            )
        )

    if vvix_pct is not None and vvix_pct <= -1.0:
        signals.append(
            DiagnosticSignal(
                title="Vol-of-vol cooled",
                severity="low",
                detail=f"VVIX fell {vvix_pct:.2f}%, so convex volatility demand did not broadly expand.",
                driver="vol_of_vol",
            )
        )

    if input_data.current_delta is not None and input_data.entry_delta is not None:
        delta_shift = input_data.current_delta - input_data.entry_delta
        if abs(delta_shift) >= 3.0:
            signals.append(
                DiagnosticSignal(
                    title="Position delta drifted",
                    severity="medium" if abs(delta_shift) < 8 else "high",
                    detail=f"Position delta changed by {delta_shift:.2f} points from entry to now.",
                    driver="greeks",
                )
            )

    if input_data.current_vega is not None and input_data.entry_vega is not None:
        vega_shift = input_data.current_vega - input_data.entry_vega
        if abs(vega_shift) >= 5.0:
            signals.append(
                DiagnosticSignal(
                    title="Position vega changed materially",
                    severity="medium",
                    detail=f"Position vega changed by {vega_shift:.2f}; check whether the position is still expressing the intended vol exposure.",
                    driver="greeks",
                )
            )

    if not signals:
        signals.append(
            DiagnosticSignal(
                title="No single dominant market driver detected",
                severity="low",
                detail="The supplied snapshot does not show a large spot, front-vol, back-vol, or term-structure shock. Review fills, bid/ask marks, and position-specific skew.",
                driver="marks",
            )
        )

    driver_counts: dict[str, int] = {}
    severity_weight = {"low": 1, "medium": 2, "high": 3}
    for signal in signals:
        driver_counts[signal.driver] = driver_counts.get(signal.driver, 0) + severity_weight.get(signal.severity, 1)
    primary_driver = max(driver_counts.items(), key=lambda item: item[1])[0]
    regime = classify_regime(points)

    if input_data.trade_pnl is None:
        verdict = "diagnostic only"
    elif input_data.trade_pnl < 0:
        verdict = "red trade"
    elif input_data.trade_pnl > 0:
        verdict = "green trade"
    else:
        verdict = "flat trade"

    bias = _adjustment_bias(strategy_family, primary_driver, signals, input_data.trade_pnl)
    summary = _summary_sentence(verdict, regime, primary_driver, signals)

    return DiagnosticReport(
        verdict=verdict,
        regime=regime,
        primary_driver=primary_driver,
        bias=bias,
        summary=summary,
        signals=signals,
        snapshot_rows=market_snapshot_rows(points),
        ratio_rows=term_structure_rows(points),
        action_rows=_action_rows(strategy_family, primary_driver, signals),
    )


def _summary_sentence(verdict: str, regime: str, primary_driver: str, signals: Iterable[DiagnosticSignal]) -> str:
    top = next(iter(signals))
    return (
        f"Diagnosis: {verdict}. Regime is {regime}. "
        f"Primary pressure came from {primary_driver.replace('_', ' ')}. "
        f"Main flag: {top.title}."
    )


def _adjustment_bias(
    strategy_family: str,
    primary_driver: str,
    signals: list[DiagnosticSignal],
    trade_pnl: float | None,
) -> str:
    high_count = sum(1 for signal in signals if signal.severity == "high")
    losing = trade_pnl is not None and trade_pnl < 0

    if strategy_family == "calendar_like" and primary_driver in {"front_vol", "term_structure"}:
        if losing and high_count >= 2:
            return "defensive: avoid adding size until front/back ratios stabilize or mean-revert"
        return "watchful: wait for front/back ratio mean reversion before adjusting aggressively"
    if primary_driver == "spot":
        return "directional review: check tent location, breakevens, and delta before rolling or hedging"
    if primary_driver == "marks":
        return "mark-quality review: verify bid/ask width, fills, and model marks before changing risk"
    return "neutral review: confirm position Greeks still match the original trade thesis"


def _action_rows(strategy_family: str, primary_driver: str, signals: list[DiagnosticSignal]) -> list[dict[str, object]]:
    rows = [
        {
            "check": "Do not diagnose from PnL alone",
            "why": "Separate spot move, vol-curve move, theta decay, and bid/ask mark noise before adjusting.",
            "priority": "high",
        },
        {
            "check": "Compare current Greeks to entry Greeks",
            "why": "A calendar/Batman can look similar on strikes but become a different risk after spot and vol move.",
            "priority": "high",
        },
    ]
    if strategy_family == "calendar_like":
        rows.append(
            {
                "check": "Watch VIX9D/VIX and VIX1D/VIX9D",
                "why": "These ratios show whether short-dated vol is still moving against the structure or starting to mean-revert.",
                "priority": "high" if primary_driver in {"front_vol", "term_structure"} else "medium",
            }
        )
    if any(signal.driver == "spot" for signal in signals):
        rows.append(
            {
                "check": "Replot risk chart at current spot",
                "why": "Spot movement can shift the trade away from the tent even when vol marks look harmless.",
                "priority": "medium",
            }
        )
    rows.append(
        {
            "check": "Set next review trigger",
            "why": "Use objective triggers such as ratio mean reversion, delta limit, loss limit, or last-hour-only adjustment rule.",
            "priority": "medium",
        }
    )
    return rows


def format_cli_report(report: DiagnosticReport) -> str:
    """Render a compact terminal-friendly report."""

    lines = [
        f"Verdict: {report.verdict}",
        f"Regime: {report.regime}",
        f"Primary driver: {report.primary_driver}",
        f"Bias: {report.bias}",
        "",
        report.summary,
        "",
        "Signals:",
    ]
    for index, signal in enumerate(report.signals, start=1):
        lines.append(f"{index}. [{signal.severity}] {signal.title}: {signal.detail}")
    lines.append("")
    lines.append("Term structure ratios:")
    for row in report.ratio_rows:
        lines.append(f"- {row['pair']}: open={row['open']} now={row['now']} change={row['change']}")
    return "\n".join(lines)
