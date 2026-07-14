# KO and MSFT Compatibility Validation

## Scope

KO and MSFT extend the public regression matrix from three to five SEC registrants. KO tests a
brand-led consumer company with meaningful debt and a high dividend payout. MSFT tests a
technology company with R&D, large short-term investments, intangible assets, and elevated data-
center capital expenditure. These are framework tests, not investment research.

## Fiscal-year selection correction

The initial KO audit exposed a false FY2026 panel. A filing-date instant fact in KO's FY2025 10-K
ended in calendar 2026 and was incorrectly allowed to establish a new fiscal year even though no
FY2026 annual statements existed. Statement coverage is now anchored to mapped annual revenue
facts. A dedicated unit test prevents unrelated 10-K instant facts from creating a future year.

After correction, both fixtures cover FY2021–FY2025 with 330 canonical observations, zero required-
account quality issues, five passing balance-sheet checks, and four passing cash roll-forwards.

## KO mapping review

KO reports trade payables separately from a combined payables-and-accruals total. The canonical
mapping now prefers `AccountsPayableTradeCurrent`, preventing accrued liabilities from distorting
DPO. KO debt uses explicit lower-priority fallbacks for notes and loans payable and long-term debt
including current maturities. Provenance identifies each fallback and the long-term debt description
discloses that the fallback may include current maturities.

## Forecast and valuation regression

Both illustrative FY2026–FY2030 cases pass all historical, forecast, debt/interest solver, and DCF
checks. Each exports the fourteen-sheet blue workbook, Markdown report, fifteen CSV tables, and six
static blue charts. Mechanical regression values are retained in tests solely to detect unintended
calculation changes.

## Limitations

- KO does not yet have separate concentrate, price/mix, unit-case volume, geography, bottling, or
  brand-acquisition drivers.
- MSFT does not yet separate Azure consumption, Microsoft 365 seats/ARPU, gaming, search, or AI
  infrastructure cohorts.
- KO debt classification uses disclosed fallback tags; current maturities are included in the
  long-term fallback and must be reviewed before a live maturity schedule is prepared.
- Market and operating assumptions are illustrative and require dated source support for research.
