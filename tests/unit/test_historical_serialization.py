import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from fmva.data.models import (
    CanonicalObservation,
    Confidence,
    FieldProvenance,
    QualityIssue,
    SelectionMethod,
)
from fmva.data.statement_builder import HistoricalStatements
from fmva.exceptions import HistoricalDataError


def _history() -> HistoricalStatements:
    frame = pd.DataFrame(
        {2024: {"revenue": 100.0, "net_income": float("nan")}}
    )
    frame.index.name = "account"
    frame.columns.name = "fiscal_year"
    return HistoricalStatements(
        statements={"income_statement": frame},
        observations=(
            CanonicalObservation(
                account="revenue",
                statement="income_statement",
                fiscal_year=2024,
                value=Decimal("100.125"),
                provenance=FieldProvenance(
                    source_tag="Revenue",
                    source_filing="0000000000-24-000001",
                    filing_date="2024-03-01",
                    fiscal_period="FY",
                    unit="USD millions",
                    confidence=Confidence.HIGH,
                    selection_method=SelectionMethod.DIRECT,
                    fallback_rank=1,
                    is_restated=True,
                    warnings=("Comparative value selected.",),
                ),
            ),
        ),
        quality_issues=(
            QualityIssue(
                account="net_income",
                fiscal_year=2024,
                severity="WARNING",
                code="OPTIONAL_ACCOUNT_MISSING",
                message="No direct value.",
            ),
        ),
    )


def test_historical_statements_json_round_trip(tmp_path: Path) -> None:
    source = _history()
    path = source.write_json(
        tmp_path / "history.json",
        metadata={"ticker": "TEST", "source": "public filing"},
    )
    restored = HistoricalStatements.read_json(path)

    pd.testing.assert_frame_equal(
        restored.statements["income_statement"],
        source.statements["income_statement"],
    )
    assert restored.observations == source.observations
    assert restored.quality_issues == source.quality_issues
    content = path.read_text(encoding="utf-8")
    payload = json.loads(content)
    serialized = payload["statements"]["income_statement"]
    missing_row = serialized["index"].index("net_income")
    assert '"schema_version": 1' in content
    assert serialized["data"][missing_row][0] is None
    assert "NaN" not in content


def test_historical_statements_rejects_unknown_schema() -> None:
    with pytest.raises(HistoricalDataError, match="schema_version"):
        HistoricalStatements.from_dict(
            {
                "schema_version": 99,
                "statements": {},
                "observations": [],
                "quality_issues": [],
            }
        )


def test_historical_statements_wraps_malformed_payload() -> None:
    with pytest.raises(HistoricalDataError, match="Malformed"):
        HistoricalStatements.from_dict(
            {
                "schema_version": 1,
                "statements": [],
                "observations": [],
                "quality_issues": [],
            }
        )
