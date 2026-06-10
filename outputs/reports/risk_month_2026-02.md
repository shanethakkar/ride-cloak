# RideCloak re-identification risk report

- Source: `month:2026-02`
- Generated: 2026-06-10T00:56:16.543377+00:00
- Rows: 14,166,961
- Time bucket: 15 min | k: 5

## Uniqueness ladder (share of rows unique on the QI)

| quasi-identifier | uniqueness |
|---|---:|
| zone x minute | 89.49% |
| zone x 15min | 45.15% |
| zone x 60min | 21.29% |
| borough x 15min | 0.06% |

## k-anonymity suppression cost (k = 5)

| quasi-identifier | rows in | rows out | suppressed | k achieved |
|---|---:|---:|---:|---:|
| zone x 15min | 14,166,961 | 2,276,953 | 83.93% | 5 |
| borough x 15min | 14,166,961 | 14,130,222 | 0.26% | 5 |

Generalization is the dominant lever: zone-level data cannot be k-anonymized without rolling up to borough (decisions.md D-0008).
