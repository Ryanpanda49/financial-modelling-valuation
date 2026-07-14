"""Import researcher-supplied canonical history from CSV or Excel."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from fmva.data.account_mapping import AccountMap
from fmva.data.models import (
    CanonicalObservation,
    Confidence,
    FieldProvenance,
    QualityIssue,
    SelectionMethod,
)
from fmva.data.statement_builder import HistoricalStatements
from fmva.exceptions import HistoricalDataError
from fmva.sec.company_registry import CompanyIdentity

HISTORY_SHEET = "Historical Financials"
COMPANY_SHEET = "Company"
REQUIRED_HISTORY_COLUMNS = {"statement", "account", "fiscal_year", "value"}
REQUIRED_COMPANY_FIELDS = {"ticker", "cik", "company_name", "filings_url"}
COMPANY_FIELDS = REQUIRED_COMPANY_FIELDS | {
    "fiscal_year_end",
    "sic",
    "sic_description",
    "entity_type",
}


@dataclass(frozen=True, slots=True)
class ImportedHistory:
    """Company identity and standardized statements loaded from a manual source."""

    company: CompanyIdentity
    history: HistoricalStatements


def import_canonical_history(
    path: str | Path,
    *,
    account_mapping_path: str | Path = "config/account_mapping.yaml",
) -> ImportedHistory:
    """Load a canonical long-form CSV or Excel workbook into the history contract."""

    input_path = Path(path)
    if input_path.suffix.lower() == ".csv":
        try:
            history_frame = pd.read_csv(input_path)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise HistoricalDataError(f"Unable to read manual history CSV: {input_path}") from exc
        metadata = _metadata_from_repeated_columns(history_frame)
    elif input_path.suffix.lower() in {".xlsx", ".xlsm"}:
        try:
            sheets = pd.read_excel(input_path, sheet_name=None)
        except (OSError, ValueError, ImportError) as exc:
            raise HistoricalDataError(f"Unable to read manual history workbook: {input_path}") from exc
        if HISTORY_SHEET not in sheets or COMPANY_SHEET not in sheets:
            raise HistoricalDataError(
                f"Workbook must contain '{COMPANY_SHEET}' and '{HISTORY_SHEET}' sheets."
            )
        history_frame = sheets[HISTORY_SHEET]
        metadata = _metadata_from_company_sheet(sheets[COMPANY_SHEET])
    else:
        raise HistoricalDataError("Manual history input must be .csv, .xlsx, or .xlsm.")

    history_frame = _normalized_columns(history_frame)
    missing_columns = sorted(REQUIRED_HISTORY_COLUMNS - set(history_frame.columns))
    if missing_columns:
        raise HistoricalDataError(
            "Manual history table is missing columns: " + ", ".join(missing_columns)
        )
    account_map = AccountMap.from_yaml(account_mapping_path)
    history = _build_history(history_frame, account_map, input_path.name)
    return ImportedHistory(company=_company_identity(metadata), history=history)


def _build_history(
    frame: pd.DataFrame,
    account_map: AccountMap,
    source_file: str,
) -> HistoricalStatements:
    frame = frame.dropna(how="all").copy()
    try:
        frame["statement"] = frame["statement"].astype(str).str.strip()
        frame["account"] = frame["account"].astype(str).str.strip()
        frame["fiscal_year"] = pd.to_numeric(frame["fiscal_year"], errors="raise").astype(int)
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    except (TypeError, ValueError) as exc:
        raise HistoricalDataError("Manual history contains an invalid fiscal_year or value.") from exc
    if frame.empty:
        raise HistoricalDataError("Manual history table contains no data rows.")
    years = sorted(int(value) for value in frame["fiscal_year"].unique())
    if any(year < 1900 or year > 2200 for year in years):
        raise HistoricalDataError("Manual fiscal years must be between 1900 and 2200.")

    definitions = {
        (statement, definition.name): definition
        for definition in account_map.accounts.values()
        for statement in definition.statements
    }
    supplied: dict[tuple[str, str, int], pd.Series] = {}
    for _, row in frame.iterrows():
        key = (str(row["statement"]), str(row["account"]), int(row["fiscal_year"]))
        if key[:2] not in definitions:
            raise HistoricalDataError(
                f"Unknown canonical statement/account combination: {key[0]}/{key[1]}."
            )
        if key in supplied:
            raise HistoricalDataError(
                f"Duplicate manual history row: {key[0]}/{key[1]}/FY{key[2]}."
            )
        supplied[key] = row

    observations: list[CanonicalObservation] = []
    issues: list[QualityIssue] = []
    for (statement, account), definition in definitions.items():
        expected_unit = _expected_unit(definition.unit_type)
        for year in years:
            current = supplied.get((statement, account, year))
            if current is None or pd.isna(current["value"]):
                observations.append(_missing(account, statement, year, source_file))
                if definition.required:
                    issues.append(
                        QualityIssue(
                            account=account,
                            fiscal_year=year,
                            severity="ERROR",
                            code="REQUIRED_ACCOUNT_MISSING",
                            message=(
                                f"Manual input is missing required account '{account}' "
                                f"on {statement}."
                            ),
                        )
                    )
                continue
            unit = _optional_text(current, "unit") or expected_unit
            if unit != expected_unit:
                raise HistoricalDataError(
                    f"Invalid unit for {statement}/{account}/FY{year}: "
                    f"expected '{expected_unit}', received '{unit}'."
                )
            confidence = _confidence(current)
            notes = _optional_text(current, "notes")
            source_name = _optional_text(current, "source_name") or "Manual upload"
            source_reference = _optional_text(current, "source_reference") or source_file
            observations.append(
                CanonicalObservation(
                    account=account,
                    statement=statement,
                    fiscal_year=year,
                    value=Decimal(str(float(current["value"]))),
                    provenance=FieldProvenance(
                        source_tag=source_name,
                        source_filing=source_reference,
                        filing_date=_optional_text(current, "filing_date"),
                        fiscal_period="FY",
                        unit=unit,
                        confidence=confidence,
                        selection_method=SelectionMethod.MANUAL,
                        fallback_rank=None,
                        is_restated=False,
                        warnings=((notes,) if notes else ()),
                    ),
                )
            )

    frames: dict[str, pd.DataFrame] = {}
    for statement in sorted({item.statement for item in observations}):
        rows = [item for item in observations if item.statement == statement]
        data = {
            year: {
                item.account: float(item.value) if item.value is not None else math.nan
                for item in rows
                if item.fiscal_year == year
            }
            for year in years
        }
        result = pd.DataFrame(data).sort_index()
        result.index.name = "account"
        result.columns.name = "fiscal_year"
        frames[statement] = result
    return HistoricalStatements(
        statements=frames,
        observations=tuple(observations),
        quality_issues=tuple(issues),
    )


def _missing(
    account: str,
    statement: str,
    year: int,
    source_file: str,
) -> CanonicalObservation:
    return CanonicalObservation(
        account=account,
        statement=statement,
        fiscal_year=year,
        value=None,
        provenance=FieldProvenance(
            source_tag="Manual upload",
            source_filing=source_file,
            filing_date=None,
            fiscal_period="FY",
            unit="unknown",
            confidence=Confidence.MISSING,
            selection_method=SelectionMethod.MISSING,
            fallback_rank=None,
            is_restated=False,
            warnings=("No value supplied in manual history input.",),
        ),
    )


def _metadata_from_repeated_columns(frame: pd.DataFrame) -> dict[str, str]:
    normalized = _normalized_columns(frame)
    missing = sorted(REQUIRED_COMPANY_FIELDS - set(normalized.columns))
    if missing:
        raise HistoricalDataError(
            "Manual CSV must repeat company metadata columns: " + ", ".join(missing)
        )
    metadata: dict[str, str] = {}
    for field in COMPANY_FIELDS & set(normalized.columns):
        values = {
            str(value).strip()
            for value in normalized[field].dropna().tolist()
            if str(value).strip()
        }
        if len(values) > 1:
            raise HistoricalDataError(f"Manual CSV contains conflicting '{field}' values.")
        if values:
            metadata[field] = next(iter(values))
    return metadata


def _metadata_from_company_sheet(frame: pd.DataFrame) -> dict[str, str]:
    normalized = _normalized_columns(frame).dropna(how="all")
    if not {"field", "value"}.issubset(normalized.columns):
        raise HistoricalDataError("Company sheet must contain 'field' and 'value' columns.")
    metadata = {
        str(row["field"]).strip(): str(row["value"]).strip()
        for _, row in normalized.iterrows()
        if not pd.isna(row["field"]) and not pd.isna(row["value"])
    }
    missing = sorted(REQUIRED_COMPANY_FIELDS - set(metadata))
    if missing:
        raise HistoricalDataError("Company sheet is missing fields: " + ", ".join(missing))
    return metadata


def _company_identity(metadata: dict[str, str]) -> CompanyIdentity:
    try:
        return CompanyIdentity(
            ticker=metadata["ticker"].upper(),
            cik=f"{int(float(metadata['cik'])):010d}",
            name=metadata["company_name"],
            fiscal_year_end=metadata.get("fiscal_year_end"),
            sic=metadata.get("sic"),
            sic_description=metadata.get("sic_description"),
            entity_type=metadata.get("entity_type"),
            filings_url=metadata["filings_url"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HistoricalDataError("Manual company metadata is invalid.") from exc


def _normalized_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(value).strip().lower().replace(" ", "_") for value in result.columns]
    return result


def _optional_text(row: pd.Series, name: str) -> str | None:
    if name not in row.index or pd.isna(row[name]):
        return None
    value = str(row[name]).strip()
    return value or None


def _confidence(row: pd.Series) -> Confidence:
    raw = (_optional_text(row, "confidence") or "MEDIUM").upper()
    try:
        return Confidence(raw)
    except ValueError as exc:
        raise HistoricalDataError(f"Unknown manual confidence value: {raw}.") from exc


def _expected_unit(unit_type: str) -> str:
    units = {
        "currency": "USD millions",
        "shares": "shares millions",
        "per_share": "USD per share",
        "ratio": "ratio",
    }
    try:
        return units[unit_type]
    except KeyError as exc:
        raise HistoricalDataError(f"Unsupported canonical unit type: {unit_type}.") from exc
