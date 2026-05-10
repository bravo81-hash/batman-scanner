# AI Startup Prompt for Batman Scanner Development

Copy/paste this prompt into Codex, Claude, or another AI coding assistant after opening this repo in VS Code.

---

```text
You are helping me continue development on the local Python project `batman-scanner`.

Before changing code, inspect these files first:

1. README.md
2. docs/ARCHITECTURE_REVIEW.md
3. docs/AI_STARTUP_PROMPT.md
4. scanner/models.py
5. scanner/batman.py
6. scanner/scoring.py
7. scanner/option_chain.py
8. scanner/risk_chart.py
9. app.py

Project purpose:

Batman Scanner is an entry-selection tool for Batman-style 3-leg CALL option structures using IBKR market data. It is designed to help shortlist candidate trades worth manually modelling in OptionNet Explorer.

It must NOT replace OptionNet Explorer.

It must NOT manage open trades.

It must NOT place, submit, preview, modify, cancel, or automate orders.

This scanner is for:

- scanning option chains
- building candidate Batman structures
- ranking candidate entries
- showing approximate quick-glance risk profiles
- explaining why candidates ranked well or were rejected
- exporting candidate details for manual review

It is NOT for:

- live execution
- auto trading
- open trade monitoring
- trade adjustments
- portfolio Greeks
- P/L tracking after entry
- replacing OptionNet Explorer

Current strategy concept:

The Batman structure is:

1. SC_High
   - Sell 1 front-expiry CALL
   - Target high delta, usually around 54 delta

2. LC_Mid
   - Buy 2 back-expiry CALLs
   - Target delta is dynamic:
     LC_Mid target ≈ SC_High delta - offset
   - Example: if SC_High is 54 delta and offset is 22, LC_Mid is around 32 delta

3. SC_Low
   - Sell 1 additional front-expiry CALL
   - Do NOT treat this as a fixed 3-delta option
   - It is dynamically selected to bring the TOTAL POSITION DELTA near target_trade_delta

Example:

- SC_High = -54 delta
- LC_Mid = +32 delta x 2 = +64 delta
- SC_Low ≈ -7 delta
- total position delta ≈ +3

This dynamic total-position-delta targeting is intentional and important.

Development philosophy:

Keep the app focused on high-value entry decision-making only.

Prioritize:

- accurate candidate construction
- reliable quick-glance risk profiles
- good reject diagnostics
- liquidity/executability scoring
- candidate diversity
- buddy-exact comparison mode
- simple and clear UI

Avoid:

- overbuilding
- auto execution
- trade management features
- duplicating OptionNet Explorer functionality
- complex ML or optimization before basic validation works

Current important design choices:

- Python app
- Streamlit UI
- ib_insync for IBKR API
- SQLite for quote cache and scan history
- no Docker
- no order placement logic
- scanner-only workflow
- conservative credit calculation:
  - short legs at bid
  - long legs at ask
- risk chart uses approximate Black-Scholes/Black-Scholes-Merton style modelling calibrated to current mids
- risk chart is for triage only, not final validation

Completed next-stage items:

- expiry_pairing_mode is implemented in scanner logic.
- require_positive_theta is implemented as a hard candidate filter.
- rejection_reasons are counted and displayed in scan diagnostics.
- liquidity_score and shape_quality_score are calculated and displayed.
- strategy presets are available in the Streamlit sidebar.
- upside_strike_multiplier is configurable and used by live quote collection.

Highest priority next development tasks:

1. Add candidate diversity / de-duplication:

   Avoid the top 10 being near-identical.

   Simple first version:

   - group candidates by front_expiry/back_expiry and rounded strikes
   - show only the best candidate per group
   - make this optional

2. Add exact buddy-comparison mode:

   Create a preset/report path that makes it easy to compare against the buddy scanner output.

   Include:

   - candidate count
   - constructed count
   - ranked count
   - selected expiry pairing mode
   - exact delta targets
   - position delta
   - position theta
   - D/T ratio
   - credit
   - score

3. Improve rejection diagnostics:

   Track and display counts for reasons such as:

   - no_valid_back_expiry
   - no_sc_high
   - no_lc_mid
   - no_sc_low
   - negative_or_zero_credit
   - negative_or_zero_total_delta
   - negative_or_zero_theta
   - invalid_structure
   - missing_quote_data
   - wide_spread

Reference details for implemented settings:

expiry_pairing_mode options:

   Options:

   - all_pairs
     Current/default behaviour. Evaluate all valid front/back expiry pairs.

   - adjacent_only
     Only pair neighbouring expiries after DTE filtering.

   - first_valid_far
     For each front expiry, use the first later expiry satisfying min_dte_gap and max_dte_gap.
     This may better replicate the original buddy scanner.

4. Update Streamlit UI:

   Add controls for:

   - optional diversity toggle

   Add display columns for:

   - diversity group / duplicate status

5. Update docs after every meaningful change:

   - README.md
   - docs/ARCHITECTURE_REVIEW.md if architectural decisions change
   - docs/AI_STARTUP_PROMPT.md if development priorities change

Important coding rules:

- Keep functions small and readable.
- Prefer obvious code over clever code.
- Add comments where trading logic could be misunderstood.
- Preserve scanner-only safety.
- Do not add order-related methods.
- Do not add any IBKR placeOrder, modifyOrder, cancelOrder, bracketOrder, or execution workflow.
- If you see any order-related code, stop and flag it.
- Do not add trade monitoring or open-position management.
- Do not add features already handled by OptionNet Explorer unless they directly improve pre-entry candidate selection.

Testing guidance:

Before making large changes, run or reason through mock mode first.

After changes, test:

1. App loads without IBKR connected.
2. Mock mode works.
3. Candidate table renders.
4. Risk chart renders.
5. CSV export still works.
6. No order placement methods exist.
7. Existing config.local.toml compatibility is preserved where possible.

When adding fields to ScanSettings:

- Update scanner/models.py
- Update config.example.toml
- Update README.md
- Update Streamlit sidebar if user-facing

When changing scoring:

- Keep existing scoring modes working.
- Add new scores without breaking old fields.
- Show score components in UI so rankings are explainable.

When changing risk-chart logic:

- Remember the goal is quick triage, not replacing OptionNet Explorer.
- Avoid making good candidates look bad due to bid/ask or mid-normalization artifacts.
- Keep mid-normalized PnL for shape comparison.
- Keep executable PnL available separately to show bid/ask drag.

Final reminder:

The scanner’s job is not to tell me what to trade automatically.

The scanner’s job is to surface the best candidates worth manually modelling in OptionNet Explorer.
```

---

## Current Human Preference Summary

Bhavik wants the scanner to remain narrowly focused on **new-position candidate selection**.

He does not want the app to duplicate OptionNet Explorer features for open-trade management.

The highest-value direction is:

```text
better candidate shortlist quality
better quick-glance risk profile accuracy
better explanation of rankings/rejections
better comparison to buddy scanner logic
```

Not:

```text
auto execution
open trade monitoring
adjustment management
portfolio dashboard
```
