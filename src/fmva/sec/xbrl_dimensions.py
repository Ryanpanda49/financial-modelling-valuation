"""Parse filing-level XBRL facts while retaining segment and product dimensions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml

from fmva.data.business_kpis import BusinessKpiHistory, BusinessKpiRecord
from fmva.exceptions import ConfigurationError, SecDataError

XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
_LINKBASE_SUFFIXES = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")


@dataclass(frozen=True, slots=True)
class XbrlContext:
    """One XBRL context with its period and explicit or typed dimensions."""

    context_id: str
    start_date: date | None
    end_date: date | None
    instant: date | None
    dimensions: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class DimensionalFact:
    """One numeric filing fact with context, units, and dimensional metadata."""

    concept: str
    value: float
    context_id: str
    unit: str | None
    decimals: str | None
    context: XbrlContext


@dataclass(frozen=True, slots=True)
class BusinessKpiRule:
    """Declarative mapping from an XBRL concept/member pair to a canonical KPI."""

    metric: str
    concept: str
    axis: str
    members: Mapping[str, str]
    unit: str
    scale: float


@dataclass(frozen=True, slots=True)
class BusinessKpiMapping:
    """Source metadata and rules for converting filing facts into KPI history."""

    source_name: str
    source_url: str
    source_document: str
    filing_date: date
    confidence: str
    restated_years: tuple[int, ...]
    rules: tuple[BusinessKpiRule, ...]

    @classmethod
    def from_yaml(cls, path: str | Path) -> BusinessKpiMapping:
        source = Path(path)
        try:
            payload: Any = yaml.safe_load(source.read_text(encoding="utf-8"))
            metadata = payload["source"]
            rules = tuple(
                BusinessKpiRule(
                    metric=str(rule["metric"]),
                    concept=str(rule["concept"]),
                    axis=str(rule["axis"]),
                    members={str(key): str(value) for key, value in rule["members"].items()},
                    unit=str(rule["unit"]),
                    scale=float(rule.get("scale", 1.0)),
                )
                for rule in payload["rules"]
            )
            result = cls(
                source_name=str(metadata["name"]),
                source_url=str(metadata["url"]),
                source_document=str(metadata["document"]),
                filing_date=date.fromisoformat(str(metadata["filing_date"])),
                confidence=str(metadata.get("confidence", "HIGH")).upper(),
                restated_years=tuple(int(year) for year in metadata.get("restated_years", [])),
                rules=rules,
            )
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid dimensional KPI mapping: {source}") from exc
        if not result.source_url.startswith("https://"):
            raise ConfigurationError("Dimensional KPI source URL must use HTTPS.")
        if result.confidence not in {"HIGH", "MEDIUM", "LOW"} or not result.rules:
            raise ConfigurationError("Dimensional KPI mapping requires rules and valid confidence.")
        return result


def filing_directory_url(cik: str | int, accession_number: str) -> str:
    """Build the SEC Archives directory-index URL for one accession."""

    accession = accession_number.replace("-", "").strip()
    if not accession.isdigit():
        raise ValueError("Accession number must contain only digits and hyphens.")
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession}/index.json"
    )


def select_instance_document(index_payload: Mapping[str, Any], primary_document: str | None = None) -> str:
    """Select the likely XBRL instance document from an SEC filing directory."""

    try:
        items = index_payload["directory"]["item"]
        names = [str(item["name"]) for item in items]
    except (KeyError, TypeError) as exc:
        raise SecDataError("SEC filing directory payload is missing directory items.") from exc
    xml_names = [
        name
        for name in names
        if name.lower().endswith(".xml")
        and not name.lower().endswith(_LINKBASE_SUFFIXES)
        and name.lower() not in {"filingsummary.xml", "metalinks.json"}
        and not name.lower().startswith("report")
    ]
    if primary_document:
        stem = Path(primary_document).stem.lower()
        stem_matches = [name for name in xml_names if Path(name).stem.lower() == stem]
        if stem_matches:
            return stem_matches[0]
    candidates = [name for name in xml_names if not name.lower().startswith(("r", "f"))]
    selected = candidates or xml_names
    if len(selected) != 1:
        raise SecDataError(
            "Unable to identify a unique XBRL instance document; "
            f"candidates={selected}."
        )
    return selected[0]


def parse_dimensional_facts(xml_source: str | bytes | Path) -> tuple[DimensionalFact, ...]:
    """Parse numeric facts from an XBRL instance without resolving taxonomy files."""

    try:
        if isinstance(xml_source, Path):
            root = ET.parse(xml_source).getroot()
        else:
            root = ET.fromstring(xml_source)
    except (OSError, ET.ParseError) as exc:
        raise SecDataError("Unable to parse the XBRL instance document.") from exc
    contexts = _parse_contexts(root)
    units = _parse_units(root)
    facts: list[DimensionalFact] = []
    for element in root.iter():
        context_id = element.attrib.get("contextRef")
        if not context_id or context_id not in contexts or element.text is None:
            continue
        try:
            value = float(element.text.strip())
        except ValueError:
            continue
        facts.append(
            DimensionalFact(
                concept=_local_name(element.tag),
                value=value,
                context_id=context_id,
                unit=units.get(element.attrib.get("unitRef", "")),
                decimals=element.attrib.get("decimals"),
                context=contexts[context_id],
            )
        )
    return tuple(facts)


def dimensional_facts_to_business_kpis(
    facts: tuple[DimensionalFact, ...],
    mapping: BusinessKpiMapping,
) -> BusinessKpiHistory:
    """Convert mapped annual duration facts into source-aware business KPI records."""

    records: list[BusinessKpiRecord] = []
    seen: set[tuple[str, str, int]] = set()
    for rule in mapping.rules:
        for fact in facts:
            member = fact.context.dimensions.get(rule.axis)
            if fact.concept != rule.concept or member is None or member not in rule.members:
                continue
            if fact.context.end_date is None or fact.context.start_date is None:
                continue
            duration = (fact.context.end_date - fact.context.start_date).days
            if not 330 <= duration <= 380:
                continue
            fiscal_year = fact.context.end_date.year
            dimension = rule.members[member]
            key = (rule.metric, dimension, fiscal_year)
            if key in seen:
                raise SecDataError(f"Duplicate mapped dimensional fact: {key}.")
            seen.add(key)
            records.append(
                BusinessKpiRecord(
                    metric=rule.metric,
                    dimension=dimension,
                    fiscal_year=fiscal_year,
                    value=fact.value * rule.scale,
                    unit=rule.unit,
                    source_name=mapping.source_name,
                    source_url=mapping.source_url,
                    source_document=mapping.source_document,
                    filing_date=mapping.filing_date,
                    confidence=mapping.confidence,
                    is_direct=True,
                    is_restated=fiscal_year in mapping.restated_years,
                    notes=(
                        f"Direct XBRL fact {rule.concept}; axis {rule.axis}; "
                        f"member {member}; context {fact.context_id}."
                    ),
                )
            )
    if not records:
        raise SecDataError("No dimensional facts matched the business KPI mapping.")
    return BusinessKpiHistory(tuple(records))


def _parse_contexts(root: ET.Element) -> dict[str, XbrlContext]:
    contexts: dict[str, XbrlContext] = {}
    for element in root.findall(f"{{{XBRLI}}}context"):
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        period = element.find(f"{{{XBRLI}}}period")
        start = _child_date(period, "startDate")
        end = _child_date(period, "endDate")
        instant = _child_date(period, "instant")
        dimensions: dict[str, str] = {}
        for member in element.findall(f".//{{{XBRLDI}}}explicitMember"):
            if member.text and member.attrib.get("dimension"):
                dimensions[_qname_local(member.attrib["dimension"])] = _qname_local(member.text)
        for member in element.findall(f".//{{{XBRLDI}}}typedMember"):
            axis = member.attrib.get("dimension")
            child = next(iter(member), None)
            if axis and child is not None and child.text:
                dimensions[_qname_local(axis)] = child.text.strip()
        contexts[context_id] = XbrlContext(context_id, start, end, instant, dimensions)
    return contexts


def _parse_units(root: ET.Element) -> dict[str, str]:
    units: dict[str, str] = {}
    for element in root.findall(f"{{{XBRLI}}}unit"):
        unit_id = element.attrib.get("id")
        measure = element.find(f"{{{XBRLI}}}measure")
        if unit_id and measure is not None and measure.text:
            units[unit_id] = _qname_local(measure.text)
    return units


def _child_date(period: ET.Element | None, name: str) -> date | None:
    if period is None:
        return None
    element = period.find(f"{{{XBRLI}}}{name}")
    return date.fromisoformat(element.text.strip()) if element is not None and element.text else None


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def _qname_local(value: str) -> str:
    return value.split(":", 1)[-1].strip()
