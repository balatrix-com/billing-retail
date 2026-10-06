# Architecture Evolution: Redis vs. Pure PostgreSQL

This document provides a simple, structured explanation of how the analytics dashboard system operated previously using Redis, compared to how it will operate under the newly proposed pure-PostgreSQL architecture.

---

## 🚀 Final Implementation Update

The system is now 100% PostgreSQL-based. We have removed Redis dependencies to simplify the architecture, improve data reliability (no cache loss on crash), and unify dashboard queries into a single SQL transaction.

---

## 🛠️ Server Setup (One-Time)

If you encounter the `externally-managed-environment` error when installing packages on the server, you must use a **Virtual Environment**. This is the standard best practice for modern Linux systems.

Run these commands in `/opt/bal_analysis`:

```bash
# 1. Create the virtual environment
python3 -m venv venv

# 2. Activate it
source venv/bin/activate

# 3. Install all dependencies
pip install -r requirements.txt
```

> [!TIP]
> Once activated, your terminal prompt will start with `(venv)`. You should always activate the environment before running `main.py` or `api.py`.

---

## 🧪 Manual Testing Guide

Follow these steps to verify that the entire analytics system (Database -> Processor -> API) is working correctly.

### 1. Initialize the Databases
1. **Source DB**: Ensure the `cdr` table exists in your billing database (e.g., `bala_billing`).
2. **Metrics DB**: Run `db_aggregates.sql` on your analytics database to create the metrics tables and job state.

### 2. Configure Environment
Update your `.env` file based on `.env.example`. You must provide credentials for both databases.

### 3. Generate Mock Data (Source)
```bash
python verify_integration.py
```
*This inserts mock calls into the **Source DB**.*

### 4. Start the System (Processor + API)
```bash
python main.py
```
*This now launches both the **Background Processor** (Source -> Metrics DB) and the **FastAPI Server** (Port 8001). Check logs to confirm both have started.*

#### 🌐 Browser Check
Open this URL replaced with your computer's IP or `localhost`:
`http://10.30.0.8:8001/analytics/dashboard?customer_id=CUST_1&range=today`

#### 💻 Curl Command
```bash
curl -X GET "http://10.30.0.8:8001/analytics/dashboard?customer_id=U0004&range=today" -H "accept: application/json"
```

---

## 🔌 API Documentation & Metrics Validation

The following metrics are provided by the `/analytics/dashboard` endpoint. Use this guide to verify each value.

### 1. KPI Cards (`kpi_cards`)
These are the high-level numbers shown at the top of the dashboard.
- `total_calls`: Total number of CDR records found for the period.
- `answered_calls`: Number of calls where `billsec > 0`.
- `missed_calls`: Number of calls where `billsec == 0`.
- `avg_duration_sec`: The average `duration_sec` across all **answered** calls.

### 2. Daily Trends (`daily_trend`)
- `bucket_day`: The date of the calls.
- `direction`: `inbound` or `outbound`.
- `total_calls`: Call count for that specific day and direction.

### 3. Top DIDs (`top_inbound_dids`)
- `did_value`: The callee phone number (for inbound calls).
- `inbound_calls`: Count of total incoming calls to this specific number.

### 4. Hourly Distribution (`hour_of_day_distribution`)
- `hour_of_day`: Number from 0 to 23.
- `direction`: `inbound` or `outbound`.
- `total_calls`: Combined count of calls made at that specific hour (across all dates).

---

## 🧪 Testing Guide

### Automated Tests (Unit Tests)
We use the standard `unittest` framework. These tests use mocks and do not require a live database connection.
```bash
python -m unittest test_processor.py
```

### Manual Integration Test
1. Clear the metrics state: `python reset_analytics.py`
2. Insert test data: `python verify_integration.py`
3. Run processor: `python main.py`
4. Confirm API output matches expected aggregations.
