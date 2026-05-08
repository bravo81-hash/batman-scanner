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
8. Run a small SPX scan and watch the progress messages.
9. Check skipped-contract warnings. Missing Greeks usually means market data permissions, delayed data, or IBKR model data is unavailable.

## What Is Included

- Conservative entry credit calculation:
  - Short calls use bid.
  - Long calls use ask.
- 3-leg CALL Batman structure:
  - `SC_High`: sell 1 front-expiry call near target delta.
  - `LC_Mid`: buy 2 back-expiry calls near `SC_High delta - offset`.
  - `SC_Low`: sell 1 front-expiry call chosen to bring total trade delta near the target.
- Hard filters for DTE order/gap, positive credit, positive total delta, and required quote/Greek data.
- Score components displayed in the UI:
  - Delta score.
  - Credit score.
  - DTE anchor score.
  - Spread penalty.
- SQLite scan history in `data/scan_history.db`.
- CSV export for top candidates.
- IBKR preflight check for underlying, chain metadata, and underlying price.
- `Max contracts per expiry` setting to reduce the first live scan size.
- `Market data batch size` setting to keep simultaneous IBKR market-data requests below account line limits.
- Optional `Manual underlying price` fallback for off-hours strike filtering.
- `Market data type` selector for live, frozen, delayed, and delayed-frozen IBKR data requests.

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
