# Database Schema & Tables

The system uses a dedicated analytics database (**Metrics DB**) to store pre-aggregated data. This ensures fast response times for the dashboard.

## 1. `cdr_metrics_day`
Stores daily aggregations per customer and call direction.

| Column | Type | Description |
| :--- | :--- | :--- |
| `customer_id` | TEXT | Unique ID of the customer (Primary Key) |
| `bucket_day` | DATE | The date of the calls (Primary Key) |
| `direction` | TEXT | `inbound` or `outbound` (Primary Key) |
| `total_calls` | BIGINT | Count of all calls |
| `answered_calls` | BIGINT | Count where duration > 0 |
| `missed_calls` | BIGINT | Count where duration = 0 |
| `total_duration_sec` | BIGINT | Sum of duration in seconds |
| `total_billsec` | BIGINT | Sum of billable seconds |

## 2. `cdr_metrics_hourly`
Stores hourly aggregations for fine-grained trend analysis.

| Column | Type | Description |
| :--- | :--- | :--- |
| `customer_id` | TEXT | Unique ID of the customer (Primary Key) |
| `bucket_hour` | TIMESTAMPTZ | The specific hour (Primary Key) |
| `direction` | TEXT | `inbound` or `outbound` (Primary Key) |
| `total_calls` | BIGINT | Count of calls in this hour |

## 3. `cdr_metrics_did_day`
Tracks call counts for specific Direct Inward Dialing (DID) numbers.

| Column | Type | Description |
| :--- | :--- | :--- |
| `customer_id` | TEXT | Unique ID of the customer (Primary Key) |
| `bucket_day` | DATE | The date (Primary Key) |
| `did_value` | TEXT | The phone number received (Primary Key) |
| `inbound_calls` | BIGINT | Total incoming calls to this number |

## 4. `metrics_job_state`
Maintains the internal state of the background processor.

| Column | Type | Description |
| :--- | :--- | :--- |
| `job_name` | TEXT | Name of the job (e.g., `cdr_analytics_processor`) (Primary Key) |
| `last_processed_cdr_id` | BIGINT | The ID of the last CDR successfully integrated |
| `updated_at` | TIMESTAMPTZ | Timestamp of the last successful update |

## Performance Considerations
- All tables use appropriate composite Primary Keys to ensure unique data and fast lookups.
- The use of `TIMESTAMPTZ` ensures consistency across different time zones.
- The processor uses UPSERT (INSERT ... ON CONFLICT) logic to handle real-time updates seamlessly.
