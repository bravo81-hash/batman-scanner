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
# External Research References

Reference implementations from trading peers are stored in:

research/external_batman_variants/

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
