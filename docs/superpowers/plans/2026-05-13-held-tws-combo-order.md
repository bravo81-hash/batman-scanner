# Held TWS Combo Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a guarded Streamlit workflow that stages the selected Batman candidate as one held TWS combo limit order using the whole-combo mid credit and `transmit=False`.

**Architecture:** Put pure order math and preview logic in `scanner/orders.py`, then make `scanner/ibkr_client.py` a thin IBKR adapter that qualifies option legs, builds one `BAG` contract, and calls `placeOrder`. The UI displays the combo mid as a positive credit, while the IBKR adapter signs `lmtPrice` for TWS combo conventions. Keep `app.py` focused on UI state, user confirmation, and status messages.

**Tech Stack:** Python, Streamlit, ib_insync, unittest, pandas.

---

## File Structure

- Create `scanner/orders.py`: pure helpers for whole-combo mid credit, preview rows, input validation, and held limit order payload creation.
- Create `tests/test_orders.py`: unit tests for pricing, validation, preview rows, and held order fields without a live IBKR session.
- Modify `scanner/ibkr_client.py`: expand lazy imports to include `Bag`, `ComboLeg`, `LimitOrder`, add option contract creation for a selected candidate, build one combo contract, and stage a held limit order.
- Modify `app.py`: add order preview helper imports, render the held-order panel in the selected-candidate workspace, disable it for mock results, and call the IBKR staging method after confirmation.
- Modify `tests/test_app_layout.py`: add UI helper tests for mock gating and default order limit value.
- Modify `README.md`: document held combo staging, manual TWS transmit, and paper-account expectations.

## Task 1: Pure Order Helpers

**Files:**
- Create: `scanner/orders.py`
- Test: `tests/test_orders.py`

- [ ] **Step 1: Write failing tests for combo mid credit and validation**

Add `tests/test_orders.py`:

```python
import unittest

from scanner.batman import build_batman_candidate
from scanner.models import OptionQuote, ScanSettings
from scanner.orders import combo_mid_credit, validate_combo_order_inputs


def quote(expiry: str, strike: float, delta: float, bid: float, ask: float, mid: float | None = None) -> OptionQuote:
    return OptionQuote(
        symbol="SPX",
        expiry=expiry,
        strike=strike,
        right="C",
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2 if mid is None else mid,
        delta=delta,
        theta=-0.1,
        vega=1.0,
        gamma=0.01,
    )


def candidate_with_mids(sc_high_mid: float | None = 10.02, lc_mid_mid: float | None = 4.01, sc_low_mid: float | None = 1.26):
    candidate = build_batman_candidate(
        symbol="SPX",
        front_expiry="2027-01-15",
        back_expiry="2027-04-16",
        front_dte=253,
        back_dte=344,
        sc_high=quote("2027-01-15", 5200, 55, 9.5, 10.5, sc_high_mid),
        lc_mid=quote("2027-04-16", 5600, 33, 3.5, 4.5, lc_mid_mid),
        front_quotes=[quote("2027-01-15", 6000, 8, 1.0, 1.5, sc_low_mid)],
        target_total_delta=3,
        settings=ScanSettings(),
    )
    assert candidate is not None
    return candidate


class OrderHelperTests(unittest.TestCase):
    def test_combo_mid_credit_uses_signed_leg_quantities_and_rounds_to_five_cents(self) -> None:
        candidate = candidate_with_mids(sc_high_mid=10.02, lc_mid_mid=4.01, sc_low_mid=1.26)

        credit = combo_mid_credit(candidate)

        self.assertEqual(credit, 3.25)

    def test_combo_mid_credit_requires_all_leg_mids(self) -> None:
        candidate = candidate_with_mids(lc_mid_mid=None)

        with self.assertRaisesRegex(ValueError, "LC_Mid"):
            combo_mid_credit(candidate)

    def test_validate_combo_order_inputs_requires_positive_quantity_and_limit_credit(self) -> None:
        validate_combo_order_inputs(quantity=1, limit_credit=3.25)

        with self.assertRaisesRegex(ValueError, "quantity"):
            validate_combo_order_inputs(quantity=0, limit_credit=3.25)
        with self.assertRaisesRegex(ValueError, "limit credit"):
            validate_combo_order_inputs(quantity=1, limit_credit=0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest tests.test_orders -v`

Expected: FAIL or ERROR because `scanner.orders` does not exist.

- [ ] **Step 3: Implement minimal pure order helpers**

Create `scanner/orders.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest tests.test_orders -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scanner/orders.py tests/test_orders.py
git commit -m "Add held combo order helpers"
```

## Task 2: Preview Rows And Held Order Payload Tests

**Files:**
- Modify: `tests/test_orders.py`
- Modify: `scanner/orders.py`

- [ ] **Step 1: Write failing tests for preview rows and held order payload**

Add imports in `tests/test_orders.py`:

```python
from scanner.models import ScanResult
from scanner.orders import build_held_limit_order_payload, can_stage_result_orders, combo_leg_preview_rows
```

Add tests inside `OrderHelperTests`:

```python
    def test_combo_leg_preview_rows_show_one_whole_combo(self) -> None:
        candidate = candidate_with_mids()

        rows = combo_leg_preview_rows(candidate)

        self.assertEqual([row["leg"] for row in rows], ["SC_High", "LC_Mid", "SC_Low"])
        self.assertEqual([row["action"] for row in rows], ["SELL", "BUY", "SELL"])
        self.assertEqual([row["ratio"] for row in rows], [1, 2, 1])
        self.assertEqual(rows[1]["expiry"], "2027-04-16")
        self.assertEqual(rows[1]["strike"], 5600)

    def test_build_held_limit_order_payload_is_limit_and_not_transmitted(self) -> None:
        payload = build_held_limit_order_payload(quantity=2, limit_credit=3.25)

        self.assertEqual(payload.action, "BUY")
        self.assertEqual(payload.totalQuantity, 2)
        self.assertEqual(payload.orderType, "LMT")
        self.assertEqual(payload.lmtPrice, -3.25)
        self.assertFalse(payload.transmit)

    def test_can_stage_result_orders_rejects_mock_results(self) -> None:
        candidate = candidate_with_mids()

        live_result = ScanResult(settings=ScanSettings(), candidates=[candidate], mock=False)
        mock_result = ScanResult(settings=ScanSettings(), candidates=[candidate], mock=True)

        self.assertTrue(can_stage_result_orders(live_result))
        self.assertFalse(can_stage_result_orders(mock_result))
```

- [ ] **Step 2: Run tests to verify they fail if Task 1 was not already complete**

Run: `uv run python -m unittest tests.test_orders -v`

Expected after Task 1: PASS. If functions are missing, FAIL with import errors.

- [ ] **Step 3: Ensure implementation matches the tests**

If Task 1 created `combo_leg_preview_rows`, `build_held_limit_order_payload`, and `can_stage_result_orders` exactly as shown, no code change is needed. If not, update `scanner/orders.py` to match the Task 1 implementation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest tests.test_orders -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scanner/orders.py tests/test_orders.py
git commit -m "Add held combo preview and payload tests"
```

## Task 3: IBKR Client Held Combo Adapter

**Files:**
- Modify: `scanner/ibkr_client.py`
- Test: `tests/test_orders.py`

- [ ] **Step 1: Write failing tests for IBKR-agnostic combo leg descriptors**

Add imports in `tests/test_orders.py`:

```python
from scanner.orders import combo_leg_descriptors
```

Add this test inside `OrderHelperTests`:

```python
    def test_combo_leg_descriptors_match_selected_candidate_contracts(self) -> None:
        candidate = candidate_with_mids()

        descriptors = combo_leg_descriptors(candidate)

        self.assertEqual(
            descriptors,
            [
                {
                    "leg": "SC_High",
                    "action": "SELL",
                    "ratio": 1,
                    "symbol": "SPX",
                    "expiry": "2027-01-15",
                    "strike": 5200,
                    "right": "C",
                },
                {
                    "leg": "LC_Mid",
                    "action": "BUY",
                    "ratio": 2,
                    "symbol": "SPX",
                    "expiry": "2027-04-16",
                    "strike": 5600,
                    "right": "C",
                },
                {
                    "leg": "SC_Low",
                    "action": "SELL",
                    "ratio": 1,
                    "symbol": "SPX",
                    "expiry": "2027-01-15",
                    "strike": 6000,
                    "right": "C",
                },
            ],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest tests.test_orders.OrderHelperTests.test_combo_leg_descriptors_match_selected_candidate_contracts -v`

Expected: FAIL with missing `combo_leg_descriptors`.

- [ ] **Step 3: Add descriptors to pure helper module**

Add to `scanner/orders.py`:

```python
def combo_leg_descriptors(candidate: BatmanCandidate) -> list[dict[str, Any]]:
    descriptors: list[dict[str, Any]] = []
    for leg in candidate.legs:
        quote = leg.quote
        descriptors.append(
            {
                "leg": leg.name,
                "action": leg.action,
                "ratio": leg.quantity,
                "symbol": quote.symbol,
                "expiry": quote.expiry,
                "strike": quote.strike,
                "right": quote.right,
            }
        )
    return descriptors
```

- [ ] **Step 4: Run tests to verify descriptors pass**

Run: `uv run python -m unittest tests.test_orders -v`

Expected: PASS.

- [ ] **Step 5: Extend `scanner/ibkr_client.py` imports and lazy loader**

Modify globals near the top:

```python
Bag = None
ComboLeg = None
LimitOrder = None
```

Modify `_load_ib_insync()` global line:

```python
global IB, Index, Option, Stock, Bag, ComboLeg, LimitOrder, util, IB_IMPORT_ERROR
```

Inside the successful import block:

```python
        Bag = module.Bag
        ComboLeg = module.ComboLeg
        LimitOrder = module.LimitOrder
```

Add imports near existing scanner imports:

```python
from scanner.contracts import format_ib_expiry
from scanner.models import BatmanCandidate, OptionQuote, ScanSettings
from scanner.orders import build_held_limit_order_payload, combo_leg_descriptors, validate_combo_order_inputs
```

Keep the existing `days_to_expiry` import by changing it to:

```python
from scanner.contracts import days_to_expiry, format_ib_expiry
```

- [ ] **Step 6: Add held combo staging method**

Add this method to `IBKRClient`:

```python
    def stage_held_combo_order(
        self,
        candidate: BatmanCandidate,
        settings: ScanSettings,
        quantity: int,
        limit_credit: float,
    ) -> dict[str, Any]:
        """Stage one untransmitted combo limit order in TWS."""
        if Bag is None or ComboLeg is None or LimitOrder is None:
            raise RuntimeError("ib_insync order classes are not available.")
        validate_combo_order_inputs(quantity, limit_credit)

        option_contracts = [
            Option(
                descriptor["symbol"],
                format_ib_expiry(str(descriptor["expiry"])),
                descriptor["strike"],
                descriptor["right"],
                settings.exchange,
                currency=settings.currency,
            )
            for descriptor in combo_leg_descriptors(candidate)
        ]
        qualified = self.ib.qualifyContracts(*option_contracts)
        if len(qualified) != len(option_contracts):
            raise RuntimeError("Could not qualify every combo leg contract.")

        combo = Bag(candidate.symbol, settings.exchange, currency=settings.currency)
        combo.comboLegs = []
        for descriptor, contract in zip(combo_leg_descriptors(candidate), qualified):
            combo.comboLegs.append(
                ComboLeg(
                    conId=contract.conId,
                    ratio=int(descriptor["ratio"]),
                    action=descriptor["action"],
                    exchange=settings.exchange,
                )
            )

        payload = build_held_limit_order_payload(quantity, limit_credit)
        order = LimitOrder(payload.action, payload.totalQuantity, payload.lmtPrice)
        order.transmit = payload.transmit

        trade = self.ib.placeOrder(combo, order)
        self.ib.sleep(1)
        return {
            "order_id": getattr(trade.order, "orderId", None),
            "status": getattr(trade.orderStatus, "status", ""),
            "transmit": bool(getattr(trade.order, "transmit", False)),
            "display_limit_credit": float(limit_credit),
            "tws_limit_price": float(getattr(trade.order, "lmtPrice", -limit_credit)),
            "quantity": int(getattr(trade.order, "totalQuantity", quantity)),
            "combo_legs": len(getattr(combo, "comboLegs", []) or []),
        }
```

- [ ] **Step 7: Run focused tests**

Run: `uv run python -m unittest tests.test_orders tests.test_live_scan_helpers -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add scanner/orders.py scanner/ibkr_client.py tests/test_orders.py
git commit -m "Add IBKR held combo staging adapter"
```

## Task 4: Streamlit Held Order Panel

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app_layout.py`

- [ ] **Step 1: Write failing UI helper tests**

Modify imports in `tests/test_app_layout.py`:

```python
from app import (
    benchmark_candidate_rows,
    candidate_order_defaults,
    candidate_picker_label,
    candidate_rows,
    macro_assumption_rows,
    rejection_reason_rows,
    risk_chart_spot_price,
    selected_candidate_summary,
)
```

Add this test inside `AppLayoutTests`:

```python
    def test_candidate_order_defaults_use_combo_mid_credit(self) -> None:
        candidate = build_batman_candidate(
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
        assert candidate is not None

        defaults = candidate_order_defaults(candidate)

        self.assertEqual(defaults["quantity"], 1)
        self.assertEqual(defaults["limit_credit"], 3.25)
        self.assertIn("conservative_credit", defaults)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_app_layout.AppLayoutTests.test_candidate_order_defaults_use_combo_mid_credit -v`

Expected: FAIL with missing `candidate_order_defaults`.

- [ ] **Step 3: Add imports and UI helper in `app.py`**

Add imports:

```python
from scanner.orders import can_stage_result_orders, combo_leg_preview_rows, combo_mid_credit
```

Add helper near `selected_candidate_summary`:

```python
def candidate_order_defaults(candidate: BatmanCandidate) -> dict[str, float | int]:
    """Return default held-order values for the selected candidate."""
    return {
        "quantity": 1,
        "limit_credit": combo_mid_credit(candidate),
        "conservative_credit": round(candidate.entry_credit, 2),
    }
```

- [ ] **Step 4: Run UI helper test**

Run: `uv run python -m unittest tests.test_app_layout.AppLayoutTests.test_candidate_order_defaults_use_combo_mid_credit -v`

Expected: PASS.

- [ ] **Step 5: Add the Streamlit held-order panel function**

Add to `app.py` near `show_results_workspace`:

```python
def show_held_order_panel(
    candidate: BatmanCandidate,
    result: ScanResult,
    settings: ScanSettings,
    connection: dict[str, Any],
    status_box: Any,
) -> None:
    """Render controls for staging the selected candidate as one held TWS combo order."""
    with st.expander("Held TWS Combo Order", expanded=False):
        if not can_stage_result_orders(result):
            st.info("Held order staging is disabled for mock results.")
            return

        try:
            defaults = candidate_order_defaults(candidate)
            preview_rows = combo_leg_preview_rows(candidate)
        except ValueError as error:
            st.warning(f"Cannot stage this candidate: {error}")
            return

        st.write(
            {
                "whole_combo_mid_credit": defaults["limit_credit"],
                "conservative_credit": defaults["conservative_credit"],
            }
        )
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        quantity = st.number_input(
            "Combo quantity",
            min_value=1,
            value=int(defaults["quantity"]),
            step=1,
            key=f"held_order_qty_{candidate.rank}",
        )
        limit_credit = st.number_input(
            "Limit credit",
            min_value=0.05,
            value=float(defaults["limit_credit"]),
            step=0.05,
            key=f"held_order_limit_{candidate.rank}",
        )
        confirmed = st.checkbox(
            "Stage this as an untransmitted held order in TWS for manual review.",
            value=False,
            key=f"held_order_confirm_{candidate.rank}",
        )
        if st.button(
            "Stage Held Order in TWS",
            disabled=not confirmed,
            key=f"stage_held_order_{candidate.rank}",
        ):
            client = IBKRClient()
            try:
                status_box.info("connecting to IBKR for held order staging")
                client.connect(connection["host"], connection["port"], connection["client_id"])
                result_payload = client.stage_held_combo_order(
                    candidate,
                    settings,
                    quantity=int(quantity),
                    limit_credit=float(limit_credit),
                )
                status_box.success("Held combo order staged in TWS. Review and transmit manually in TWS.")
                st.write(result_payload)
            except Exception as error:
                status_box.error(f"Held order staging failed: {error}")
            finally:
                client.disconnect()
```

- [ ] **Step 6: Call the panel from selected candidate workspace**

In `show_results_workspace`, after the `"Selected Candidate Legs"` expander, add:

```python
        show_held_order_panel(selected_candidate, result, risk_settings, st.session_state.get("connection", {}), st.empty())
```

Then replace that with the cleaner signature by changing `show_results_workspace` to accept `connection` and `status_box`:

```python
def show_results_workspace(
    result: ScanResult,
    spot_price: float,
    risk_settings: ScanSettings,
    macro_source: str,
    macro_last_refresh: str,
    connection: dict[str, Any],
    status_box: Any,
) -> None:
```

Call inside it:

```python
        show_held_order_panel(selected_candidate, result, risk_settings, connection, status_box)
```

Update the call in `main()`:

```python
    show_results_workspace(
        result,
        spot_price,
        settings,
        connection.get("macro_source", "manual"),
        connection.get("macro_last_refresh", ""),
        connection,
        status_box,
    )
```

- [ ] **Step 7: Run focused app layout tests**

Run: `uv run python -m unittest tests.test_app_layout -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_app_layout.py
git commit -m "Add held combo order Streamlit panel"
```

## Task 5: Documentation And Safety Text

**Files:**
- Modify: `app.py`
- Modify: `README.md`

- [ ] **Step 1: Update app caption**

Change:

```python
    st.caption("Scanner only. No order placement, no live trade modification.")
```

To:

```python
    st.caption("Scanner with optional held TWS combo staging. Orders are untransmitted and must be reviewed in TWS.")
```

- [ ] **Step 2: Update README capability lists**

In `README.md`, under "What Is Included", add:

```markdown
- Optional held TWS combo staging:
  - sends one IBKR `BAG` combo limit order for the selected candidate
  - defaults the user-facing limit credit to the whole-combo mid credit
  - sends the signed TWS `lmtPrice` required by IBKR combo-price conventions
  - uses `transmit=False`, so manual review and transmit in TWS are still required
```

Under "What Is Intentionally Not Included Yet", replace:

```markdown
- No order placement.
```

With:

```markdown
- No transmitted order placement from the app.
```

Add to "What To Test First":

```markdown
11. In paper TWS only, select a candidate and use `Stage Held Order in TWS`; confirm one held combo limit order appears in TWS with manual transmit still required.
```

- [ ] **Step 3: Run docs/app smoke checks**

Run: `uv run python -m unittest tests.test_orders tests.test_app_layout tests.test_live_scan_helpers -v`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app.py README.md
git commit -m "Document held TWS combo staging"
```

## Task 6: Final Verification

**Files:**
- No planned edits unless verification reveals failures.

- [ ] **Step 1: Run the full unit test suite**

Run: `uv run python -m unittest discover -v`

Expected: PASS.

- [ ] **Step 2: Run a Streamlit import smoke test**

Run: `uv run python -c "import app; print('app import ok')"`

Expected: `app import ok`

- [ ] **Step 3: Check git status**

Run: `git status --short`

Expected: clean worktree.

- [ ] **Step 4: Manual paper TWS verification**

Run the app with TWS paper connected and confirm:

- selected candidate shows one held order panel
- default limit equals whole-combo mid credit
- staging creates one TWS combo order with three legs
- order is untransmitted and requires manual transmit in TWS

Do not use a live account for first verification.

---

## Self-Review

Spec coverage:

- selected candidate workflow: Task 4
- one BAG combo order, not individual legs: Tasks 2, 3, 4
- limit order with whole-combo mid: Tasks 1, 4
- `transmit=False`: Tasks 1, 3
- guardrails for mock/incomplete data/confirmation: Tasks 1, 4
- documentation updates: Task 5
- verification: Task 6

Marker scan:

- No banned marker text or vague edge handling remains.

Type consistency:

- `combo_mid_credit`, `combo_leg_preview_rows`, `combo_leg_descriptors`, `build_held_limit_order_payload`, and `can_stage_result_orders` are introduced before use.
- `stage_held_combo_order` takes `BatmanCandidate`, `ScanSettings`, `quantity`, and `limit_credit`, matching the UI call.
