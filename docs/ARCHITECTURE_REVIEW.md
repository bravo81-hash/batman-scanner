# Batman Scanner — Architecture Review and Next Steps

## Overall Assessment

The current scanner implementation is directionally correct and already more practical for live trading than the original command-line research scanner.

The project currently has:

- Dynamic DTE scanning
- Dynamic delta targeting
- Conservative live-trading credit assumptions
- IBKR integration
- Quote caching
- Risk charting
- SQLite scan history
- Streamlit UI
- Mock mode
- No order placement logic

The overall architecture is strong and suitable for iterative development.

---

# Core Batman Logic Validation

## Current construction logic

The current scanner correctly implements:

1. SC_High
   - Front expiry short call
   - Selected by nearest target delta
   - Typically around 45–60 delta

2. LC_Mid
   - Back expiry long call
   - Quantity = 2
   - Selected using:

   LC_Mid delta ≈ SC_High delta - offset

3. SC_Low
   - Front expiry short call
   - NOT fixed 7 delta
   - Selected dynamically to bring TOTAL POSITION DELTA close to target_trade_delta

This matches the intended strategy design.

Approximate example:

- short 54 delta = -54
- long 2 x 32 delta = +64
- short ~7 delta = -7
- total position delta ≈ +3

The scanner currently solves the final short call dynamically, which is the correct interpretation.

---

# What Is Already Better Than The Original Scanner

## 1. Conservative pricing assumptions

Current implementation:

- short legs priced at bid
- long legs priced at ask

This is more realistic than mid-price ranking and should produce more executable rankings.

---

## 2. Quote cache architecture

The quote cache + background collector design is excellent.

Benefits:

- faster rescans
- reduced IBKR throttling risk
- ability to rerank structures without requesting new market data
- cleaner live workflow

This is one of the strongest architectural choices in the project.

---

## 3. Streamlit workspace layout

The current workflow:

Candidate list
→ Risk chart
→ Leg inspection
→ CSV export

is already very practical for live discretionary trading.

---

## 4. Separation of concerns

The codebase is modular and reasonably clean:

- ibkr_client.py
- option_chain.py
- scoring.py
- batman.py
- quote_cache.py
- collector.py
- risk_chart.py

This will scale well.

---

# Highest Priority Improvements

## PRIORITY 1 — Add Expiry Pairing Modes

Current scanner:

- scans ALL valid front/back DTE pairs

Original scanner likely used:

- near expiry
- first later expiry satisfying minimum spread

Add setting:

Expiry Pairing Mode:

1. all_pairs
2. adjacent_only
3. first_valid_far

This will allow exact reproduction of the original scanner behavior.

---

## PRIORITY 2 — Add Strategy Presets

Add preset system:

### Preset: Buddy 54-32-3

- SC_High target = 54
- LC_Mid offset = 22
- target_trade_delta = 3
- theta_first scoring
- adjacent expiry pairing

### Preset: Dynamic Batman Grid

- SC_High range = 45–60
- dynamic offsets
- dynamic target deltas

### Preset: Live Conservative

- tighter spread filters
- positive theta required
- narrower DTE ranges

---

## PRIORITY 3 — Add Positive Theta Filter

Current theta-first scoring can still allow theta-negative setups.

Add optional filters:

- require_position_theta_positive
- max_theta_drag

Recommended default:

position_theta > 0

---

## PRIORITY 4 — Improve Far OTM Strike Coverage

Current strike window:

spot * 0.75 → spot * 1.45

This may exclude useful far OTM short calls in high-volatility or far-DTE environments.

Add configurable setting:

upside_strike_multiplier:

- 1.45
- 1.60
- 1.80
- 2.00

Recommended default:

1.60

---

## PRIORITY 5 — Add Hard Structural Rules

Recommended hard rules:

- SC_Low strike > SC_High strike
- SC_High and SC_Low cannot be same contract
- LC_Mid expiry must equal back expiry
- SC_High and SC_Low expiry must equal front expiry

Avoid fallback behavior unless explicitly enabled.

---

# Recommended Future Architecture

## Phase 1 — Current MVP

Goal:

Reliable live scanner.

Features:

- IBKR integration
- quote cache
- rankings
- risk chart
- CSV export

DO NOT add auto execution yet.

---

## Phase 2 — Research Layer

Add:

- regime tagging
- scan persistence analytics
- historical ranking outcomes
- IV rank
- VIX filters
- skew metrics
- realized volatility

---

## Phase 3 — Portfolio Layer

Add:

- portfolio Greeks
- overlapping position analysis
- adjustment suggestions
- live monitoring dashboard

---

# Important Long-Term Insight

The likely edge is NOT simply:

- fixed 54-32-7 deltas
- or raw theta harvesting

The likely edge is:

- convexity structure
- calendar/diagonal behavior
- stable positive delta
- favorable theta profile
- dynamic strike adaptation
- regime-sensitive DTE relationships

This means:

The scanner should remain:

- dynamic
- constrained
- structure-aware

Avoid over-optimizing isolated metrics.

---

# Recommended Immediate Next Development Tasks

## Task 1

Add expiry pairing modes.

---

## Task 2

Add strategy presets.

---

## Task 3

Add positive theta filters.

---

## Task 4

Improve strike window configurability.

---

## Task 5

Create side-by-side comparison mode:

- original buddy logic
- current enhanced logic

This will help validate whether enhancements improve real trading quality.

---

# Final Assessment

The project is already:

- structurally sound
- modular
- extensible
- practical for live discretionary trading

The quote cache architecture, risk visualization workflow, and dynamic total-delta targeting are especially strong design choices.

The scanner is no longer merely replicating the original research tool.

It is evolving into a professional discretionary systematic options trading workstation.
