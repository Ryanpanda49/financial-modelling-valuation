# MSFT Live Dimensional XBRL Validation

## Scope

The live validation used Microsoft's FY2025 Form 10-K accession
`0000950170-25-100235`. The command resolved MSFT to CIK `0000789019`, selected the requested 10-K,
read its SEC filing-directory index, located `msft-20250630_htm.xml`, and retrieved it through the
same User-Agent, rate-limit, retry, timeout, and cache policy as Company Facts.

## Result

- 1,590 numeric instance facts parsed without executing external taxonomy formulas.
- Actual segment axis: `StatementBusinessSegmentsAxis`.
- Revenue concept: `RevenueFromContractWithCustomerExcludingAssessedTax`.
- Segment COGS concept: `CostOfGoodsAndServicesSold`.
- Three segment members and FY2023–FY2025 annual contexts mapped.
- 18 canonical business KPI records produced.
- All 18 records contain source identity and are direct XBRL facts.
- FY2023 and FY2024 are flagged as recast comparative periods; FY2025 is not.
- Extracted numeric values match the existing reviewed public sample with maximum absolute
  difference of USD 0 million.

The mapping retains fallback aliases for filings that use `OperatingSegmentsAxis`,
`RevenueFromExternalCustomers`, or `CostOfRevenue`. Alias selection is explicit in YAML.

## Reproduction

Live SEC access requires a private configuration containing a real monitored contact address:

```bash
python -m fmva.cli business-kpis \
  --identifier MSFT \
  --config config/model_config.yaml \
  --accession 0000950170-25-100235 \
  --mapping config/business_kpi_mapping.msft.yaml \
  --output outputs/msft_live_instance/msft_business_kpis.csv \
  --quality-output outputs/msft_live_instance/quality.json
```

Runtime cache files, private configuration, and generated outputs remain excluded from Git.

## Limitations

- The selector currently searches the recent submissions arrays; older accessions listed only in
  historical submissions files require a later extension.
- Company-specific concept/member mappings still require review before use.
- Typed dimensions are retained by the parser but not exercised by this MSFT segment case.
- A successful historical extraction does not establish forecast accuracy.
