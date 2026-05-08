# Batman Scanner

Local Python scanner for Batman-style 3-leg call option structures using Interactive Brokers market data.

This app is scanner-only. It does not place orders, submit orders, modify live trades, or automate execution.

## Continuation Status Prompt

If one AI session runs out of usage, paste this into the next session:

```text
Continue building the local Python project at batman-scanner. It is a macOS Streamlit app using ib_insync, SQLite, and modular scanner files. It scans IBKR option chains for 3-leg Batman CALL candidates only; no order placement or live trade modification is allowed. First inspect the current files and git diff, then continue from the checklist in README.md.
```

## MVP Checklist

- [x] Create Git/GitHub-friendly Python project structure.
- [x] Add Streamlit UI that loads without IBKR connected.
- [x] Add sidebar scanner and IBKR connection settings.
- [x] Add read-only IBKR client using `ib_insync`.
- [x] Add Batman candidate construction logic.
- [x] Add scoring components and spread penalty.
- [x] Add SQLite scan history storage.
- [x] Add CSV export with leg-level rows.
- [x] Add clearly labelled mock data mode for UI testing.
- [x] Add bounded live market-data request setting.
- [x] Add IBKR preflight check before full scan.
- [x] Add local SQLite quote cache.
- [x] Add background quote-cache collector.
- [x] Add cache-backed scan path for faster repeated ranking.
- [x] Store implied volatility from IBKR model Greeks when available.
- [x] Add selected-candidate risk chart with projected PnL and Greeks.
- [ ] Test with TWS or IB Gateway paper account.
- [ ] Tune strike filtering and market data pacing after real IBKR testing.

## Setup On macOS

From the parent folder:

```bash
cd batman-scanner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.toml config.local.toml
streamlit run app.py
```

Open the local Streamlit URL printed in the terminal.

## Connect To TWS Or IB Gateway

1. Start TWS or IB Gateway.
2. Use a paper account first.
3. Enable API access:
   - TWS: `Global Configuration` -> `API` -> `Settings`.
   - Check `Enable ActiveX and Socket Clients`.
   - Confirm the socket port:
     - TWS paper: `7497`
     - TWS live: `7496`
     - IB Gateway paper: `4002`
     - IB Gateway live: `4001`
4. Keep `Read-Only API` enabled if available.
5. In Batman Scanner, use host `127.0.0.1`, the matching port, and client ID `11`.
6. Click `Connect to IBKR`.
7. Click `Preflight IBKR` before running a full scan. This checks the underlying, chain metadata, and underlying price without requesting option Greeks.

## What To Test First

1. Run the app with `MOCK DATA` checked and click `Run Scan`.
2. Confirm the candidate table, expandable details, and CSV export work.
3. Start TWS paper trading and click `Connect to IBKR`.
4. Click `Preflight IBKR` and confirm the chain metadata appears.
5. If the market is closed and `underlying_price` is blank, this is normal. You can enter a `Manual underlying price` in the sidebar for strike filtering, and try `Frozen` or `Delayed frozen` in `Market data type`, but live bid/ask/Greeks may still be unavailable until market data is active.
6. Keep `Market data batch size` below your IBKR line limit. The default is `80`, which stays below a 100-line account limit.
7. Set `Max contracts per expiry` low, such as `40` or `60`, for the first live scan.
8. Click `Refresh Quote Cache` and let the background collector populate local SQLite quotes.
9. Leave `Run scan from quote cache` checked and click `Run Scan`.
10. Check skipped-contract warnings. Missing Greeks usually means market data permissions, delayed data, or IBKR model data is unavailable.

## What Is Included

- Conservative entry credit calculation:
  - Short calls use bid.
  - Long calls use ask.
- 3-leg CALL Batman structure:
  - `SC_High`: sell 1 front-expiry call near target delta.
  - `LC_Mid`: buy 2 back-expiry calls near `SC_High delta - offset`.
  - `SC_Low`: sell 1 front-expiry call chosen to bring total trade delta near the target.
- Hard filters for DTE order/gap, positive credit, positive total delta, and required quote/Greek data.
- Scoring modes:
  - `Theta-first Batman` ranks mostly by position theta, then entry credit.
  - `Balanced delta/credit` keeps the original delta, credit, and DTE-anchor score.
  - `Delta/theta ratio` ranks by position-delta efficiency versus theta.
- Score components displayed in the UI:
  - Delta score.
  - Theta score.
  - Credit score.
  - D/T ratio score.
  - DTE anchor score.
  - Spread penalty.
- Position-dollar Greeks displayed in the UI:
  - Position delta.
  - Position theta.
  - Position vega.
  - Position gamma.
  - D/T ratio.
- SQLite scan history in `data/scan_history.db`.
- SQLite quote cache in `data/quote_cache.db`.
- CSV export for top candidates.
- Side-by-side results workspace:
  - compact ranked candidate list
  - selected-candidate risk chart
  - selected leg details without returning to the top of the page
- Selected-candidate risk chart:
  - projected PnL curves across underlying prices
  - multiple projection dates
  - current spot marker
  - T+0 delta, gamma, theta, and vega/100 curves
- IBKR preflight check for underlying, chain metadata, and underlying price.
- `Max contracts per expiry` setting to reduce the first live scan size.
- `Market data batch size` setting to keep simultaneous IBKR market-data requests below account line limits.
- Optional `Manual underlying price` fallback for off-hours strike filtering.
- `Market data type` selector for live, frozen, delayed, and delayed-frozen IBKR data requests.
- Background `Refresh Quote Cache` workflow so repeated scans rank from local cached quotes instead of blocking on IBKR.

## Risk Chart Notes

The built-in risk chart uses a simple Black-Scholes approximation from cached bid/ask, strike, DTE, and implied volatility. If IBKR does not provide implied volatility, the chart falls back to a default IV assumption. Use this chart to compare shapes quickly, then manually model preferred setups in OptionNet Explorer before trading.

## Troubleshooting No Candidates

If the scan reports no candidates during market hours, open `Scan diagnostics` and check the minimum usable delta. Batman scans need far-OTM calls for the low short leg. If the minimum usable delta is still high, for example above 20, refresh the quote cache so the scanner collects a wider upside strike range.

## What Is Intentionally Not Included Yet

- No order placement.
- No automated execution.
- No live trade modification.
- No portfolio management.
- No OptionNet Explorer file-format integration.
- No advanced IBKR pacing/retry system.
- No volatility surface or scenario analysis.
- No Docker.

## Notes

- Market data subscriptions are required for reliable live Greeks.
- If bid, ask, or model delta is missing, the contract is skipped instead of crashing the scan.
- The first live scans may need tuning for your IBKR data permissions and pacing limits.
