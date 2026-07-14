# Data directories

Runtime SEC responses are stored under `data/cache/` and are ignored by Git. Only small,
auditable public or synthetic samples may be committed under `data/sample/`.

## Public sample data

`sample/wmt_fy2022_2026_history.json` is a versioned, standardized snapshot derived solely
from Walmart's public SEC Company Facts. It contains canonical values, filing lineage, and
quality metadata, but no SEC request headers, personal contact details, or cache metadata.

`sample/aapl_fy2021_2025_history.json` provides the same contract for Apple and is used to
verify that the canonical mapping and linked model are not retailer-specific.

The fixture exists so the complete research workflow can be tested offline and deterministically.
It is not a substitute for refreshing SEC filings before live research. Maintainers can regenerate
it with `python scripts/build_public_history_fixture.py WMT` after creating the ignored local
file `config/model_config.yaml` with a valid SEC User-Agent.
