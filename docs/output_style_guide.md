# Output Style Guide

## Default palette

The project uses a blue-first visual system across Excel workbooks and static charts.

| Role | Color | Hex |
|---|---|---|
| Workbook title and major sections | Navy | `#17365D` |
| Table headers | Primary blue | `#1F4E78` |
| Secondary chart series | Medium blue | `#5B9BD5` |
| Accent chart series | Accent blue | `#2F75B5` |
| Forecast and calculated output background | Pale blue | `#EAF3F8` |
| Notes and secondary panels | Light blue | `#D9EAF7` |
| Editable assumption font | Excel input blue | `#0000FF` |

Blue is the dominant presentation color, but semantic exceptions remain intentional:

- formulas linking to another workbook sheet use green font under financial-model convention;
- failed checks and negative financial values may use red;
- warnings may use amber;
- normal calculations and labels remain black for readability.

## Workbook conventions

- Gridlines are hidden and section hierarchy is created with fills and restrained borders.
- Titles use navy bands; table headers use primary blue with white text.
- Editable assumptions use blue font and a light-blue background.
- Forecast values use pale-blue backgrounds without being misclassified as editable inputs.
- Amounts are displayed in USD millions except per-share data.
- Negative amounts use parentheses and red font through the number format.
- The Summary sheet contains key valuation metrics, model status, and a blue revenue/EBITDA chart.
- The Sensitivity sheet uses a blue sequential scale; darker blue represents higher implied value.
