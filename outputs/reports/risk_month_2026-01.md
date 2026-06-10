# RideCloak re-identification risk report

- Source: `month:2026-01`
- Generated: 2026-06-10T01:34:14.431726+00:00
- Rows: 15,245,631
- Time bucket: 15 min | k: 5

## Uniqueness ladder (share of rows unique on the QI)

| quasi-identifier | uniqueness |
|---|---:|
| zone x minute | 89.51% |
| zone x 15min | 45.38% |
| zone x 60min | 21.45% |
| borough x 15min | 0.06% |

## k-anonymity suppression cost (k = 5)

| quasi-identifier | rows in | rows out | suppressed | k achieved |
|---|---:|---:|---:|---:|
| zone x 15min | 15,245,631 | 2,449,387 | 83.93% | 5 |
| borough x 15min | 15,245,631 | 15,204,375 | 0.27% | 5 |

Generalization is the dominant lever: zone-level data cannot be k-anonymized without rolling up to borough (decisions.md D-0008).
