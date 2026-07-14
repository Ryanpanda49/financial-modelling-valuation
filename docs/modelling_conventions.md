# Modelling Conventions

## Units

- Financial statement values: USD millions.
- Shares: millions.
- EPS and share price: USD per share.
- Rates are decimals in configuration and displayed as percentages in presentation outputs.
- Working-capital days use 365 days in the MVP. A future fiscal-calendar adapter may use actual 52/53-week durations.

## Signs

- Revenue and income are positive.
- Expenses are positive magnitudes and subtracted in calculations.
- Assets, liabilities, and equity balances are positive.
- CapEx, debt repayment, dividends, and repurchases are positive in schedules.
- Schedule outflows become negative in the cash flow statement.
- Source-signed cash-flow totals and working-capital adjustments preserve their reported direction.
- Treasury stock is a positive contra-equity magnitude when separately modelled.

## Time

- `FY historical` is an annual reported period selected from 10-K/10-K-A facts.
- Model fiscal year is derived from the annual fact's period end year; SEC `fy` is retained separately.
- Forecast years are integer fiscal years and must be consecutive from the opening historical year.
- `LTM`, quarterly, and YTD facts are retained by the data layer but not mixed into the annual MVP.
- Filing date and period end remain separate fields.

## Inputs and calculations

- All editable assumptions are loaded from a YAML assumption set.
- Calculations contain no company-specific hardcoded growth, margin, working-capital, CapEx, debt, or valuation assumptions.
- Optional missing historical values are not automatically set to zero by the standardized data layer.
- A manual opening state may aggregate non-modelled assets, liabilities, and contributed equity, but the opening balance sheet must balance before forecasting.

## Circularity

- The MVP does not use an opaque global circular calculation switch.
- Minimum cash can trigger short-term borrowing.
- Interest is calculated on average beginning/ending short- and long-term debt.
- Incremental borrowing and interest are solved with a bounded fixed-point iteration.
- Iteration count, final delta, tolerance, and convergence status are exported and checked.

## Plugs

- No cash, equity, or generic other-account plug is used.
- Cash is the result of the cash flow statement.
- Aggregated `other_assets`, `other_liabilities`, and `contributed_equity` in the opening state are disclosed static categories, not forecast balancing items.
- A future plug policy, if added, must be opt-in and disclose amount, trigger, rationale, and check status.
