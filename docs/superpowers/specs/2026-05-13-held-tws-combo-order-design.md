# Held TWS Combo Order Design

## Summary

Add a guarded workflow that lets the user stage the currently selected Batman candidate in TWS as a held IBKR combo order. The app will call `placeOrder(..., transmit=False)` so the order appears in TWS for manual review and transmit. The app will not auto-transmit, modify, cancel, or manage the order after staging.

This changes the app boundary from read-only scanning to scanner plus explicit held-order staging.

## Goals

- Let the user choose a scanned combo position from the existing results workspace.
- Build one IBKR `BAG` combo contract for the whole Batman structure.
- Stage one combo limit order in TWS with `transmit=False`.
- Default the limit price to the whole-combo mid credit.
- Show enough preview detail for the user to verify the staged order before sending it to TWS.
- Keep mock scan results and incomplete candidate data from sending any order.

## Non-Goals

- No market orders.
- No individual leg orders.
- No auto-transmission from the app.
- No order modification, cancellation, or portfolio management.
- No automatic account selection beyond the active TWS/API session behavior unless IBKR requires an account field in local testing.

## User Flow

After a scan returns candidates, the selected-candidate panel will include a held-order section.

The section will show:

- selected candidate rank and leg summary
- conservative estimated credit already used by the scanner
- calculated whole-combo mid credit for the default limit price
- order quantity, default `1`
- editable limit credit, defaulting to whole-combo mid credit
- a confirmation checkbox stating that the app will stage an untransmitted order in TWS
- a `Stage Held Order in TWS` button

When clicked, the app connects to TWS using the sidebar connection settings, qualifies the option contracts, builds one combo contract, creates one limit order with `transmit=False`, calls `placeOrder`, and reports the returned order id/status.

## Combo Price

The default limit price is the whole-combo mid credit per one Batman combo:

```text
SC_High short call mid credit
- 2 * LC_Mid long call mid debit
+ SC_Low short call mid credit
```

In code this should be calculated from each leg action and signed quantity:

- `SELL` legs contribute positive mid value.
- `BUY` legs contribute negative mid value.
- The resulting net credit is rounded to the nearest `0.05` for display and order submission.

`candidate.entry_credit` remains visible as the conservative bid/ask estimate, but it is not the default order price.

## IBKR Contract And Order Mapping

The selected Batman candidate maps to one IBKR combo contract:

- `secType="BAG"`
- symbol from the candidate/settings, such as `SPX`
- exchange from current scan settings, such as `CBOE`
- currency from current scan settings, such as `USD`
- three `ComboLeg` entries:
  - `SC_High`: sell 1 front-expiry call
  - `LC_Mid`: buy 2 back-expiry calls
  - `SC_Low`: sell 1 front-expiry call

The staged order maps to one combo limit order:

- action should represent entering the net-credit combo in IBKR's combo-order terms.
- total quantity comes from the UI quantity field.
- order type is `LMT`.
- limit price defaults to the whole-combo mid credit.
- `transmit=False`.

Implementation must verify the correct IBKR action and sign convention against `ib_insync` combo order behavior. The tests should protect the app's internal candidate-to-leg mapping, and live paper testing should verify how the held order appears in TWS before any live account use.

## Architecture

Create `scanner/orders.py` to keep order construction separate from scan generation and UI layout.

Responsibilities:

- calculate whole-combo mid credit from a `BatmanCandidate`
- create a serializable preview of combo legs
- build or describe the IBKR combo leg mapping from a candidate
- build the held limit order with `transmit=False`

Extend `scanner/ibkr_client.py` deliberately rather than leaving it as read-only:

- load `Bag`, `ComboLeg`, and `LimitOrder` from `ib_insync`
- qualify each option contract from the selected candidate
- build the combo contract from qualified conIds
- stage the held order with `placeOrder`
- return a small result object or dictionary with order id, status, and preview data

Update `app.py` to render the held-order panel inside the selected-candidate workspace. UI code should remain thin and call helper functions for price calculations and order preview rows.

## Guardrails

- Disable or hide staging for mock scan results.
- Require the confirmation checkbox before enabling the staging button.
- Require positive quantity.
- Require all leg mids and option contract details needed for qualification.
- Use a limit order only.
- Always set `transmit=False`.
- Show a clear warning that the order is staged in TWS and must be reviewed there before manual transmit.
- Keep errors visible in Streamlit without crashing the scan result view.

## Documentation Updates

Update the README and app caption so they no longer claim "no order placement" without qualification. The new statement should be clear:

- the scanner can stage held, untransmitted combo limit orders in TWS
- the user must manually review and transmit in TWS
- paper account testing is expected first

## Testing

Add unit tests before implementation for:

- whole-combo mid credit calculation uses signed leg quantities
- preview rows show the correct three legs and quantities
- held order construction sets `transmit=False`
- mock results do not expose staging behavior in UI helper logic
- incomplete mids produce a validation error instead of an order price

Manual verification after implementation:

- run unit tests
- run Streamlit smoke test if practical
- test with TWS paper account and confirm one held combo limit order appears in TWS with three combo legs and manual transmit still required
