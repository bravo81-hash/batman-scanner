"""Order construction helpers for held IBKR combo staging."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from scanner.models import BatmanCandidate, BatmanLeg, ScanResult


@dataclass(frozen=True)
class HeldOrderPayload:
    action: str
    totalQuantity: int
    orderType: str
    lmtPrice: float
    transmit: bool


def round_to_increment(value: float, increment: float = 0.05) -> float:
    decimal_value = Decimal(str(value))
    decimal_increment = Decimal(str(increment))
    rounded = (decimal_value / decimal_increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * decimal_increment
    return float(rounded)


def signed_mid_value(leg: BatmanLeg) -> float:
    if leg.quote.mid is None:
        raise ValueError(f"{leg.name} is missing a mid price.")
    sign = 1 if leg.action == "SELL" else -1
    return sign * leg.quantity * float(leg.quote.mid)


def combo_mid_credit(candidate: BatmanCandidate) -> float:
    return round_to_increment(sum(signed_mid_value(leg) for leg in candidate.legs))


def combo_leg_preview_rows(candidate: BatmanCandidate) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for leg in candidate.legs:
        quote = leg.quote
        rows.append(
            {
                "leg": leg.name,
                "action": leg.action,
                "ratio": leg.quantity,
                "expiry": quote.expiry,
                "strike": quote.strike,
                "right": quote.right,
                "mid": quote.mid,
                "signed mid value": round(signed_mid_value(leg), 4),
            }
        )
    return rows


def validate_combo_order_inputs(quantity: int, limit_credit: float) -> None:
    if int(quantity) < 1:
        raise ValueError("Order quantity must be at least 1.")
    if float(limit_credit) <= 0:
        raise ValueError("Order limit credit must be positive.")


def build_held_limit_order_payload(quantity: int, limit_credit: float) -> HeldOrderPayload:
    validate_combo_order_inputs(quantity, limit_credit)
    return HeldOrderPayload(
        action="BUY",
        totalQuantity=int(quantity),
        orderType="LMT",
        lmtPrice=-float(limit_credit),
        transmit=False,
    )


def can_stage_result_orders(result: ScanResult) -> bool:
    return bool(result.candidates) and not result.mock
