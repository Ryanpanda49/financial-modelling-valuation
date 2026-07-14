# Excel Export Design and Public-Dependency Boundary

## Decision

The Python calculation engine is the single source of truth. An Excel workbook is a
presentation and audit artifact, not a second independently calculated model. The public
repository must use a documented, open-source, installable workbook engine and must not
depend on internal tooling, desktop Excel automation, paid add-ins, or proprietary plugins.

The public exporter uses `openpyxl`, selected after explicit project approval. Markdown, CSV,
PNG, and Excel exporters consume the same `ModelResult` contract, so workbook presentation
does not alter valuation logic.

## Proposed workbook contract

| Sheet | Purpose | Primary source |
|---|---|---|
| Summary | Company, valuation summary, key KPIs, warnings | `ModelResult` |
| Sources_Audit | Filing/tag/unit/period/provenance records | Historical metadata |
| Historical | Standardized historical statements | Historical result |
| Assumptions | Central editable operating and valuation inputs | Typed assumptions |
| Income_Statement | Historical and forecast income statement | Forecast result |
| Balance_Sheet | Historical and forecast balance sheet | Forecast result |
| Cash_Flow | Historical and forecast cash flow | Forecast result |
| Working_Capital | Days, balances, NWC, and change in NWC | Working-capital schedule |
| CapEx_Dep | PP&E roll-forward, CapEx, depreciation, disposals | Fixed-assets schedule |
| Debt_Schedule | Debt roll-forward and interest calculation | Debt schedule |
| Ratios | Formula definitions, values, units, warnings | Ratio result |
| DCF | UFCF, discounting, terminal value, and equity bridge | DCF result |
| Sensitivity | WACC versus terminal growth implied price | Sensitivity table |
| Checks | Difference, tolerance, status, and message | Structured checks |

## Presentation conventions

- Company/model title at the top of each sheet; units and as-of date are always visible.
- Historical and forecast columns are visually distinct without copying the reference
  workbook's branding or layout.
- Researcher-editable inputs use one consistent input style; calculated cells use a
  separate style; warnings and failed checks use explicit status colors and text.
- Units are USD millions except per-share data. Percentages, multiples, dates, and currency
  use native number formats rather than preformatted strings.
- Freeze panes, filters where useful, restrained column widths, and print-friendly sections.
- Sources and limitations are written into the workbook; no hidden external links or named
  ranges that depend on private add-ins are permitted.

## Formula policy

Core numbers are exported as Python-calculated values with reconciliation checks. Selected
transparent subtotal or identity formulas may be written for auditability, provided their
cached values are verified and they do not create a parallel source of truth. Circular
references, volatile formulas, macros, external workbook links, and opaque cash plugs are
not allowed.

## Verification gate

The exporter will be accepted only when tests confirm:

1. all required sheets exist in the intended order;
2. key DCF and three-statement values equal `ModelResult` values;
3. checks and limitations are visible;
4. formulas contain no Excel errors or external links;
5. the workbook can be opened by common spreadsheet applications;
6. rendered sheets are visually inspected for clipping, unreadable widths, and broken charts.

## Known limitations

`openpyxl` writes formulas but does not calculate them. The workbook requests automatic full
calculation when opened in a compatible spreadsheet application. Python-calculated values
remain the model source of truth, and automated tests validate sheet structure, references,
formula presence, theme conventions, charts, and absence of external links.
