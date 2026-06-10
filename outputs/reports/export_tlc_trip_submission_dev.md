# RideCloak methodology report — tlc_trip_submission v1

- Source: `dev`
- Generated: 2026-06-10T01:35:27.671413+00:00
- Output kind: row_level
- Policy hash: `a6a1314ca81830f5...`
- Health score: 99.9906 (gate passed)
- Salt fingerprint: `04dbb71cf6e0aa4ee656f0d95a14cabdfb2efd9a62e909020e67f00e4fd5f3f2`
- Output: `outputs\exports\tlc_trip_submission_dev.parquet`
- Output SHA-256: `eaf720af0d295a50...`

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
