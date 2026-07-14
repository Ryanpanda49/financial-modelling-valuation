import json
from pathlib import Path

from fmva.config.models import SecConfig
from fmva.sec.client import SecClient
from fmva.sec.company_registry import CompanyRegistry


def read(name: str) -> dict:
    return json.loads(Path("tests/fixtures", name).read_text())


def test_wmt_ticker_to_identity(tmp_path: Path) -> None:
    fixtures = {
        f"{SecClient.WWW_BASE}/files/company_tickers.json": read("company_tickers.json"),
        f"{SecClient.DATA_BASE}/submissions/CIK0000104169.json": read("wmt_submissions.json"),
    }

    def transport(url: str, headers: dict[str, str], timeout: float) -> dict:
        return fixtures[url]

    client = SecClient(
        SecConfig(
            user_agent="Researcher researcher@domain.test",
            cache_directory=tmp_path,
            requests_per_second=10,
        ),
        transport=transport,
        sleeper=lambda _: None,
    )
    company = CompanyRegistry(client).get_company("wmt")
    assert company.ticker == "WMT"
    assert company.cik == "0000104169"
    assert company.name == "Walmart Inc."
    assert company.fiscal_year_end == "0131"
    assert company.sic == "5331"
    assert company.entity_type == "operating"
    assert "CIK=0000104169" in company.filings_url
