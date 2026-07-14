# COST Compatibility Validation

## Purpose

Costco is the third live SEC registrant used to test the canonical data model and linked model.
It extends coverage to a second retailer with a membership-led economics profile and a fiscal year
that does not align with the calendar year. This is a framework compatibility test, not Costco
investment research.

## Historical data result

- Source: SEC Company Facts API using the configured compliant User-Agent and local cache.
- CIK: `0000909832`.
- Fiscal years: FY2021–FY2025.
- Canonical observations: 330.
- Required-account quality issues after mapping review: 0.
- Historical balance-sheet checks: 5 PASS.
- Historical cash roll-forwards: 4 PASS.

Costco's selected FY2025 facts do not separately report minority interest. Parent income is
therefore derived using the explicit rule `net_income - minority_interest`, with the optional
component allowed to be zero for this derivation only. The source field remains missing and the
derived observation retains an analyst-review warning.

## Forecast and DCF regression

- Forecast years: FY2026–FY2030.
- Historical, forecast, debt/interest solver, and DCF checks: all PASS.
- Output bundle: fourteen-sheet blue Excel workbook, Markdown report, fifteen CSV tables, and six
  static blue charts.
- Offline fixture: `data/sample/cost_fy2021_2025_history.json`.

The top-down illustrative case anchors gross margin, cash SG&A, working-capital days, CapEx, and
depreciation to recent history. Reported SG&A is normalized to exclude D&A so the fixed-asset
schedule deducts depreciation exactly once. The resulting implied share value is a deterministic
regression value, not a target price.

## Known limitations

- Membership-fee revenue is not separated from merchandise sales in the generic operating model.
- Other current assets are absent from the selected canonical facts and use a disclosed zero
  opening default; residual asset and liability buckets remain visible.
- The model does not capture warehouse openings, comparable sales, renewal rates, membership tiers,
  foreign exchange, 52/53-week calendars, or special-dividend policy as separate drivers.
- All forecast and valuation assumptions are illustrative and must be replaced with dated,
  sourced research inputs before current use.
