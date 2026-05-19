# Trade Outcome Diagnosis Streamlit Integration Design

## Goal

Add Phase 2 trade outcome diagnosis to the Streamlit app as a selected-candidate workflow in the existing right-side workspace.

The feature lets a user diagnose why a selected Batman candidate is red, green, or flat after entry by combining:

- selected scanner candidate context
- manual trade PnL
- manual open/current market and volatility snapshots
- optional current position Greeks
- deterministic signals from `scanner.trade_diagnostics`

The feature must not place orders, fetch live held positions, or use an AI narrative layer.

## Current Context

The repository already has a deterministic diagnosis engine:

- `scanner/trade_diagnostics.py`
  - `DiagnosticInput`
  - `build_market_points`
  - `diagnose`
  - `DiagnosticReport`
  - CLI formatting helpers

The repository also has a CLI entry point:

- `diagnose_trade.py`

The Streamlit app currently renders scan results in `app.py` using a two-column workspace:

- left column: ranked candidate picker, full candidate table, CSV export
- right column: selected candidate risk chart, risk assumptions, benchmark comparison, selected legs, held TWS combo order panel

The diagnosis UI should live in the right column for the currently selected candidate.

## Recommended UX

Add a collapsed-by-default `Trade Outcome Diagnosis` expander in the selected candidate workspace.

The expander should sit after the risk chart assumptions and before operational/order actions. This keeps diagnosis close to the selected risk chart while avoiding interference with the normal scan workflow.

The panel should include:

- a compact diagnosis input area
- an open/current market snapshot editor
- a deterministic report area

The user should be able to run a diagnosis without leaving the selected candidate view.

## Input Defaults

The selected candidate should pre-fill the fields that are already known:

- `strategy`: `batman`
- `entry_delta`: `candidate.position_delta`
- `entry_vega`: `candidate.position_vega`
- `current_delta`: defaults to `candidate.position_delta`
- `current_vega`: defaults to `candidate.position_vega`

The user manually enters:

- `trade_pnl`
- open/current values for:
  - `SPX`
  - `VIX`
  - `VIX9D`
  - `VIX1D`
  - `VIX3M`
  - `VIX6M`
  - `VVIX`

Market snapshot fields should allow blank values. The diagnostics engine already tolerates incomplete market points by returning lower-signal results where required data is missing.

## Report Output

After input entry, the panel should call `diagnose()` and render:

- a compact verdict/regime/driver/bias summary
- a "Why red / why green" signal table
- a term-structure ratio table
- an adjustment/action checklist table
- an optional market snapshot table when snapshot rows exist

The report must label findings as deterministic diagnostics, not trading instructions.

## Architecture

Keep `scanner.trade_diagnostics` as the source of truth for diagnostic logic.

Add small app-layer helpers in `app.py` to:

- build default diagnosis values from a `BatmanCandidate`
- convert Streamlit market snapshot inputs into `MarketPoint` data
- convert a `DiagnosticReport` into display rows

The Streamlit renderer should only collect inputs and render the returned report. It should not duplicate rule logic from `scanner.trade_diagnostics`.

## Data Flow

1. User runs or loads a scan.
2. User selects a ranked candidate.
3. Right-side workspace renders risk chart and selected candidate details.
4. `Trade Outcome Diagnosis` expander pre-fills candidate-derived inputs.
5. User enters PnL and market open/current values.
6. App builds `DiagnosticInput`.
7. App calls `diagnose()`.
8. App renders the deterministic report tables/cards.

## Error Handling

The panel should avoid hard failures for missing market data:

- blank open/current values should be passed as `None`
- partially filled symbols should still be included when either open or current is present
- non-positive or missing values should not crash rendering

The app should show the normal low-signal diagnostics if insufficient inputs exist.

## Testing

Tests should focus on pure helper behavior and deterministic data shaping:

- candidate defaults include strategy, entry/current delta, and entry/current vega
- market snapshot form data converts to normalized `MarketPoint` entries
- diagnosis display rows include verdict, regime, primary driver, and bias
- incomplete market snapshot input does not raise

Streamlit widget rendering does not need browser-level testing in this phase.

## Out Of Scope

Phase 2 does not include:

- automatic IBKR held-position ingestion
- saving entry regime at scan time
- comparing live held trades against entry regime
- strategy-specific adapters beyond the existing strategy-family logic
- AI narrative rewriting
- order recommendations or automated adjustments

Those remain later phases.
