"""Declarative XBRL-to-canonical account mapping."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from fmva.exceptions import ConfigurationError
from fmva.sec.company_facts import FactKind


@dataclass(frozen=True, slots=True)
class TagCandidate:
    """Accepted XBRL tag and deterministic fallback priority."""

    tag: str
    priority: int
    taxonomy: str = "us-gaap"


@dataclass(frozen=True, slots=True)
class AccountDefinition:
    """One canonical account definition."""

    name: str
    statements: tuple[str, ...]
    fact_kind: FactKind
    sign: str
    required: bool
    unit_type: str
    description: str
    accepted_tags: tuple[TagCandidate, ...]
    derivation: str | None = None
    zero_if_missing: tuple[str, ...] = ()

    @property
    def statement(self) -> str:
        """Return the primary statement for backwards-compatible callers."""

        return self.statements[0]


@dataclass(frozen=True, slots=True)
class AccountMap:
    """Versioned canonical account mapping."""

    version: int
    accounts: dict[str, AccountDefinition]

    @classmethod
    def from_yaml(cls, path: str | Path) -> AccountMap:
        """Load and validate a mapping YAML file."""

        mapping_path = Path(path)
        try:
            payload = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
            raw_accounts = payload["accounts"]
        except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
            raise ConfigurationError(f"Invalid account mapping file: {mapping_path}") from exc
        if not isinstance(raw_accounts, dict):
            raise ConfigurationError("account_mapping accounts must be a mapping.")
        accounts: dict[str, AccountDefinition] = {}
        for name, raw in raw_accounts.items():
            if not isinstance(raw, dict):
                raise ConfigurationError(f"Account definition must be a mapping: {name}")
            try:
                candidates = tuple(
                    sorted(
                        (
                            TagCandidate(
                                tag=str(item["tag"]),
                                priority=int(item["priority"]),
                                taxonomy=str(item.get("taxonomy", "us-gaap")),
                            )
                            for item in raw["accepted_tags"]
                        ),
                        key=lambda item: item.priority,
                    )
                )
                statement_value = raw.get("statements", raw.get("statement"))
                statements: tuple[str, ...]
                if isinstance(statement_value, str):
                    statements = (statement_value,)
                elif isinstance(statement_value, list) and statement_value:
                    statements = tuple(str(item) for item in statement_value)
                else:
                    raise ValueError("statement or statements is required")
                accounts[str(name)] = AccountDefinition(
                    name=str(raw.get("canonical_name", name)),
                    statements=statements,
                    fact_kind=FactKind(str(raw["fact_kind"])),
                    sign=str(raw["sign"]),
                    required=bool(raw["required"]),
                    unit_type=str(raw["unit_type"]),
                    description=str(raw["description"]),
                    accepted_tags=candidates,
                    derivation=str(raw["derivation"]) if raw.get("derivation") else None,
                    zero_if_missing=tuple(
                        str(value) for value in raw.get("zero_if_missing", [])
                    ),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ConfigurationError(f"Invalid account definition: {name}") from exc
        return cls(version=int(payload.get("version", 1)), accounts=accounts)


class AccountMapper:
    """Container for mapping definitions and normalization policies."""

    def __init__(self, account_map: AccountMap) -> None:
        self.account_map = account_map

    def definition(self, account: str) -> AccountDefinition:
        """Return one definition or a clear configuration error."""

        try:
            return self.account_map.accounts[account]
        except KeyError as exc:
            raise ConfigurationError(f"Unknown canonical account: {account}") from exc


def normalized_scale(unit_type: str, unit: str) -> Decimal:
    """Return divisor that normalizes currency and shares to millions."""

    if unit_type == "currency" and unit == "USD":
        return Decimal("1000000")
    if unit_type == "shares" and unit == "shares":
        return Decimal("1000000")
    if unit_type == "per_share" and unit in {"USD/shares", "USD / shares"}:
        return Decimal("1")
    if unit_type == "ratio" and unit in {"pure", "percent"}:
        return Decimal("1")
    raise ConfigurationError(f"Unsupported source unit '{unit}' for unit type '{unit_type}'.")


def normalize_sign(value: Decimal, sign: str) -> Decimal:
    """Apply the documented canonical sign convention."""

    if sign == "positive":
        return abs(value)
    if sign == "source":
        return value
    raise ConfigurationError(f"Unsupported sign convention: {sign}")
