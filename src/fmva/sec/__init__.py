"""SEC data access and parsing."""

from fmva.sec.client import SecClient
from fmva.sec.company_facts import CompanyFacts, FactObservation
from fmva.sec.company_registry import CompanyIdentity, CompanyRegistry
from fmva.sec.filing_instance import (
    FilingInstance,
    FilingInstanceService,
    FilingMetadata,
    filing_document_url,
    select_annual_filing,
)
from fmva.sec.xbrl_dimensions import (
    BusinessKpiMapping,
    DimensionalFact,
    XbrlContext,
    dimensional_facts_to_business_kpis,
    filing_directory_url,
    parse_dimensional_facts,
    select_instance_document,
)

__all__ = [
    "BusinessKpiMapping",
    "CompanyFacts",
    "CompanyIdentity",
    "CompanyRegistry",
    "DimensionalFact",
    "FactObservation",
    "FilingInstance",
    "FilingInstanceService",
    "FilingMetadata",
    "SecClient",
    "XbrlContext",
    "dimensional_facts_to_business_kpis",
    "filing_document_url",
    "filing_directory_url",
    "parse_dimensional_facts",
    "select_annual_filing",
    "select_instance_document",
]
