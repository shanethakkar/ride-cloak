# RideCloak validation report

- Source: `dev`
- Generated: 2026-06-09T23:18:05.837267+00:00
- Rows: 250,000
- Gate threshold: 90
- **Verdict: PASSED**

## Tier-1 structural contract: PASSED

## Health score: 99.9906 / 100

| dimension | score (of 100) |
|---|---:|
| completeness | 100.0 |
| validity | 99.9644 |
| consistency | 99.998 |
| uniqueness | 100.0 |

## Quality detail

- Completeness: 0 null cells of 6,250,000 (0.000%)
- Validity: 89 rows fail a value rule
- Consistency: 5 rows fail a cross-field rule
- Uniqueness: 0 duplicate rows

### Rules that fired

| rule | rows |
|---|---:|
| base_passenger_fare_negative | 89 |
| trip_time_mismatch | 5 |
