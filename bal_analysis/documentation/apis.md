# API Reference

The CDR Analytics API is built with FastAPI and provides optimized data for dashboard visualization.

## 📡 Get Dashboard Data

Returns a complete set of analytics metrics for a specific customer over a given date range.

- **URL**: `/analytics/dashboard`
- **Method**: `GET`
- **Response Type**: `application/json`

### Query Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `customer_id` | string | **Yes** | The unique ID of the customer (e.g., `U0004`). |
| `range` | string | No | The date period. Defaults to `today`. <br>Supported: `today`, `yesterday`, `7_days`, `30_days`, `1_month`. |

### 📥 Example Request

```bash
curl -X GET "http://localhost:8001/analytics/dashboard?customer_id=U0004&range=last_7_days"
```

### 📤 Example Response

```json
{
  "range": "last_7_days",
  "customer_id": "U0004",
  "start_date": "2026-04-15",
  "end_date": "2026-04-22",
  "kpi_cards": {
    "total_calls": 1250,
    "answered_calls": 980,
    "missed_calls": 270,
    "avg_duration_sec": 45.2
  },
  "daily_trend": [
    {
      "bucket_day": "2026-04-21",
      "direction": "inbound",
      "total_calls": 150
    }
  ],
  "top_inbound_dids": [
    {
      "did_value": "101",
      "inbound_calls": 45
    }
  ],
  "hour_of_day_distribution": [
    {
      "hour_of_day": 14,
      "direction": "inbound",
      "total_calls": 85
    }
  ]
}
```

### Response Fields

- **`kpi_cards`**: Summarized totals for the entire range.
- **`daily_trend`**: Call volumes grouped by day and direction.
- **`top_inbound_dids`**: The most called numbers for the customer.
- **`hour_of_day_distribution`**: Heatmap data showing peak calling hours (0-23).

## 🛠️ Diagnostics
If the API returns `500 Internal Server Error`, check the `main.py` logs. Common issues include database connection timeouts or missing environment variables.
