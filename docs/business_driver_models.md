# Business driver models

The framework supports two operating-model layers without changing the linked statement engine:

1. `TopDownOperatingModel` is the default. Revenue growth and operating cost ratios come from
   the centralized forecast assumptions YAML.
2. A company-specific `OperatingModel` may replace revenue and selected operating drivers while
   continuing to feed the same working-capital, fixed-asset, debt, tax, cash, balance-sheet, DCF,
   sensitivity, and check modules.

## COST warehouse and membership model

`CostMembershipRetailModel` is the first bottom-up implementation. It calculates merchandise
revenue from beginning warehouses, comparable-sales growth, half-year contribution from new
warehouses, and new-warehouse productivity. Membership-fee revenue is calculated from paid-member
equivalents and an effective recognized fee. Merchandise COGS is driven against merchandise sales,
so membership fees are not incorrectly assigned merchandise cost.

The resulting revenue bridge is:

```text
Merchandise revenue
= Beginning warehouses × mature sales per warehouse
 + New warehouses × 0.5 × mature sales per warehouse × new-store productivity

Membership fee revenue
= Paid members (millions) × effective recognized fee (USD)

Total revenue = Merchandise revenue + Membership fee revenue
```

The `0.5` convention represents an average mid-year opening and is an explicit MVP simplification.
It can later be replaced by monthly cohort timing. The model also discloses executive-member mix
and renewal rate as KPIs, but does not use them as hidden formula multipliers; this avoids double
counting because their economic effects are reflected in member growth and effective fee inputs.

## Controls and limitations

- Opening merchandise and membership revenue must reconcile to the latest standardized historical
  revenue within 0.1% or USD 1 million, whichever is larger.
- Every business-driver year must match the forecast horizon.
- `business_driver_revenue_tie` proves that bottom-up total revenue equals forecast revenue.
- All business-driver inputs are researcher judgments, not SEC Company Facts and not company
  guidance. The sample is deliberately labelled illustrative.
- The interface is extensible to product, geography, subscriber, seat, capacity, or price-volume
  models. Financial institutions remain outside the MVP.
