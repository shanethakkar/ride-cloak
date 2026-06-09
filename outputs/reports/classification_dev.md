# RideCloak classification & PII detection report

- Source: `dev`
- Generated: 2026-06-09T23:18:40.051568+00:00
- Notes scanned: 4,952 (3,702 PII, 1,250 decoy)
- spaCy model: `en_core_web_lg` | score threshold: 0.5
- Targets: recall >= 0.95, precision >= 0.9
- **Verdict: PASSED** (overall recall 0.9977, precision 0.9974)

## Field classification

| tier | columns |
|---|---:|
| direct | 10 |
| quasi | 8 |
| sensitive | 4 |
| safe | 14 |

## Detection metrics (per entity)

| entity | TP | FP | FN | precision | recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| CREDIT_CARD | 399 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| EMAIL_ADDRESS | 828 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| LOCATION | 1220 | 17 | 0 | 0.9863 | 1.0 | 0.9931 |
| NY_PLATE | 386 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| PERSON | 2474 | 2 | 16 | 0.9992 | 0.9936 | 0.9964 |
| PHONE_NUMBER | 1686 | 1 | 2 | 0.9994 | 0.9988 | 0.9991 |
| TLC_LICENSE | 409 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| VEHICLE_VIN | 406 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| **overall** | 7808 | 20 | 18 | 0.9974 | 0.9977 | 0.9976 |
