# Financial Analysis Methodology

## General rules

- Ratios use canonical model accounts, not raw XBRL tags.
- Balance-based denominators use average beginning/ending balances where economically appropriate.
- A zero or missing denominator returns null and records a warning; infinity is prohibited.
- Ratios are applicable to the industrial/non-financial MVP profile only.
- Percentage outputs are stored as decimals and formatted as percentages by presentation layers.

## Operating-expense normalization

The generic forecast engine treats SG&A as a cash operating expense excluding separately
modelled depreciation and amortization. When a company reports D&A inside SG&A, the researcher
must normalize the historical driver before forecasting to avoid double counting. Other
operating income is a separate, visible assumption and may capture disclosed membership,
franchise, or similar operating income that is not included in the revenue/COGS mapping. It
must not be used as an unexplained balancing plug.

## Growth

- Revenue growth = current revenue / prior revenue − 1.
- EBITDA growth = current EBITDA / prior EBITDA − 1.
- Net income growth = current net income / prior net income − 1.
- EPS growth = current EPS / prior EPS − 1, when diluted shares are available.
- FCF growth uses CFO less CapEx as the analysis-layer FCF measure.

Growth from a zero or missing prior-period value is null rather than infinite.

## Profitability

- Gross margin = gross profit / revenue.
- EBITDA margin = EBITDA / revenue.
- Operating margin = EBIT / revenue.
- Net margin = net income / revenue.
- ROA = net income / average total assets.
- ROE = net income attributable to parent / average total equity.
- ROIC = NOPAT / average invested capital.
- NOPAT = EBIT × (1 − effective tax rate).
- Invested capital = debt + equity − cash.

## Liquidity

- Current ratio = current assets / current liabilities.
- Quick ratio = (cash + accounts receivable) / current liabilities in the aggregate MVP.
- Cash ratio = cash / current liabilities.

Short-term investments will be included in quick and cash ratios when the live standardized-history adapter supplies them to the forecast state.

## Leverage

- Debt/equity = total short- and long-term debt / total equity.
- Debt/EBITDA = total debt / EBITDA.
- Net debt/EBITDA = (total debt − cash) / EBITDA.
- Interest coverage = EBIT / interest expense.

Net debt may be negative for net-cash companies. This is not automatically treated as an error.

## Efficiency

- Asset turnover = revenue / average assets.
- Inventory turnover = COGS / average inventory.
- Receivables turnover = revenue / average accounts receivable.
- Payables turnover = COGS / average accounts payable.
- DSO, DIO, and DPO come from the working-capital schedule.
- Cash conversion cycle = DSO + DIO − DPO.

## Cash flow

- CFO/net income = cash from operations / net income.
- FCF margin = (CFO − CapEx) / revenue.
- CapEx/revenue = CapEx / revenue.
- Cash conversion ratio = CFO / EBITDA.

The DCF module uses UFCF, which is distinct from the analysis-layer CFO-less-CapEx measure.
