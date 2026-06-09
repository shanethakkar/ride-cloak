# RideCloak re-identification risk report

- Source: `dev`
- Generated: 2026-06-09T22:04:50.331868+00:00
- Rows: 250,000
- Time bucket: 15 min | k: 5

## Uniqueness ladder (share of rows unique on the QI)

| quasi-identifier | uniqueness |
|---|---:|
| zone x minute | 99.80% |
| zone x 15min | 97.12% |
| zone x 60min | 90.42% |
| borough x 15min | 5.37% |

## k-anonymity suppression cost (k = 5)

| quasi-identifier | rows in | rows out | suppressed | k achieved |
|---|---:|---:|---:|---:|
| zone x 15min | 250,000 | 10 | 100.00% | 5 |
| borough x 15min | 250,000 | 191,591 | 23.36% | 5 |

Generalization is the dominant lever: zone-level data cannot be k-anonymized without rolling up to borough (decisions.md D-0008).
