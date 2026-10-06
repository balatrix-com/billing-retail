# CDR Analytics Backend System

A real-time analytics aggregation and dashboard system built for high-performance processing of Call Detail Records (CDRs).

## 🚀 Key Improvements
The system has been migrated to a **pure PostgreSQL architecture**. We have removed all Redis dependencies to simplify setup, improve data persistence, and utilize powerful SQL features for dashboard analytics.

## 📁 Project Structure
- **[main.py](file:///c:/bal_analysis/main.py)**: The unified system entry point (manages both Processor and API processes).
- **[api.py](file:///c:/bal_analysis/api.py)**: FastAPI dashboard endpoint implementation.
- **[processor.py](file:///c:/bal_analysis/processor.py)**: Core business logic for aggregating CDR metrics.
- **[db.py](file:///c:/bal_analysis/db.py)**: PostgreSQL connection management (Dual-DB support).
- **[documentation/](file:///c:/bal_analysis/documentation/)**: Comprehensive project guides and technical reference.

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL (Source and Metrics databases)

### 2. Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create environment config
cp .env.example .env  # Update with your credentials
```

### 3. Initialize Metrics DB
```bash
psql -d analytics_db -f db_aggregates.sql
```

### 4. Start the System
Launch both the Background Processor and the Dashboard API with a single command:
```bash
python main.py
```

## 📖 Detailed Documentation
For more in-depth information, please refer to the following guides:
- **[Overview](file:///c:/bal_analysis/documentation/overview.md)**: System goals and features.
- **[Architecture](file:///c:/bal_analysis/documentation/architecture.md)**: Data flow and process management.
- **[Database Schema](file:///c:/bal_analysis/documentation/databases.md)**: Table definitions and purpose.
- **[API Reference](file:///c:/bal_analysis/documentation/apis.md)**: Endpoint documentation and examples.
- **[Setup Guide](file:///c:/bal_analysis/documentation/setup.md)**: Detailed deployment and troubleshooting.

## 🧪 Testing
- **Insert Mock Data**: `python verify_integration.py`
- **Reset Metrics**: `python reset_analytics.py`
- **Run Unit Tests**: `python -m unittest test_processor.py`
