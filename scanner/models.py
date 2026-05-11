"""Shared data models for the Batman Scanner.

The scanner keeps these models simple on purpose. Dataclasses are easy to
inspect, serialize, and explain when debugging scan output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class OptionQuote:
    symbol: str
    expiry: str
    strike: float
    right: str
    bid: float | None
    ask: float | None
    mid: float | None
    delta: float | None
    theta: float | None = None
    vega: float | None = None
    gamma: float | None = None
    implied_vol: float | None = None
    contract: Any | None = None

    def has_required_data(self) -> bool:
        """Return True when this quote can be used in candidate math."""
        return (
            self.bid is not None
            and self.ask is not None
            and self.mid is not None
            and self.delta is not None
            and self.bid >= 0
            and self.ask > 0
            and self.ask >= self.bid
        )

    def missing_data_reasons(self) -> list[str]:
        """Explain why a quote cannot be used in candidate math."""
        reasons: list[str] = []
        if self.bid is None or self.ask is None or self.mid is None:
            reasons.append("missing_bid_ask")
        elif self.bid < 0 or self.ask <= 0 or self.ask < self.bid:
            reasons.append("invalid_bid_ask")
        if self.delta is None:
            reasons.append("missing_delta")
        return reasons

    @property
    def spread(self) -> float:
        if self.bid is None or self.ask is None:
            return 0.0
        return max(self.ask - self.bid, 0.0)


@dataclass
class BatmanLeg:
    name: str
    action: str
    quantity: int
    quote: OptionQuote

    @property
    def signed_quantity(self) -> int:
        return self.quantity if self.action == "BUY" else -self.quantity

    @property
    def delta_contribution(self) -> float:
        return self.signed_quantity * (self.quote.delta or 0.0)

    @property
    def theta_contribution(self) -> float:
        return self.signed_quantity * (self.quote.theta or 0.0)

    @property
    def vega_contribution(self) -> float:
        return self.signed_quantity * (self.quote.vega or 0.0)

    @property
    def gamma_contribution(self) -> float:
        return self.signed_quantity * (self.quote.gamma or 0.0)


@dataclass
class BatmanCandidate:
    symbol: str
    front_expiry: str
    back_expiry: str
    front_dte: int
    back_dte: int
    sc_high: BatmanLeg
    lc_mid: BatmanLeg
    sc_low: BatmanLeg
    entry_credit: float
    total_delta: float
    total_theta: float
    total_vega: float
    total_gamma: float
    average_spread_ratio: float
    score: float = 0.0
    delta_score: float = 0.0
    credit_score: float = 0.0
    dte_anchor_score: float = 0.0
    spread_penalty: float = 0.0
    theta_score: float = 0.0
    delta_theta_ratio_score: float = 0.0
    liquidity_score: float = 0.0
    shape_quality_score: float = 0.0
    rank: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def legs(self) -> list[BatmanLeg]:
        return [self.sc_high, self.lc_mid, self.sc_low]

    @property
    def position_delta(self) -> float:
        # Deltas are stored in 100-delta style, for example 54 instead of 0.54.
        return self.total_delta

    @property
    def position_theta(self) -> float:
        return self.total_theta * 100

    @property
    def position_vega(self) -> float:
        return self.total_vega * 100

    @property
    def position_gamma(self) -> float:
        return self.total_gamma * 100

    @property
    def theta_drag(self) -> float:
        return max(0.0, -self.position_theta)

    @property
    def delta_theta_ratio(self) -> float:
        if abs(self.position_theta) < 1e-9:
            return 0.0
        return self.position_delta / abs(self.position_theta)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["position_delta"] = self.position_delta
        data["position_theta"] = self.position_theta
        data["position_vega"] = self.position_vega
        data["position_gamma"] = self.position_gamma
        data["theta_drag"] = self.theta_drag
        data["delta_theta_ratio"] = self.delta_theta_ratio
        for leg_name in ("sc_high", "lc_mid", "sc_low"):
            data[leg_name]["quote"].pop("contract", None)
        return data


@dataclass
class ScanSettings:
    symbol: str = "SPX"
    exchange: str = "CBOE"
    currency: str = "USD"
    min_front_dte: int = 80
    max_dte: int = 600
    min_dte_gap: int = 50
    max_dte_gap: int = 200
    sc_high_min_delta: int = 45
    sc_high_max_delta: int = 60
    sc_high_delta_step: int = 5
    lc_mid_min_offset: int = 18
    lc_mid_max_offset: int = 26
    lc_mid_offset_step: int = 2
    target_trade_delta: float = 3.0
    min_credit: float = 0.0
    max_results: int = 10
    max_contracts_per_expiry: int = 120
    market_data_batch_size: int = 80
    allowed_delta_deviation: float = 5.0
    target_credit: float = 10.0
    scoring_mode: str = "theta_first"
    expiry_pairing_mode: str = "all_pairs"
    require_positive_theta: bool = False
    upside_strike_multiplier: float = 1.60
    strike_increment: int = 0
    strategy_preset: str = "dynamic_batman_grid"
    dte_selection_mode: str = "range"
    front_target_dte: int = 200
    back_target_dte: int = 260
    dte_tolerance: int = 20
    risk_free_rate: float = 0.045
    dividend_yield: float = 0.013
    sweep_long_delta: float = 32.0
    sweep_short_hi_min_delta: float = 48.0
    sweep_short_hi_max_delta: float = 54.0
    sweep_short_lo_min_delta: float = 7.0
    sweep_short_lo_max_delta: float = 13.0
    sweep_max_abs_delta: float = 5.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    settings: ScanSettings
    candidates: list[BatmanCandidate]
    underlying_price: float | None = None
    skipped_missing_data: int = 0
    skipped_filters: int = 0
    quote_counts_by_expiry: dict[str, dict[str, int | float]] = field(default_factory=dict)
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    canonical_candidate: BatmanCandidate | None = None
    sweep_candidates: list[BatmanCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mock: bool = False
