# Setup & Deployment Guide

Follow these instructions to set up the CDR Analytics system on a new server or local development environment.

## 1. Prerequisites
- Python 3.11+
- PostgreSQL (Two databases or two schemas)
- Access to the Billing (Source) database

## 2. Virtual Environment Setup
It is highly recommended to use a virtual environment, especially on Linux servers where system packages are managed:

```bash
# Create the environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# OR
.\venv\Scripts\activate  # Windows
```

## 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 4. Configuration
Create a `.env` file in the root directory. You can use `.env.example` as a template:

```ini
SOURCE_DB_HOST=10.30.0.8
SOURCE_DB_NAME=bala_billing
METRICS_DB_NAME=analytics_db
# ... other settings ...
```

## 5. Database Initialization
1. Ensure the **Source DB** has the `cdr` table.
2. Run the initialization script on the **Metrics DB**:
   ```bash
   psql -d analytics_db -f db_aggregates.sql
   ```

## 6. Running the System
Start both the background processor and the API with a single command:
```bash
python main.py
```

### Troubleshooting Port Conflicts
If you see `[Errno 98] Address already in use`, it means port 8001 is taken.
1. Find the process: `lsof -i :8001`
2. Kill it: `kill -9 <PID>`
3. Restart `main.py`.

## 7. Development & Testing
- **Insert Mock Data**: `python verify_integration.py`
- **Reset Metrics**: `python reset_analytics.py`
- **Run Unit Tests**: `python -m unittest test_processor.py`
