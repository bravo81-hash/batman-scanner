# Trade Outcome Diagnosis Streamlit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a selected-candidate `Trade Outcome Diagnosis` panel to the Streamlit right-side workspace.

**Architecture:** Keep diagnostic logic in `scanner.trade_diagnostics`; add small pure helpers in `app.py` for defaults, market snapshot conversion, report summary rows, and Streamlit rendering. Tests exercise helper behavior and avoid browser-level Streamlit assertions.

**Tech Stack:** Python, Streamlit, pandas, unittest, existing `scanner.trade_diagnostics` dataclasses and functions.

---

## File Structure

- Modify: `app.py`
  - Import diagnostic engine symbols.
  - Add `DIAGNOSIS_MARKET_SYMBOLS`.
  - Add helper functions:
    - `candidate_diagnosis_defaults(candidate: BatmanCandidate) -> dict[str, float | str]`
    - `diagnosis_market_points_from_rows(rows: dict[str, dict[str, float | None]]) -> dict[str, MarketPoint]`
    - `diagnosis_summary_rows(report: DiagnosticReport) -> list[dict[str, str]]`
    - `build_diagnostic_input(...) -> DiagnosticInput`
    - `show_trade_outcome_diagnosis(candidate: BatmanCandidate) -> None`
  - Call `show_trade_outcome_diagnosis(selected_candidate)` from the right-side workspace after risk chart assumptions and before benchmark/order sections.
- Modify: `tests/test_app_layout.py`
  - Import new helpers.
  - Add focused tests for defaults, market snapshot conversion, incomplete inputs, and summary rows.

---

### Task 1: Add Candidate Diagnosis Defaults

**Files:**
- Modify: `tests/test_app_layout.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing test**

Add the new import names in `tests/test_app_layout.py`:

```python
from app import (
    benchmark_candidate_rows,
    candidate_diagnosis_defaults,
    candidate_order_defaults,
    candidate_picker_label,
    candidate_rows,
    diagnosis_market_points_from_rows,
    diagnosis_summary_rows,
    macro_assumption_rows,
    rejection_reason_rows,
    risk_chart_spot_price,
    selected_candidate_summary,
)
```

Add this test method to `AppLayoutTests` after `test_candidate_rows_include_theta_first_ranking_fields`:

```python
    def test_candidate_diagnosis_defaults_prefill_selected_candidate_context(self) -> None:
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote("2027-01-15", 5200, 55, 35, 36),
            lc_mid=quote("2027-04-16", 5600, 33, 12, 13),
            front_quotes=[quote("2027-01-15", 6000, 8, 3, 4)],
            target_total_delta=3,
            settings=ScanSettings(),
        )
        assert candidate is not None

        defaults = candidate_diagnosis_defaults(candidate)

        self.assertEqual(defaults["strategy"], "batman")
        self.assertAlmostEqual(float(defaults["entry_delta"]), candidate.position_delta)
        self.assertAlmostEqual(float(defaults["current_delta"]), candidate.position_delta)
        self.assertAlmostEqual(float(defaults["entry_vega"]), candidate.position_vega)
        self.assertAlmostEqual(float(defaults["current_vega"]), candidate.position_vega)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run python -m unittest tests.test_app_layout.AppLayoutTests.test_candidate_diagnosis_defaults_prefill_selected_candidate_context -v
```

Expected: FAIL or ERROR because `candidate_diagnosis_defaults` is not defined/importable.

- [ ] **Step 3: Write minimal implementation**

In `app.py`, add these imports near the other scanner imports:

```python
from scanner.trade_diagnostics import (
    DiagnosticInput,
    DiagnosticReport,
    MarketPoint,
    build_market_points,
    diagnose,
)
```

Add this constant after `st.set_page_config(...)`:

```python
DIAGNOSIS_MARKET_SYMBOLS: tuple[str, ...] = ("SPX", "VIX", "VIX9D", "VIX1D", "VIX3M", "VIX6M", "VVIX")
```

Add this helper after `candidate_rows`:

```python
def candidate_diagnosis_defaults(candidate: BatmanCandidate) -> dict[str, float | str]:
    """Return selected-candidate defaults for trade outcome diagnosis."""
    return {
        "strategy": "batman",
        "entry_delta": round(candidate.position_delta, 2),
        "current_delta": round(candidate.position_delta, 2),
        "entry_vega": round(candidate.position_vega, 2),
        "current_vega": round(candidate.position_vega, 2),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run python -m unittest tests.test_app_layout.AppLayoutTests.test_candidate_diagnosis_defaults_prefill_selected_candidate_context -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_layout.py
git commit -m "test: cover diagnosis candidate defaults"
```

---

### Task 2: Add Market Snapshot and Summary Helpers

**Files:**
- Modify: `tests/test_app_layout.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing tests**

Add these test methods to `AppLayoutTests` after the candidate diagnosis defaults test:

```python
    def test_diagnosis_market_points_from_rows_keeps_partial_symbols(self) -> None:
        points = diagnosis_market_points_from_rows(
            {
                "spx": {"open": 7415.0, "now": 7374.0},
                "vix": {"open": 19.25, "now": None},
                "vvix": {"open": None, "now": None},
            }
        )

        self.assertEqual(points["SPX"].open, 7415.0)
        self.assertEqual(points["SPX"].now, 7374.0)
        self.assertEqual(points["VIX"].open, 19.25)
        self.assertIsNone(points["VIX"].now)
        self.assertNotIn("VVIX", points)

    def test_diagnosis_summary_rows_include_report_headline_fields(self) -> None:
        report = diagnose(
            DiagnosticInput(
                strategy="batman",
                trade_pnl=-450,
                market_points=diagnosis_market_points_from_rows(
                    {
                        "SPX": {"open": 7415.0, "now": 7374.0},
                        "VIX9D": {"open": 16.81, "now": 17.45},
                        "VIX1D": {"open": 10.51, "now": 12.07},
                    }
                ),
            )
        )

        rows = diagnosis_summary_rows(report)

        self.assertEqual(rows[0]["field"], "Verdict")
        self.assertEqual(rows[0]["value"], "red trade")
        self.assertIn({"field": "Primary driver", "value": report.primary_driver}, rows)
        self.assertIn({"field": "Bias", "value": report.bias}, rows)
```

Add this import near the top of `tests/test_app_layout.py`:

```python
from scanner.trade_diagnostics import DiagnosticInput, diagnose
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run python -m unittest \
  tests.test_app_layout.AppLayoutTests.test_diagnosis_market_points_from_rows_keeps_partial_symbols \
  tests.test_app_layout.AppLayoutTests.test_diagnosis_summary_rows_include_report_headline_fields \
  -v
```

Expected: FAIL or ERROR because `diagnosis_market_points_from_rows` and `diagnosis_summary_rows` are not defined/importable.

- [ ] **Step 3: Write minimal implementation**

In `app.py`, add these helpers after `candidate_diagnosis_defaults`:

```python
def diagnosis_market_points_from_rows(rows: dict[str, dict[str, float | None]]) -> dict[str, MarketPoint]:
    """Convert editable diagnosis market rows into normalized market points."""
    raw: dict[str, tuple[float | None, float | None]] = {}
    for symbol, values in rows.items():
        open_value = values.get("open")
        now_value = values.get("now")
        if open_value is None and now_value is None:
            continue
        raw[symbol] = (open_value, now_value)
    return build_market_points(raw)


def diagnosis_summary_rows(report: DiagnosticReport) -> list[dict[str, str]]:
    """Return compact summary rows for a diagnosis report."""
    return [
        {"field": "Verdict", "value": report.verdict},
        {"field": "Regime", "value": report.regime},
        {"field": "Primary driver", "value": report.primary_driver},
        {"field": "Bias", "value": report.bias},
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run python -m unittest \
  tests.test_app_layout.AppLayoutTests.test_diagnosis_market_points_from_rows_keeps_partial_symbols \
  tests.test_app_layout.AppLayoutTests.test_diagnosis_summary_rows_include_report_headline_fields \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_layout.py
git commit -m "test: cover diagnosis display helpers"
```

---

### Task 3: Render Trade Outcome Diagnosis Panel

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app_layout.py`

- [ ] **Step 1: Write the failing integration-adjacent test**

Add `build_diagnostic_input` to the app imports in `tests/test_app_layout.py`:

```python
from app import (
    benchmark_candidate_rows,
    build_diagnostic_input,
    candidate_diagnosis_defaults,
    candidate_order_defaults,
    candidate_picker_label,
    candidate_rows,
    diagnosis_market_points_from_rows,
    diagnosis_summary_rows,
    macro_assumption_rows,
    rejection_reason_rows,
    risk_chart_spot_price,
    selected_candidate_summary,
)
```

Add this test method to `AppLayoutTests` after the diagnosis summary rows test:

```python
    def test_diagnosis_helpers_build_report_with_incomplete_snapshot(self) -> None:
        candidate = build_batman_candidate(
            symbol="SPX",
            front_expiry="2027-01-15",
            back_expiry="2027-04-16",
            front_dte=253,
            back_dte=344,
            sc_high=quote("2027-01-15", 5200, 55, 35, 36),
            lc_mid=quote("2027-04-16", 5600, 33, 12, 13),
            front_quotes=[quote("2027-01-15", 6000, 8, 3, 4)],
            target_total_delta=3,
            settings=ScanSettings(),
        )
        assert candidate is not None
        defaults = candidate_diagnosis_defaults(candidate)

        diagnostic_input = build_diagnostic_input(
            strategy=str(defaults["strategy"]),
            trade_pnl=0.0,
            entry_delta=float(defaults["entry_delta"]),
            current_delta=float(defaults["current_delta"]),
            entry_vega=float(defaults["entry_vega"]),
            current_vega=float(defaults["current_vega"]),
            market_rows={"SPX": {"open": 7415.0, "now": None}},
        )
        report = diagnose(diagnostic_input)

        self.assertEqual(report.verdict, "flat trade")
        self.assertGreaterEqual(len(report.signals), 1)
        self.assertGreaterEqual(len(diagnosis_summary_rows(report)), 4)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run python -m unittest tests.test_app_layout.AppLayoutTests.test_diagnosis_helpers_build_report_with_incomplete_snapshot -v
```

Expected: FAIL or ERROR because `build_diagnostic_input` is not defined/importable.

- [ ] **Step 3: Add the diagnostic input builder**

In `app.py`, add this helper after `diagnosis_summary_rows`:

```python
def build_diagnostic_input(
    *,
    strategy: str,
    trade_pnl: float,
    entry_delta: float | None,
    current_delta: float | None,
    entry_vega: float | None,
    current_vega: float | None,
    market_rows: dict[str, dict[str, float | None]],
) -> DiagnosticInput:
    """Build a deterministic diagnosis input from app form values."""
    return DiagnosticInput(
        strategy=strategy,
        trade_pnl=trade_pnl,
        entry_delta=entry_delta,
        current_delta=current_delta,
        entry_vega=entry_vega,
        current_vega=current_vega,
        market_points=diagnosis_market_points_from_rows(market_rows),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
uv run python -m unittest tests.test_app_layout.AppLayoutTests.test_diagnosis_helpers_build_report_with_incomplete_snapshot -v
```

Expected: PASS.

- [ ] **Step 5: Add the Streamlit renderer**

In `app.py`, add this function after `show_risk_chart`:

```python
def show_trade_outcome_diagnosis(candidate: BatmanCandidate) -> None:
    """Render deterministic trade outcome diagnostics for the selected candidate."""
    defaults = candidate_diagnosis_defaults(candidate)

    with st.expander("Trade Outcome Diagnosis", expanded=False):
        st.caption("Deterministic diagnostics only. Use this to separate spot, vol-curve, Greek, and mark pressure before making trade decisions.")

        top_cols = st.columns([1, 1, 1])
        with top_cols[0]:
            strategy = st.text_input(
                "Strategy",
                value=str(defaults["strategy"]),
                key=f"diagnosis_strategy_{candidate.rank}",
            )
            trade_pnl = st.number_input(
                "Trade PnL",
                value=0.0,
                step=25.0,
                key=f"diagnosis_trade_pnl_{candidate.rank}",
            )
        with top_cols[1]:
            entry_delta = st.number_input(
                "Entry delta",
                value=float(defaults["entry_delta"]),
                step=0.5,
                key=f"diagnosis_entry_delta_{candidate.rank}",
            )
            current_delta = st.number_input(
                "Current delta",
                value=float(defaults["current_delta"]),
                step=0.5,
                key=f"diagnosis_current_delta_{candidate.rank}",
            )
        with top_cols[2]:
            entry_vega = st.number_input(
                "Entry vega",
                value=float(defaults["entry_vega"]),
                step=1.0,
                key=f"diagnosis_entry_vega_{candidate.rank}",
            )
            current_vega = st.number_input(
                "Current vega",
                value=float(defaults["current_vega"]),
                step=1.0,
                key=f"diagnosis_current_vega_{candidate.rank}",
            )

        st.write("Open/current market snapshot")
        market_rows: dict[str, dict[str, float | None]] = {}
        for symbol in DIAGNOSIS_MARKET_SYMBOLS:
            cols = st.columns([0.25, 0.375, 0.375])
            cols[0].write(symbol)
            open_value = cols[1].number_input(
                f"{symbol} open",
                value=None,
                step=0.01,
                key=f"diagnosis_{candidate.rank}_{symbol.lower()}_open",
                label_visibility="collapsed",
                placeholder="open",
            )
            now_value = cols[2].number_input(
                f"{symbol} now",
                value=None,
                step=0.01,
                key=f"diagnosis_{candidate.rank}_{symbol.lower()}_now",
                label_visibility="collapsed",
                placeholder="now",
            )
            market_rows[symbol] = {"open": open_value, "now": now_value}

        report = diagnose(
            build_diagnostic_input(
                strategy=strategy,
                trade_pnl=float(trade_pnl),
                entry_delta=float(entry_delta),
                current_delta=float(current_delta),
                entry_vega=float(entry_vega),
                current_vega=float(current_vega),
                market_rows=market_rows,
            )
        )

        st.dataframe(pd.DataFrame(diagnosis_summary_rows(report)), use_container_width=True, hide_index=True)
        st.write(report.summary)

        if report.signals:
            st.write("Why red / why green")
            st.dataframe(
                pd.DataFrame([signal.__dict__ for signal in report.signals]),
                use_container_width=True,
                hide_index=True,
            )
        if report.snapshot_rows:
            with st.expander("Market Snapshot", expanded=False):
                st.dataframe(pd.DataFrame(report.snapshot_rows), use_container_width=True, hide_index=True)
        if report.ratio_rows:
            st.write("Term-structure ratios")
            st.dataframe(pd.DataFrame(report.ratio_rows), use_container_width=True, hide_index=True)
        if report.action_rows:
            st.write("Adjustment bias checklist")
            st.dataframe(pd.DataFrame(report.action_rows), use_container_width=True, hide_index=True)
```

Then call the renderer in `show_results_workspace` after the `Risk Chart Assumptions` expander and before `benchmark_rows`:

```python
        show_trade_outcome_diagnosis(selected_candidate)
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run python -m unittest tests.test_app_layout -v
```

Expected: PASS.

- [ ] **Step 7: Run broader test suite**

Run:

```bash
uv run python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 8: Manually smoke-test Streamlit startup**

Run:

```bash
uv run streamlit run app.py --server.port 8507
```

Expected: Streamlit starts and prints a local URL. In the UI, run with mock data, select a candidate, expand `Trade Outcome Diagnosis`, enter sample SPX/VIX values, and confirm summary/signals/ratio/action tables render.

- [ ] **Step 9: Commit**

```bash
git add app.py tests/test_app_layout.py
git commit -m "feat: add trade outcome diagnosis panel"
```

---

## Self-Review Notes

- Spec coverage: The plan covers selected-candidate prefill, manual market snapshot, deterministic report rendering, incomplete input tolerance, and out-of-scope boundaries by reusing `scanner.trade_diagnostics`.
- Placeholder scan: No unresolved implementation placeholders are included.
- Type consistency: Helper names and imported types are consistent across tests and implementation steps.
