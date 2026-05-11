# Batman Scanner — AI Startup Prompt

This is the single canonical startup prompt for future AI coding sessions.

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
5. Market regime analysis
6. UI rendering

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
# New High-Priority Development Direction

The scanner is evolving toward:

"market-aware dynamic candidate discovery"

The next development phase should focus on:

1. DTE neighborhood intelligence
2. market regime analysis
3. candidate efficiency analysis
4. benchmark comparison workflows
5. maintaining fast live usability

The scanner should become better at answering:

- WHICH structures are attractive today?
- WHICH DTE neighborhoods are currently efficient?
- WHEN do dynamic structures outperform canonical structures?
- WHAT volatility regime currently exists?
- WHICH candidates deserve OptionNet modelling time?

---
# High-Priority Features To Implement

## 1. DTE Neighborhood Ranking Engine

Implement a pre-ranking system for front/back DTE neighborhoods.

Purpose:
- identify efficient expiration pairings BEFORE strike optimization
- avoid blind scanning
- improve theta efficiency
- improve liquidity quality
- improve structure quality

Possible outputs:

- DTE pair heatmap
- theta efficiency by DTE pair
- premium richness by DTE pair
- liquidity quality by DTE pair
- regime-favored neighborhoods

IMPORTANT:
Do NOT brute-force blindly.

Prefer:
- cached chain summaries
- heuristics
- coarse-to-fine scans
- deterministic ranking

Avoid:
- expensive evolutionary optimization during live scans
- nondeterministic behavior
- long blocking scans

---
# 2. Market Regime Scanner (VERY IMPORTANT)

This is now a major feature direction.

The scanner should classify the current market environment.

Potential metrics:

- IV percentile
- IV rank
- term structure steepness
- skew steepness
- premium richness
- theta richness
- convexity opportunity
- volatility expansion/compression
- front/back volatility relationships

Potential outputs:

- "Compressed volatility regime"
- "Expansion risk elevated"
- "Dynamic structures favored"
- "Canonical structures favored"
- "Premium-rich environment"
- "Low edge environment"

IMPORTANT:
This is informational guidance ONLY.

Do NOT:
- recommend position sizing
- recommend capital allocation
- become a portfolio tool

Purpose:
Improve candidate interpretation and trade selection quality.

---
# 3. Candidate Efficiency Metrics

Add better candidate-quality metrics.

Examples:

- theta efficiency
- credit efficiency
- premium density
- liquidity density
- spread-adjusted efficiency
- convexity efficiency
- theta-per-unit-delta
- premium-per-liquidity-risk

Purpose:
Avoid selecting:
- pretty graphs with poor economics
- illiquid structures
- structurally weak candidates

---
# 4. Benchmark Comparison Panels

Add side-by-side comparison panels:

- canonical structure
- constrained sweep structure
- dynamic scanner structure

Purpose:
Help the trader understand:
- regime effects
- structural differences
- whether optimization meaningfully improves the trade

These are educational and analytical tools ONLY.

---
# Recently Completed

- Streamlit macro controls:
  - auto-fetch toggle
  - manual risk-free rate
  - manual dividend yield
  - displayed source and refresh metadata
- Risk chart modelling now receives risk-free rate and dividend yield from one settings path.
- Benchmark comparison panel now displays canonical and constrained-sweep candidates.
- Target-DTE mode is exposed in the sidebar.
- Strike increment controls are exposed in the sidebar.

---
# What Still Needs To Be Implemented

## Candidate Diversity / De-duplication

Avoid the top ranked list being near-identical structures.

Simple first version:

- group candidates by front expiry, back expiry, and rounded strikes
- keep only the best candidate per group
- make this optional in Streamlit

---
## Exact Buddy Comparison Mode

Create a report-style mode that makes it easy to compare against buddy scanner output.

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

---
## Improve Rejection Diagnostics

Add or refine rejection reasons such as:

- no_valid_back_expiry
- invalid_structure
- wide_spread

Current rejection diagnostics already include the major leg/credit/delta/theta failures.

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
4. DTE neighborhood intelligence
5. market regime awareness
6. fast live scanning
7. benchmark comparison tools
8. UI polish

NOT:
- broker execution
- automation
- portfolio management
- capital allocation

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
- high-quality candidate discovery
