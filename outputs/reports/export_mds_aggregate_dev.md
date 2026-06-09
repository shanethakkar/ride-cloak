# RideCloak methodology report — mds_aggregate v1

- Source: `dev`
- Generated: 2026-06-09T23:19:22.598945+00:00
- Output kind: aggregate
- Policy hash: `6844317ab135b45f...`
- Health score: 99.9906 (gate passed)
- Salt fingerprint: `n/a`
- Output: `outputs\exports\mds_aggregate_dev.csv`
- Output SHA-256: `431c602c3a31bc7c...`

## Volume

- Rows in: 250,000
- Rows out: 238,153
- Cells suppressed: 5,988
- k achieved: 5
- Aggregate cells: 9,000 of 14,988 retained

## What was shared

`PUBorough`, `DOBorough`, `pickup_bucket`, `trip_count`

## What was withheld

`DOLocationID`, `PULocationID`, `access_a_ride_flag`, `airport_fee`, `base_passenger_fare`, `bcf`, `cbd_congestion_fee`, `congestion_surcharge`, `device_id`, `dispatching_base_num`, `driver_license_num`, `driver_name`, `driver_pay`, `dropoff_datetime`, `hvfhs_license_num`, `on_scene_datetime`, `originating_base_num`, `payment_token`, `pickup_datetime`, `request_datetime`, `rider_email`, `rider_id`, `rider_phone`, `sales_tax`, `shared_match_flag`, `shared_request_flag`, `support_note`, `tips`, `tolls`, `trip_id`, `trip_miles`, `trip_time`, `vehicle_plate`, `vehicle_vin`, `wav_match_flag`, `wav_request_flag`

## Transforms applied (in order)

- **aggregate** — dimensions=['PUBorough', 'DOBorough', 'pickup_bucket'], minutes=60, k=5
