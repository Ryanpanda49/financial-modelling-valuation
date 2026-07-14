# WMT Live SEC Validation

## Validation scope

Validation was performed on 2026-07-14 using SEC Company Facts and submissions metadata for
Walmart Inc. (`WMT`, CIK `0000104169`). The private SEC User-Agent configuration, live response
cache, and generated outputs are excluded from Git.

The standardized annual panel covers FY2022 through FY2026. It contains 330 canonical
account-period observations with field-level accession, tag, filing date, unit, confidence,
selection method, and restatement metadata.

## Mapping changes required by live data

- Added `ReceivablesNetCurrent` and `AccountsReceivableNet` fallbacks for receivables.
- Added current WMT D&A, interest-expense, and prepaid/other-current-asset tags.
- Prioritized cash plus restricted cash because it is the balance reconciled by WMT's cash-flow
  change tag. This produces exact historical cash roll-forwards but requires analyst review
  before treating all restricted cash as excess cash in valuation.
- Derived total liabilities as total assets less total equity when no standalone liabilities
  fact is reported.
- Derived net income attributable to parent as net income less noncontrolling interest when no
  direct generic US-GAAP fact is available.
- Removed required-account missing issues only after a configured derivation succeeds.
- Added gzip/deflate decoding to the SEC transport after the live ticker endpoint returned
  compressed content.

## Historical validation results

- Required canonical accounts: PASS, no remaining required-account issues.
- FY2022–FY2026 balance sheets: PASS with zero difference.
- FY2023–FY2026 cash roll-forwards: PASS with zero difference.
- Period selection: annual 10-K/10-K-A observations only for the historical panel.
- Units: USD millions; diluted shares in millions.

## Forecast normalization

WMT's reported SG&A embeds D&A and does not by itself reconcile revenue, cost of sales, and
operating income because membership and other operating income are economically material.
The forecast therefore uses two explicit researcher inputs:

1. cash SG&A excluding separately modelled D&A; and
2. other operating income as a percentage of revenue.

With the illustrative draft, operating margin runs from approximately 4.1% to 4.4% across
FY2027–FY2031 rather than falling mechanically to approximately 1.1% through double counting.
Share issuance and repurchases are also explicit financing assumptions and roll through cash
and contributed equity.

## Valuation output

The generated workbook uses illustrative, user-editable valuation inputs rather than current
market-data automation. Under the draft assumptions it calculates a 6.78125% WACC and an
illustrative implied value of approximately $51.02 per diluted share. This is a model test, not
an investment recommendation or a validated target price. The workbook includes the full
WACC/terminal-growth sensitivity table.

## Remaining limitations

- Risk-free rate, beta, equity risk premium, debt cost, target capital weights, and terminal
  growth are illustrative researcher assumptions and need dated primary/market sources.
- Cash includes restricted cash for historical CFS reconciliation; an analyst may need to
  exclude unavailable restricted cash from the equity bridge.
- Other assets, other liabilities, and contributed equity use disclosed residual calculations
  in the aggregate MVP model.
- Membership and other operating income remain top-down rather than a bottom-up membership
  schedule.
- Lease liabilities, minority interest, share count changes, tax attributes, and repurchases
  remain simplified relative to a full company-specific model.
- Average-balance ratios and days metrics for FY2022 are intentionally null because FY2021
  opening balances are outside the five-year standardized panel; the workbook records this in
  ratio warnings rather than substituting ending balances silently.
