# RideCloak re-identification risk report

- Source: `month:2026-03`
- Generated: 2026-06-10T00:56:28.638494+00:00
- Rows: 15,956,175
- Time bucket: 15 min | k: 5

## Uniqueness ladder (share of rows unique on the QI)

| quasi-identifier | uniqueness |
|---|---:|
| zone x minute | 89.86% |
| zone x 15min | 45.83% |
| zone x 60min | 21.51% |
| borough x 15min | 0.06% |

## k-anonymity suppression cost (k = 5)

| quasi-identifier | rows in | rows out | suppressed | k achieved |
|---|---:|---:|---:|---:|
| zone x 15min | 15,956,175 | 2,424,413 | 84.81% | 5 |
| borough x 15min | 15,956,175 | 15,914,859 | 0.26% | 5 |

Generalization is the dominant lever: zone-level data cannot be k-anonymized without rolling up to borough (decisions.md D-0008).
