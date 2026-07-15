# Data directories

Runtime SEC responses are stored under `data/cache/` and are ignored by Git. Only small,
auditable public or synthetic samples may be committed under `data/sample/`.

## Public sample data

`sample/wmt_fy2022_2026_history.json` is a versioned, standardized snapshot derived solely
from Walmart's public SEC Company Facts. It contains canonical values, filing lineage, and
quality metadata, but no SEC request headers, personal contact details, or cache metadata.

`sample/aapl_fy2021_2025_history.json` provides the same contract for Apple and is used to
verify that the canonical mapping and linked model are not retailer-specific.

`sample/cost_fy2021_2025_history.json` adds Costco as a third registrant, covering a
membership retailer and a fiscal year that does not align with the calendar year.

`sample/ko_fy2021_2025_history.json` and `sample/msft_fy2021_2025_history.json` extend the
matrix to consumer brands and technology, including debt fallbacks, R&D, intangible assets,
short-term investments, and capital-intensive cloud infrastructure.

`sample/cost_manual_history_input.xlsx` is a blue, auditable example of the canonical Excel
fallback contract. It contains only public COST SEC data and can be copied for researcher-supplied
history. The workbook is tested end to end against the same model result as the JSON fixture.

`sample/msft_business_kpis_fy2023_2025.csv` is a separate long-form operating KPI table sourced
from Microsoft's FY2025 Form 10-K segment note. It preserves direct source URLs and identifies
FY2023–FY2024 as recast comparative periods; segment revenue and COGS are checked against the
standardized consolidated statements.

The fixture exists so the complete research workflow can be tested offline and deterministically.
It is not a substitute for refreshing SEC filings before live research. Maintainers can regenerate
it with `python scripts/build_public_history_fixture.py TICKER` after creating the ignored local
file `config/model_config.yaml` with a valid SEC User-Agent.
