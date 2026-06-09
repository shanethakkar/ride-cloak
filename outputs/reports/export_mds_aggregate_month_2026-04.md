# RideCloak methodology report — mds_aggregate v1

- Source: `month:2026-04`
- Generated: 2026-06-09T22:32:07.416710+00:00
- Output kind: aggregate
- Policy hash: `6844317ab135b45f...`
- Health score: None (gate passed)
- Salt fingerprint: `n/a`
- Output: `outputs\exports\mds_aggregate_month_2026-04.csv`
- Output SHA-256: `b645a07803117871...`

## Volume

- Rows in: 15,378,858
- Rows out: 15,370,445
- Cells suppressed: 4,217
- k achieved: 5
- Aggregate cells: 20,549 of 24,766 retained

## What was shared

`PUBorough`, `DOBorough`, `pickup_bucket`, `trip_count`

## What was withheld

(none)

## Transforms applied (in order)

- **aggregate** — dimensions=['PUBorough', 'DOBorough', 'pickup_bucket'], minutes=60, k=5
