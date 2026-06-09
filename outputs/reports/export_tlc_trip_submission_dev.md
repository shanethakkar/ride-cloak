# RideCloak methodology report — tlc_trip_submission v1

- Source: `dev`
- Generated: 2026-06-09T22:33:09.739672+00:00
- Output kind: row_level
- Policy hash: `a6a1314ca81830f5...`
- Health score: 99.9906 (gate passed)
- Salt fingerprint: `f10ddfdccf2bba716e25010ba8bab1b7cf4bc6d9f3c720f8b89e2382ed2b7e89`
- Output: `outputs\exports\tlc_trip_submission_dev.parquet`
- Output SHA-256: `03689f301bd47b1d...`

## Volume

- Rows in: 250,000
- Rows out: 250,000
- Cells suppressed: 0

## What was shared

`hvfhs_license_num`, `dispatching_base_num`, `originating_base_num`, `request_datetime`, `on_scene_datetime`, `pickup_datetime`, `dropoff_datetime`, `PULocationID`, `DOLocationID`, `trip_miles`, `trip_time`, `base_passenger_fare`, `tolls`, `bcf`, `sales_tax`, `congestion_surcharge`, `airport_fee`, `tips`, `driver_pay`, `shared_request_flag`, `shared_match_flag`, `access_a_ride_flag`, `wav_request_flag`, `wav_match_flag`, `cbd_congestion_fee`, `trip_id`, `rider_id`, `rider_phone`, `rider_email`, `device_id`, `payment_token`, `driver_license_num`, `driver_name`, `vehicle_plate`, `vehicle_vin`, `support_note`

## What was withheld

(none)

## Transforms applied (in order)

- **redact_note** — rows_redacted=3705, spans_masked=7828
- **pseudonymize** — columns=['trip_id', 'rider_id', 'rider_phone', 'rider_email', 'device_id', 'payment_token', 'driver_license_num', 'driver_name', 'vehicle_plate', 'vehicle_vin']
- **generalize_time** — minutes=15
