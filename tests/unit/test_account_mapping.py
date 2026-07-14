from decimal import Decimal

from fmva.data.account_mapping import AccountMap, normalize_sign

EXPECTED_ACCOUNTS = {
    "revenue", "cogs", "gross_profit", "selling_general_admin", "research_and_development",
    "depreciation_and_amortization", "operating_income", "interest_expense", "interest_income",
    "income_before_tax", "income_tax", "net_income", "minority_interest",
    "net_income_attributable_to_parent", "diluted_eps", "diluted_shares",
    "cash_and_equivalents", "short_term_investments", "accounts_receivable", "inventory",
    "other_current_assets", "total_current_assets", "property_plant_equipment", "goodwill",
    "intangible_assets", "other_noncurrent_assets", "total_assets", "accounts_payable",
    "accrued_liabilities", "short_term_debt", "current_lease_liabilities",
    "other_current_liabilities", "total_current_liabilities", "long_term_debt",
    "noncurrent_lease_liabilities", "deferred_tax_liabilities", "other_noncurrent_liabilities",
    "total_liabilities", "common_stock", "additional_paid_in_capital", "retained_earnings",
    "accumulated_other_comprehensive_income", "treasury_stock", "total_equity",
    "stock_based_compensation", "deferred_taxes", "change_in_accounts_receivable",
    "change_in_inventory", "change_in_accounts_payable", "change_in_other_working_capital",
    "cash_from_operations", "capital_expenditures", "acquisitions", "asset_disposals",
    "cash_from_investing", "debt_issuance", "debt_repayment", "share_issuance",
    "share_repurchases", "dividends_paid", "cash_from_financing", "fx_effect",
    "net_change_in_cash",
}


def test_mapping_covers_required_canonical_dictionary() -> None:
    mapping = AccountMap.from_yaml("config/account_mapping.yaml")
    canonical_names = {definition.name for definition in mapping.accounts.values()}
    assert EXPECTED_ACCOUNTS <= canonical_names
    assert mapping.version == 2
    assert mapping.accounts["net_income"].statements == (
        "income_statement",
        "cash_flow_statement",
    )
    assert mapping.accounts["minority_interest_balance"].name == "minority_interest"


def test_positive_sign_convention_normalizes_source_negative() -> None:
    assert normalize_sign(Decimal("-15"), "positive") == Decimal("15")
    assert normalize_sign(Decimal("-15"), "source") == Decimal("-15")
