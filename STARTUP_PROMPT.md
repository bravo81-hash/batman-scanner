# Batman Scanner — AI Startup Prompt

This is the single canonical startup prompt for future AI coding sessions.

Use this prompt when opening this repository in VS Code with Claude/Codex/ChatGPT.

---

## Project Purpose

You are continuing development of the Batman Scanner project.

This application is intentionally designed as:

- a professional SPX Batman trade candidate discovery workstation
- NOT an execution engine
- NOT a portfolio manager
- NOT a replacement for OptionNet Explorer

The trader uses:

- IBKR TWS API
- Streamlit
- Python
- MacBook Air + Mac Mini
- GitHub sync between both machines
- OptionNet Explorer for final modelling and live trade management

Primary goal:

Provide FAST and HIGH-QUALITY candidate discovery during live market hours.

The scanner should help shortlist trades worth manually modelling further in OptionNet Explorer.

The scanner must remain:

- stable
- deterministic
- low-latency
- modular
- easy to debug
- safe during live trading

DO NOT add:

- automated execution
- trade management
- portfolio tracking
- position adjustments
- broker write actions
- Kelly sizing
- capital allocation
- unnecessary complexity
- Docker

---

## Core Strategy Understanding

Batman structure:

- Short call around 54 delta
- Long 2x calls around 32 delta
- Short call low delta, often around 7 delta

Combined position delta target:

- approximately +3 position delta

Example:

```text
-54
+64
-7
= +3
```

The scanner evolved from fixed canonical structures into a dynamic scanner.

Current philosophy:

- keep ALL THREE LEGS dynamic
- optimize based on total position characteristics
- avoid hardcoded deltas where possible
- canonical structures are benchmarks only

---

## Architecture Rules

The project intentionally separates:

1. Candidate generation
2. Scoring/ranking
3. Risk modelling
4. Benchmark structures
5. Candidate efficiency analysis
6. DTE neighborhood analysis
7. Market regime analysis
8. UI rendering

DO NOT tightly couple these systems.

---

## External Research References

Reference implementations from trading peers are stored in:

```text
research/external_batman_variants/
```

These files exist for:

- research
- benchmarking
- conceptual comparison
- optimization ideas
- DTE neighborhood ideas
- regime concepts

These files are NOT production architecture references.

DO NOT blindly merge logic from those files into the scanner core.

They should be treated as:

- conceptual inspiration
- research material
- benchmark references

NOT:

- coding standards
- architecture standards
- direct implementation templates

Useful concepts extracted from those references:

- DTE neighborhood ranking
- dynamic third-leg derivation
- market regime awareness
- candidate efficiency metrics
- benchmark structures

Concepts intentionally NOT adopted:

- Kelly sizing
- portfolio management
- auto dependency installation
- broker execution
- heavy evolutionary optimization during live scans

---

## Current Important Backend Modules

Core scanner:

- `scanner/batman.py`
- `scanner/option_chain.py`
- `scanner/scoring.py`
- `scanner/models.py`

Benchmarks:

- `scanner/benchmarks.py`

Risk chart:

- `scanner/risk_chart.py`
- `scanner/macro_data.py`

New candidate-discovery intelligence modules:

- `scanner/efficiency.py`
- `scanner/dte_neighborhoods.py`
- `scanner/market_regime.py`

External references:

- `research/external_batman_variants/`

---

## Recently Implemented Here

The previous Codex attempt mostly added knobs and panels but did not add the actual intelligence layer.

The following backend modules have now been added properly:

### `scanner/efficiency.py`

Purpose:

- candidate efficiency metrics for pre-entry selection
- no new market-data calls
- no execution logic
- no trade management

Current metrics include:

- theta per credit
- positive theta per credit
- credit per spread risk
- theta per spread risk
- theta per absolute delta
- liquidity-adjusted credit
- liquidity-adjusted theta
- shape-adjusted score

### `scanner/dte_neighborhoods.py`

Purpose:

- deterministic DTE-pair ranking using already-fetched quotes
- no heavy optimizer
- no differential evolution
- no long blocking scans

Current metrics include:

- liquidity score
- theta richness
- premium richness
- term structure score
- DTE anchor component

### `scanner/market_regime.py`

Purpose:

- market-regime snapshot using already-fetched quotes and ranked candidates
- informational only
- no sizing
- no allocation
- no trade management

Current outputs include:

- regime label
- IV level proxy
- IV percentile proxy
- term-structure slope
- skew proxy
- premium richness
- theta richness
- liquidity quality
- whether dynamic structures appear favored
- whether canonical comparison deserves attention
- explanatory notes

### `scanner/models.py`

Updated with:

- efficiency fields on `BatmanCandidate`
- `dte_neighborhoods` on `ScanResult`
- `market_regime` on `ScanResult`

### `scanner/option_chain.py`

Updated so scan results now build and attach:

- ranked candidates with efficiency metrics
- DTE neighborhood rankings
- market regime snapshot
- canonical benchmark
- constrained sweep benchmark

---

## What Still Needs To Be Done Next

### 1. Run validation locally or in Codex Web

Run:

```bash
python -m compileall app.py scanner
```

Then run:

```bash
streamlit run app.py
```

Check both:

- mock mode
- quote-cache mode if data exists

### 2. Wire new backend outputs into Streamlit UI

The backend now attaches:

```python
result.dte_neighborhoods
result.market_regime
candidate.theta_per_credit
candidate.credit_per_spread_risk
candidate.liquidity_adjusted_credit
candidate.shape_adjusted_score
```

The UI should display these in clean expanders, not clutter the main risk-chart workspace.

Add UI sections:

#### Market Regime Snapshot

Show:

- label
- IV level proxy
- IV percentile proxy
- term structure slope
- skew proxy
- premium richness
- theta richness
- liquidity quality
- dynamic favored / canonical favored
- notes

Suggested location:

- above the candidate list or in a collapsed expander near results

#### DTE Neighborhoods

Show top ranked DTE pairs:

- rank
- score
- front expiry / DTE
- back expiry / DTE
- gap
- liquidity
- theta richness
- premium richness
- term structure score
- avg IVs

Suggested location:

- expander titled `DTE Neighborhood Ranking`

#### Candidate Efficiency Metrics

Show a separate expander:

- theta per credit
- positive theta per credit
- credit per spread risk
- theta per spread risk
- theta per absolute delta
- liquidity-adjusted credit
- liquidity-adjusted theta
- shape-adjusted score

Suggested location:

- expander titled `Candidate Efficiency`

### 3. Candidate Diversity / De-duplication

Still not implemented.

Goal:

Avoid top ranked list being near-identical structures.

Simple first version:

- group candidates by front expiry, back expiry, rounded strikes
- keep only best candidate per group
- make optional in Streamlit

### 4. Exact Buddy Comparison Mode

Still not implemented.

Create a report-style comparison mode that makes it easy to compare against buddy scanner output.

Include:

- candidate count
- constructed count
- ranked count
- expiry pairing mode
- exact delta targets
- position delta
- position theta
- D/T ratio
- credit
- score

### 5. Improve Rejection Diagnostics

Add or refine reasons such as:

- no_valid_back_expiry
- invalid_structure
- wide_spread

Current diagnostics already include major leg/credit/delta/theta failures.

---

## UI Integration Guidance

When wiring UI, avoid rewriting the whole `app.py` if possible.

Prefer:

- small helper row functions
- `st.expander()` sections
- `pd.DataFrame(...)`
- no new complex state
- no expensive calculations in UI

Suggested imports in `app.py`:

```python
from scanner.dte_neighborhoods import dte_neighborhood_rows
from scanner.efficiency import efficiency_rows
from scanner.market_regime import market_regime_rows
```

Suggested display helpers:

```python
def show_market_regime(result: ScanResult) -> None:
    if result.market_regime is not None:
        with st.expander("Market Regime Snapshot", expanded=True):
            st.dataframe(pd.DataFrame(market_regime_rows(result.market_regime)), use_container_width=True, hide_index=True)


def show_dte_neighborhoods(result: ScanResult) -> None:
    if result.dte_neighborhoods:
        with st.expander("DTE Neighborhood Ranking", expanded=False):
            st.dataframe(pd.DataFrame(dte_neighborhood_rows(result.dte_neighborhoods)), use_container_width=True, hide_index=True)


def show_candidate_efficiency(result: ScanResult) -> None:
    if result.candidates:
        with st.expander("Candidate Efficiency", expanded=False):
            st.dataframe(pd.DataFrame(efficiency_rows(result.candidates)), use_container_width=True, hide_index=True)
```

Call those helpers after a scan result exists, near the existing quote diagnostics / benchmark sections.

---

## Risk Graph Philosophy

The scanner is NOT intended to replace OptionNet Explorer.

Risk graphs are intended only for:

- quick visual triage
- avoiding obviously poor candidates
- deciding which candidates deserve OptionNet modelling

But risk graph accuracy is important because inaccurate graphs could cause good candidates to be wrongly rejected.

Current risk graph design:

- Black-Scholes style approximation
- calibrated to current option mid values
- supports risk-free rate and dividend yield assumptions
- mid-normalized PnL for cleaner shape comparison
- executable PnL retained separately in the data frame

Do not turn this into a full pricing engine.

---

## Current Development Priority

Priority order:

1. scanner stability
2. compile/run validation
3. risk graph accuracy
4. candidate quality
5. DTE neighborhood intelligence
6. market regime awareness
7. fast live scanning
8. benchmark comparison tools
9. UI polish

NOT:

- broker execution
- automation
- portfolio management
- capital allocation

---

## Important User Workflow

Workflow is:

```text
Scanner -> shortlist -> OptionNet Explorer -> execution decision
```

The scanner is NOT the final source of truth.

The scanner’s job is to surface the best candidates worth manually modelling.

---

## Coding Rules

DO:

- preserve backward compatibility
- preserve scanner stability
- preserve speed
- prefer small modular functions
- prefer deterministic behavior
- keep scanner read-only
- prefer safe fallbacks
- cache external requests
- isolate experimental features
- favor live-trading practicality over theoretical elegance

DO NOT:

- rewrite architecture unnecessarily
- tightly couple UI and scanner logic
- add execution logic
- add async complexity unless necessary
- add fragile external dependencies
- add broker write permissions
- break offline/delayed-data mode
- add portfolio management
- add Kelly sizing systems
- add auto-allocation systems

---

## Before Making Major Changes

Before implementing anything substantial:

1. explain architectural impact
2. explain tradeoffs
3. avoid unnecessary complexity
4. preserve current workflow philosophy

The trader values:

- simplicity
- robustness
- practical usefulness
- speed during live trading
- high-quality candidate discovery
