# Manual CSV and Excel History Input

## Purpose

Canonical manual input is the fallback when SEC Company Facts is unavailable, a company uses an
unsupported tag, or a researcher needs a documented override. It enters the same
`HistoricalStatements` contract as SEC data and therefore receives the same ratios, opening-state
gate, three-statement forecast, DCF, checks, and outputs.

## Excel contract

The workbook must contain:

- `Company`: `field` and `value` columns with `ticker`, `cik`, `company_name`, and `filings_url`;
  fiscal-year end, SIC, description, and entity type are optional.
- `Historical Financials`: one row per `statement + account + fiscal_year`, with required columns
  `statement`, `account`, `fiscal_year`, and `value`.

Optional audit columns are `unit`, `source_name`, `source_reference`, `filing_date`, `confidence`,
and `notes`. Confidence accepts `HIGH`, `MEDIUM`, `LOW`, or `MISSING`.

## CSV contract

CSV uses the same historical columns and repeats `ticker`, `cik`, `company_name`, and `filings_url`
on every row. Conflicting repeated metadata fails clearly.

## Units and validation

- Currency: `USD millions`.
- Diluted shares: `shares millions`.
- EPS: `USD per share`.
- Annual periods only; quarter, YTD, and LTM rows are not accepted as FY history.
- Unknown account/statement pairs, duplicate keys, invalid units, or invalid confidence values fail.
- Optional missing values remain missing; required missing values create quality issues and failing
  completeness checks.
- Imported values use `MANUAL` provenance, retain the supplied source reference, and are never
  presented as direct SEC-selected facts.

## Usage

```bash
python -m fmva.run \
  --history-table data/sample/cost_manual_history_input.xlsx \
  --forecast-assumptions examples/cost/forecast_assumptions.yaml \
  --valuation-assumptions examples/cost/valuation_assumptions.yaml \
  --output outputs/cost_manual
```

The public COST workbook is a reproducible example, not a private research workbook or a source
of current investment conclusions.
