# DCF Methodology

## Market-input audit metadata

Numerical valuation inputs are accompanied by scenario metadata rather than being treated as
timeless constants. The YAML schema supports `valuation_date`, `scenario_name`,
`is_illustrative`, warnings, and field-level source records containing source name, URL, as-of
date, access date, and analyst rationale.

When `is_illustrative: false`, the framework requires dated source records and URLs for the
risk-free rate, equity risk premium, beta, and pre-tax cost of debt. Missing coverage fails
configuration validation before the DCF runs. Illustrative examples remain reproducible but are
visibly labelled and must not be interpreted as current investment research.

## Free cash flow

The MVP values unlevered free cash flow:

```text
UFCF = EBIT × (1 − tax rate)
     + depreciation and amortization
     − capital expenditures
     − change in net working capital
```

Each component comes from the linked forecast rather than an independent valuation input. Missing values and tax rates outside 0–100% are rejected.

## Cost of capital

```text
Cost of equity = risk-free rate + beta × equity risk premium

WACC = equity weight × cost of equity
     + debt weight × pre-tax cost of debt × (1 − tax rate)
```

Debt and equity weights must be nonnegative and sum to one. Market inputs are user-supplied, dated research assumptions; the framework does not silently retrieve or refresh them.

## Discounting

The MVP uses end-of-year discounting:

```text
Discount factor in year t = 1 / (1 + WACC)^t
PV of FCF = UFCF × discount factor
```

Mid-year discounting is a future option and must not be mixed with the end-of-year convention.

## Terminal value

Two methods are supported.

Perpetuity growth:

```text
TV = UFCF(n) × (1 + g) / (WACC − g)
```

`WACC <= g` is invalid and raises an error; the engine never returns a disguised zero value.

Exit multiple:

```text
TV = EBITDA(n) × exit multiple
```

Both methods discount terminal value with the final forecast-period discount factor.

## Enterprise-to-equity bridge

```text
Enterprise value = PV of forecast UFCF + PV of terminal value
Equity value = enterprise value
             − debt
             − preferred stock
             − minority interest
             + cash
             + non-operating investments
Implied share price = equity value / diluted shares
```

Every bridge item is explicit. Diluted shares must be greater than zero, and missing bridge inputs are not silently inferred.

## Sensitivity analysis

The WACC versus terminal-growth table reruns the entire DCF for every cell. It does not apply a percentage adjustment to the final share price. Invalid WACC/g combinations are returned as missing values. Directional tests require value to decrease as WACC rises and increase as terminal growth rises, holding other assumptions constant.
