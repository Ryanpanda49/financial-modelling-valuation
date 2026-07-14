# AAPL Compatibility Validation

## Purpose

Apple is the second live SEC registrant used to test whether the canonical data model and linked
forecast are reusable beyond Walmart. The exercise is a framework compatibility test, not Apple
investment research.

## Historical data result

- Source: SEC Company Facts API using the configured compliant User-Agent and local cache.
- CIK: `0000320193`.
- Fiscal years: FY2021–FY2025.
- Canonical observations: 330.
- Required-account quality issues after mapping review: 0.
- Historical balance-sheet checks: 5 PASS.
- Historical cash roll-forwards: 4 PASS.

Apple reports consolidated `NetIncomeLoss` but does not publish a separate minority-interest
allocation in the selected facts. The mapping therefore uses the explicit, auditable rule
`net_income - minority_interest`, with `minority_interest` allowed to be zero only for that
derivation. The minority-interest source field remains missing, and the derived parent-income
provenance contains an analyst-review warning. No silent global missing-to-zero conversion occurs.

## Forecast and DCF regression

- Forecast years: FY2026–FY2030.
- Historical, forecast, debt/interest solver, and DCF checks: all PASS.
- Output bundle: fourteen-sheet blue Excel workbook, Markdown report, fifteen CSV tables, and six
  static blue charts.
- Offline fixture: `data/sample/aapl_fy2021_2025_history.json`.

The illustrative forecast normalizes reported operating expenses so D&A from the fixed-asset
schedule is deducted exactly once. Revenue growth, margins, working-capital days, repurchases,
WACC, and terminal assumptions are researcher-editable compatibility inputs rather than company
guidance or current market conclusions.

## Known limitations

- Other current assets and accrued liabilities are absent from the selected canonical facts and
  use disclosed opening defaults; residual other-asset and other-liability buckets remain visible.
- The model does not yet include product/service segment volumes, geographic drivers, tax
  jurisdiction schedules, or automated comparable-company analysis.
- The illustrative implied share value is a mechanical test result and must not be interpreted as
  an investment recommendation.
