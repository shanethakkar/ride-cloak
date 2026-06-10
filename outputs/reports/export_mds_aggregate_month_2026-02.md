# RideCloak methodology report — mds_aggregate v1

- Source: `month:2026-02`
- Generated: 2026-06-10T00:56:18.521059+00:00
- Output kind: aggregate
- Policy hash: `6844317ab135b45f...`
- Health score: None (gate passed)
- Salt fingerprint: `n/a`
- Output: `outputs\exports\mds_aggregate_month_2026-02.csv`
- Output SHA-256: `a55c0139eeab7804...`

## Volume

- Rows in: 14,166,961
- Rows out: 14,159,190
- Cells suppressed: 3,952
- k achieved: 5
- Aggregate cells: 18,925 of 22,877 retained

## What was shared

`PUBorough`, `DOBorough`, `pickup_bucket`, `trip_count`

## What was withheld

(none)

## Transforms applied (in order)

- **aggregate** — dimensions=['PUBorough', 'DOBorough', 'pickup_bucket'], minutes=60, k=5
