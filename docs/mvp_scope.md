# MVP Scope and Development Plan

## Objective

Deliver a reproducible WMT example that retrieves at least five annual periods from SEC EDGAR, standardizes historical statements with provenance, forecasts five years through linked schedules, passes three-statement checks, produces a complete DCF and sensitivity table, and exports Excel, Markdown, and charts.

The reference-model analysis and system design were approved. Phase 0 and the first SEC data-layer slice are implemented; subsequent phases remain incremental acceptance gates.

## Implementation status

| Phase | Status | Current evidence |
|---|---|---|
| Reference analysis and design | Complete | Four design documents reviewed and retained in `docs/`. |
| Phase 0 — Repository foundation | Complete | Git repository, package layout, configuration, logging, exceptions, README, license, privacy rules, and tests. |
| Phase 1 — SEC data layer | Complete live for WMT and AAPL | Client, compression decoding, cache, limiter, ticker/CIK lookup, Company Facts parser, annual selector, synthetic fixtures, and two-company live retrieval. |
| Phase 2 — Standardized history | Complete live for WMT and AAPL | Each public fixture contains five fiscal years and 330 provenance records, no required mapping issues, balanced statements, and exact cash roll-forwards. |
| Phase 3 — Analysis | Complete live for WMT | Historical and forecast growth, profitability, liquidity, leverage, efficiency, cash-flow ratios, warnings, and continuous trend charts are implemented. |
| Phase 4 — Forecast engine | Complete live for WMT draft | FY2027–FY2031 linked schedules include operating normalization, working capital, PP&E, debt/interest, retained earnings, share issuance/repurchases, and passing checks without a plug. |
| Phase 5 — DCF and sensitivity | Complete | UFCF, WACC, both terminal methods, equity bridge, implied price, structured checks, and WACC/g sensitivity are implemented. |
| Phase 6 — Outputs and release readiness | Complete | `ModelResult`, fourteen-sheet blue Excel, Markdown, CSV tables, six PNG charts, versioned WMT fixture, privacy audit, and Python 3.11/3.12 CI workflow. |

## In scope

- U.S. SEC registrants using industrial/non-financial three-statement logic.
- Ticker/CIK lookup and company metadata.
- SEC Company Facts and submissions metadata with compliant User-Agent, retry, timeout, rate limiting, and cache.
- Five or more 10-K annual periods with restatement/amendment handling.
- Canonical mapping for the requested income statement, balance sheet, and cash flow accounts.
- Field-level provenance and a data-quality report.
- Top-down revenue forecast and extensible bottom-up operating interface.
- Linked income statement, working capital, PP&E/depreciation, debt/cash/interest, equity, balance sheet, and cash flow.
- DCF using UFCF, WACC, Gordon growth, exit multiple, equity bridge, and implied price.
- WACC/terminal-growth sensitivity; optional WACC/exit-multiple sensitivity if low-cost.
- Historical and forecast ratios, trend charts, Excel workbook, Markdown report, and checks.
- Python API and CLI matching the requested usage pattern.

## Explicitly out of scope

- Banks, insurers, brokers, REITs, and complex financial groups.
- A-share data ingestion and Chinese PDF OCR.
- Automatic investment recommendations or target-price opinions.
- Automatic peer selection, precedent transactions, LBO, M&A, or quantitative strategies.
- Company-specific bottom-up WMT operating drivers in the first pass.
- Full lease-accounting, pension, tax, foreign-currency, and acquisition submodels.
- Intraperiod quarterly/YTD forecasting and LTM construction.
- Publishing either reference source file.

## Delivery phases

### Phase 0 — Repository foundation

Deliverables:

- `pyproject.toml`, package, CLI/API shell, logging, exceptions, configuration models.
- README skeleton, license, contribution guidance, privacy-safe `.gitignore`.
- Unit/integration test layout and synthetic fixtures.
- Exact exclusions for local reference documents and live caches.

Exit criteria:

- Package installs on Python 3.11+.
- Formatting, linting, typing, and pytest commands are documented.
- No proprietary reference material is tracked.

### Phase 1 — SEC data layer

Deliverables:

- SEC client, ticker/CIK resolution, submissions/company-facts retrieval, cache, rate limiter, retry, timeout.
- Filing and fact models, annual period classifier, amendment/restatement logic.
- WMT integration fixture and AAPL auxiliary mapping fixture if needed.

Exit criteria:

- `get_company("WMT")` returns required identity fields.
- At least five annual WMT periods are identified without using quarterly cumulative values as quarters.
- Repeated runs use cache and produce clear network/configuration errors.

### Phase 2 — Standardized historical statements

Deliverables:

- Declarative account map.
- Candidate ranking, canonical statement builder, unit/sign normalization.
- Historical three statements and field-level provenance.
- Completeness, duplicate, period, unit, and mapping-quality report.

Exit criteria:

- Historical totals reconcile within documented tolerances or failures are explained.
- Missing required accounts are not silently zeroed.
- Each output value traces to accession, tag, filing date, period, unit, and selection method.

### Phase 3 — Historical analysis

Deliverables:

- Ratio definitions and applicability rules.
- Historical growth, profitability, liquidity, leverage, efficiency, and cash-flow analysis.
- Revenue, margin, earnings, CFO/FCF, and cash/debt charts.

Exit criteria:

- Zero denominators and abnormal values create warnings, not infinities.
- Ratio formulas and units are documented and tested.

### Phase 4 — Forecast engine

Implementation order:

1. Assumption models and resolver.
2. Top-down operating model and income statement.
3. Working-capital schedule.
4. Aggregate CapEx/depreciation and PP&E schedule.
5. Debt/cash/interest schedule with bounded convergence.
6. Equity and retained-earnings roll-forward.
7. Balance sheet and cash flow statement.
8. Three-statement orchestration and checks.

Exit criteria:

- Five forecast years.
- Balance sheet, cash, retained earnings, PP&E, and debt checks pass.
- No unexplained cash/equity/other plug.
- Solver convergence diagnostics are visible.

### Phase 5 — DCF and sensitivity

Deliverables:

- UFCF, cost of equity, WACC, both terminal-value methods, discounting, enterprise value, equity bridge, and implied price.
- WACC versus terminal growth sensitivity.
- Valuation validation and check suite.

Exit criteria:

- `WACC <= g`, invalid weights, zero shares, and missing bridge components fail clearly.
- Sensitivity cells recalculate full valuation mechanics.
- DCF components reconcile to enterprise and equity value.

### Phase 6 — Outputs and public release readiness

Deliverables:

- Excel workbook with Summary, Sources/Audit, Historical, Assumptions, schedules, statements, Ratios, DCF, Sensitivity, and Checks.
- Markdown report and static charts.
- WMT example config, reproducibility instructions, limitations, methodology, and disclaimer.

Exit criteria:

- CLI and Python API produce the requested output bundle.
- A clean-environment run is documented.
- Tests pass and public outputs contain no private or paid data.

## Testing strategy

- Unit tests: formulas, sign/unit conversion, period classification, mapping ranking, schedules, ratios, DCF, and checks.
- Property tests where useful: roll-forward identities, discount-factor monotonicity, sensitivity direction under valid assumptions.
- Contract tests: SEC response schemas and cache behavior using pinned fixtures, not uncontrolled live requests.
- Integration tests: WMT historical build and complete synthetic three-statement/DCF run.
- Golden-file tests: small stable tables and Markdown sections; avoid brittle full-workbook binary comparisons.
- Live smoke test: opt-in because it requires contact configuration and network access.

## Key risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| XBRL tag variation and extensions | Missing or incorrect canonical accounts | Priority mappings, candidate scoring, derivations, provenance, manual override, WMT+AAPL fixtures. |
| Duplicate facts and restatements | Wrong historical series | Filing-aware selection, accession/date tracking, later comparative restatement preference, conflict report. |
| FY/Q/YTD confusion | Misstated flows | Duration-based period classifier, form/report-date checks, annual-only MVP filters, dedicated tests. |
| Units and shares differ | Orders-of-magnitude errors | Unit-type validation, explicit USD/shares conversion, scale metadata, sanity checks. |
| SEC access limits or outages | Non-reproducible runs | Valid User-Agent, conservative limiter, retry/backoff, timeout, cache, pinned public fixtures, CSV/Excel fallback. |
| Missing gross profit/COGS/D&A | Broken analysis or DCF | Configured derivations only when components reconcile; otherwise explicit missingness/manual input. |
| Interest/cash/debt circularity | Non-convergence or opaque results | Staged solver, optional bounded iteration, tolerance/max-iteration config, convergence check. |
| Balance achieved through plugs | False model confidence | Plugs disabled by default; typed plug policy, trigger reason, amount, disclosure, and failing/warning check. |
| Cash-flow sign inconsistency | Incorrect cash and FCF | Separate source sign from canonical sign, schedule-to-CFS adapters, identity tests. |
| Fiscal calendars (e.g. 52/53 weeks) | Bad growth/day ratios | Use actual dates/duration days; store fiscal year end and duration; disclose day-count convention. |
| Retailer working capital differs | Weak WMT forecast | Allow negative NWC, use company-relevant days/percent drivers, do not force generic assumptions. |
| Market inputs are time-sensitive | Stale WACC | Require user-supplied valuation date/source; label market assumptions and avoid hidden live providers. |
| Excel formula compatibility | Broken public outputs | Keep calculation truth in Python, export transparent formulas where stable, verify key cells and rendered sheets. |
| Proprietary reference leakage | Licensing/reputation risk | Exact ignore rules, no copied branding/data/layout, pre-commit secret/file checks, public-artifact review. |
| Scope expansion | MVP delay | Enforce explicit out-of-scope list and extension protocols without premature implementation. |

## Proposed milestone acceptance matrix

| Requirement | Phase | Evidence |
|---|---:|---|
| 5+ annual historical years | 1–2 | Historical statement and provenance fixture. |
| 5 forecast years | 4 | Forecast tables and assumption set. |
| Three statements balance | 4 | Structured PASS checks. |
| Cash check passes | 4 | CFS-to-BS cash reconciliation. |
| Complete DCF | 5 | Forecast FCF, discounting, TV, EV, bridge, price. |
| Sensitivity works | 5 | Recalculated DataFrame and export sheet. |
| Tests pass | All | CI test run. |
| README reproducible | 6 | Clean install and WMT example instructions. |
| No private/paid data | 0 and 6 | Repository audit. |
| Reference workbook excluded | 0 | `.gitignore` and tracked-file check. |

## Next gate

Create the first public Git commit and publish the repository without the ignored reference
files, private SEC configuration, caches, or generated local outputs. Confirm the Python 3.11
and 3.12 workflows from a clean GitHub clone. Committed WMT and AAPL valuation cases remain
illustrative by design; live research configurations must replace them with dated, sourced
market inputs using the enforced metadata schema.
