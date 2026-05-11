# Batman Scanner — AI Startup Prompt

Use this prompt when opening this repository in VS Code with Claude/Codex/ChatGPT.

---

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

The scanner should help shortlist trades worth modelling further in OptionNet Explorer.

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
- unnecessary complexity
- Docker

---
# Core Strategy Understanding

Batman structure:

- Short call ~54 delta
- Long 2x calls ~32 delta
- Short call low delta (~7 delta typical)

Combined position delta target:

- approximately +3 position delta

Example:

-54
+64
-7
=
+3

The scanner evolved from fixed canonical structures into a dynamic scanner.

Current philosophy:

- keep ALL THREE LEGS dynamic
- optimize based on total position characteristics
- avoid hardcoded deltas where possible
- canonical structures are benchmarks only

---
# Important Architectural Rules

The project intentionally separates:

1. Candidate generation
2. Scoring/ranking
3. Risk modelling
4. Benchmark structures
5. UI rendering

DO NOT tightly couple these systems.

---
# Current Scanner Philosophy

Primary scanner:

- dynamic Batman structures
- dynamic DTE pairing
- dynamic deltas
- total-position optimization
- scoring-based ranking

Benchmark/reference systems:

- canonical 54/32/7 structures
- constrained optimizer sweeps
- research-only comparison tools

Benchmarks MUST NOT replace the primary scanner.

---
# Current Important Features Already Implemented

## Dynamic Scanner

- dynamic total-delta scanner
- dynamic DTE pairing
- dynamic strike selection
- liquidity filtering
- theta scoring
- shape quality scoring
- spread penalty scoring
- delta/theta ratio scoring

## Risk Graph System

Risk graph logic was upgraded and corrected.

The scanner is NOT intended to fully replace OptionNet Explorer.

Risk graphs are intended ONLY for:
- quick visual triage
- avoiding obviously poor candidates
- deciding which candidates deserve OptionNet modelling

Risk graph accuracy is therefore VERY important.

But:
- simplicity
- speed
- robustness

still matter more than full institutional pricing models.

---
# Macro Modelling Inputs

A safe macro modelling layer was added.

File:

scanner/macro_data.py

Purpose:
- optional risk-free rate auto-fetch
- optional dividend yield assumptions
- risk-chart-only modelling

VERY IMPORTANT:
These values MUST NOT destabilize:
- scans
- ranking
- quote fetching
- IBKR integration

Macro inputs affect ONLY:
- Black-Scholes assumptions
- theoretical risk chart calculations
- modelling projections

NOT live candidate generation.

---
# What Still Needs To Be Implemented

## 1. Streamlit UI Integration For Macro Inputs

Wire into sidebar:

- auto-fetch toggle
- manual override fields
- source label
- last refresh timestamp

Required behavior:

AUTO MODE:
- use macro_data.resolve_macro_inputs()

MANUAL MODE:
- use user-entered values

Must fail gracefully.

Scanner must NEVER fail because macro fetch failed.

---
# 2. Risk Chart Integration

Propagate:

- risk_free_rate
- dividend_yield

through all Black-Scholes / modelling paths.

Ensure:
- consistent calculations
- no mixed assumptions
- no duplicated logic

IMPORTANT:
Use ONE central modelling assumptions source.

---
# 3. Benchmark UI Panels

Add UI sections for:

- canonical candidate
- constrained sweep candidates

Purpose:
- compare scanner output vs benchmark structures
- help trader understand market regime

These are comparison tools ONLY.

---
# 4. Target DTE Mode UI

Support UI controls for:

- range mode
- target mode
- front target DTE
- back target DTE
- tolerance

This was already added to backend models.

Need clean Streamlit integration.

---
# 5. Strike Increment UI

Expose:

- any strike
- 5-point
- 10-point
- 25-point

This improves:
- practical execution
- cleaner modelling
- faster scans

---
# Important Coding Rules

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

DO NOT:

- rewrite architecture unnecessarily
- tightly couple UI and scanner logic
- add execution logic
- add async complexity unless necessary
- add fragile external dependencies
- add broker write permissions
- break offline/delayed-data mode

---
# Important User Workflow

Workflow is:

Scanner -> shortlist -> OptionNet Explorer -> execution decision

The scanner is NOT the final source of truth.

But:

If the scanner risk graph is materially inaccurate,
then good trades may be incorrectly rejected.

Therefore:
- risk graphs must be directionally and structurally accurate
- values should be reasonably realistic
- speed and robustness still matter

---
# Current Development Priority

Priority order:

1. scanner stability
2. risk graph accuracy
3. candidate quality
4. fast live scanning
5. benchmark comparison tools
6. UI polish

NOT:
- broker execution
- automation
- portfolio management

---
# Before Making Major Changes

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
