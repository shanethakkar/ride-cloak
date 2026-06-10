# RideCloak methodology report — mds_aggregate v1

- Source: `month:2026-01`
- Generated: 2026-06-10T01:34:16.304687+00:00
- Output kind: aggregate
- Policy hash: `6844317ab135b45f...`
- Health score: None (gate passed)
- Salt fingerprint: `n/a`
- Output: `outputs\exports\mds_aggregate_month_2026-01.csv`
- Output SHA-256: `799f317cf217c095...`

## Volume

- Rows in: 15,245,631
- Rows out: 15,236,553
- Cells suppressed: 4,485
- k achieved: 5
- Aggregate cells: 20,761 of 25,246 retained

## What was shared

`PUBorough`, `DOBorough`, `pickup_bucket`, `trip_count`

## What was withheld

(none)

## Transforms applied (in order)

- **aggregate** — dimensions=['PUBorough', 'DOBorough', 'pickup_bucket'], minutes=60, k=5
