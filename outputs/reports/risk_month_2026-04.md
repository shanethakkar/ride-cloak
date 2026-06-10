# RideCloak re-identification risk report

- Source: `month:2026-04`
- Generated: 2026-06-10T01:34:47.107289+00:00
- Rows: 15,378,858
- Time bucket: 15 min | k: 5

## Uniqueness ladder (share of rows unique on the QI)

| quasi-identifier | uniqueness |
|---|---:|
| zone x minute | 90.08% |
| zone x 15min | 46.05% |
| zone x 60min | 21.60% |
| borough x 15min | 0.06% |

## k-anonymity suppression cost (k = 5)

| quasi-identifier | rows in | rows out | suppressed | k achieved |
|---|---:|---:|---:|---:|
| zone x 15min | 15,378,858 | 2,261,943 | 85.29% | 5 |
| borough x 15min | 15,378,858 | 15,338,713 | 0.26% | 5 |

Generalization is the dominant lever: zone-level data cannot be k-anonymized without rolling up to borough (decisions.md D-0008).
