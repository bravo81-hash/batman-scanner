"""CLI entry point for strategy outcome diagnostics.

Example:

python diagnose_trade.py \
  --strategy batman \
  --trade-pnl -450 \
  --spx-open 7415 --spx-now 7374 \
  --vix-open 19.25 --vix-now 18.55 \
  --vix9d-open 16.81 --vix9d-now 17.45 \
  --vix1d-open 10.51 --vix1d-now 12.07
"""

from __future__ import annotations

import argparse

from scanner.trade_diagnostics import (
    DiagnosticInput,
    build_market_points,
    diagnose,
    format_cli_report,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Strategy outcome diagnostics")
    p.add_argument("--strategy", default="batman")
    p.add_argument("--trade-pnl", type=float, default=0.0)

    symbols = ["spx", "vix", "vix9d", "vix1d", "vix3m", "vix6m", "vvix"]
    for symbol in symbols:
        p.add_argument(f"--{symbol}-open", type=float)
        p.add_argument(f"--{symbol}-now", type=float)

    p.add_argument("--entry-delta", type=float)
    p.add_argument("--current-delta", type=float)
    p.add_argument("--entry-vega", type=float)
    p.add_argument("--current-vega", type=float)

    return p


def main() -> None:
    args = parser().parse_args()

    market_inputs = {}
    for symbol in ["SPX", "VIX", "VIX9D", "VIX1D", "VIX3M", "VIX6M", "VVIX"]:
        key = symbol.lower()
        open_value = getattr(args, f"{key}_open")
        now_value = getattr(args, f"{key}_now")
        if open_value is not None or now_value is not None:
            market_inputs[symbol] = (open_value, now_value)

    report = diagnose(
        DiagnosticInput(
            strategy=args.strategy,
            trade_pnl=args.trade_pnl,
            entry_delta=args.entry_delta,
            current_delta=args.current_delta,
            entry_vega=args.entry_vega,
            current_vega=args.current_vega,
            market_points=build_market_points(market_inputs),
        )
    )

    print(format_cli_report(report))


if __name__ == "__main__":
    main()
