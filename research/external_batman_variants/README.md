# External Batman Variant Research

This folder contains external/reference Batman implementations shared by trading peers.

These files are intentionally isolated from the production scanner architecture.

Purpose:
- research
- optimization ideas
- DTE neighborhood concepts
- benchmark comparisons
- market regime concepts
- alternative scoring philosophies

These are NOT production architecture references.

Do NOT blindly merge logic from these files into the scanner core.

All ideas must first be evaluated against the Batman Scanner philosophy:

- fast live scanning
- deterministic behavior
- stable IBKR integration
- modular architecture
- scanner-only workflow
- OptionNet Explorer remains final modelling authority

Useful concepts discovered from these references:

- DTE neighborhood ranking
- dynamic third-leg derivation
- market regime awareness
- candidate efficiency concepts
- benchmark structures
- premium richness concepts

Concepts intentionally NOT adopted:

- broker execution
- Kelly sizing
- portfolio management
- auto dependency installation
- heavy evolutionary optimization during live scans

Files in this folder should be treated as:

- research material
- conceptual inspiration
- comparison tools

NOT:

- coding standards
- production scanner architecture
- direct implementation templates
