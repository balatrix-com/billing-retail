# Billing System

Python-based billing system for processing CDR (Call Detail Records), calculating standard and recording billing, and generating financial transactions.

## Setup

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```
.\venv\Scripts\Activate.ps1

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## PM2 Deployment

We use PM2 to manage the backend billing processor. You can run the billing engine continuously in the background using the provided ecosystem file:
```bash
pm2 start ecosystem.config.js
pm2 save
```
*(Note: Ensure paths in `ecosystem.config.js` match your server environment).*

## API Usage

The billing system provides cache refresh API endpoints to update in-memory configurations without restarting.

### Start API Server
```bash
python src/api_server.py
```

### Trigger Rate Card Cache Refresh
```bash
curl -X POST http://10.30.0.8:8000/api/v1/cache/refresh -H "X-Auth-Token: <dev-token-123>"
```

### Trigger Recording Rate Card Cache Refresh
```bash
curl -X POST http://10.30.0.8:8000/api/v1/cache/refresh-record -H "X-Auth-Token: <dev-token-123>"
```
