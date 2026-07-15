"""Source-aware historical business KPI import for analyst operating models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from fmva.exceptions import HistoricalDataError

REQUIRED_COLUMNS = (
    "metric",
    "dimension",
    "fiscal_year",
    "value",
    "unit",
    "source_name",
    "source_url",
    "source_document",
    "filing_date",
    "confidence",
    "is_direct",
    "is_restated",
    "notes",
)


@dataclass(frozen=True, slots=True)
class BusinessKpiRecord:
    """One historical operating KPI with sufficient evidence for review."""

    metric: str
    dimension: str
    fiscal_year: int
    value: float
    unit: str
    source_name: str
    source_url: str
    source_document: str
    filing_date: date
    confidence: str
    is_direct: bool
    is_restated: bool
    notes: str


@dataclass(frozen=True, slots=True)
class BusinessKpiHistory:
    """Validated immutable historical KPI collection."""

    records: tuple[BusinessKpiRecord, ...]

    @classmethod
    def from_tabular(cls, path: str | Path) -> BusinessKpiHistory:
        """Load canonical CSV/XLSX input and reject silent ambiguity."""

        source = Path(path)
        try:
            if source.suffix.lower() == ".csv":
                frame = pd.read_csv(source, keep_default_na=False)
            elif source.suffix.lower() in {".xlsx", ".xlsm"}:
                frame = pd.read_excel(source, sheet_name="Business KPIs", keep_default_na=False)
            else:
                raise HistoricalDataError("Business KPI input must be CSV, XLSX, or XLSM.")
        except HistoricalDataError:
            raise
        except (OSError, ValueError) as exc:
            raise HistoricalDataError(f"Unable to read business KPI input: {source}") from exc
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise HistoricalDataError(f"Business KPI input is missing columns: {missing}")
        records: list[BusinessKpiRecord] = []
        seen: set[tuple[str, str, int]] = set()
        for row_number, row in frame.iterrows():
            try:
                fiscal_year = int(row["fiscal_year"])
                key = (str(row["metric"]).strip(), str(row["dimension"]).strip(), fiscal_year)
                if not key[0] or not key[1]:
                    raise ValueError("metric and dimension are required")
                if key in seen:
                    raise HistoricalDataError(f"Duplicate business KPI key {key}.")
                seen.add(key)
                confidence = str(row["confidence"]).strip().upper()
                if confidence not in {"HIGH", "MEDIUM", "LOW"}:
                    raise ValueError("confidence must be HIGH, MEDIUM, or LOW")
                source_url = str(row["source_url"]).strip()
                if not source_url.startswith("https://"):
                    raise ValueError("source_url must be an HTTPS URL")
                records.append(
                    BusinessKpiRecord(
                        metric=key[0],
                        dimension=key[1],
                        fiscal_year=fiscal_year,
                        value=float(row["value"]),
                        unit=str(row["unit"]).strip(),
                        source_name=str(row["source_name"]).strip(),
                        source_url=source_url,
                        source_document=str(row["source_document"]).strip(),
                        filing_date=pd.to_datetime(row["filing_date"]).date(),
                        confidence=confidence,
                        is_direct=_parse_bool(row["is_direct"]),
                        is_restated=_parse_bool(row["is_restated"]),
                        notes=str(row["notes"]).strip(),
                    )
                )
            except HistoricalDataError:
                raise
            except (TypeError, ValueError) as exc:
                raise HistoricalDataError(
                    f"Invalid business KPI row {row_number!s}: {exc}"
                ) from exc
        if not records:
            raise HistoricalDataError("Business KPI input contains no records.")
        return cls(tuple(records))

    def to_frame(self) -> pd.DataFrame:
        """Return the public long-form audit table in stable column order."""

        frame: pd.DataFrame = pd.DataFrame([asdict(record) for record in self.records])
        ordered: pd.DataFrame = frame.reindex(columns=list(REQUIRED_COLUMNS))
        return ordered.sort_values(
            ["metric", "dimension", "fiscal_year"]
        ).reset_index(drop=True)

    def metric_frame(self, metric: str) -> pd.DataFrame:
        """Pivot one metric into dimensions by fiscal year for modelling or review."""

        frame = self.to_frame()
        selected = frame.loc[frame["metric"] == metric]
        if selected.empty:
            raise HistoricalDataError(f"Business KPI metric not found: {metric}")
        return selected.pivot(index="dimension", columns="fiscal_year", values="value")


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")
