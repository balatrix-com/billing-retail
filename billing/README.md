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
Both POST routes require `X-Auth-Token` matching `REFRESH_CACHE_TOKEN` (a unique
random value of at least 32 characters). The API binds to `127.0.0.1:8005` by
default; see [Phase 4.1 deployment settings](../../security_phase4_1_deployment.md)
for private-interface deployments and caller configuration.

### Start API Server
```bash
python src/api_server.py
```

### Trigger Rate Card Cache Refresh
```bash
curl -X POST http://127.0.0.1:8005/api/v1/cache/refresh -H "X-Auth-Token: <configured-token>"
```

### Trigger Recording Rate Card Cache Refresh
```bash
curl -X POST http://127.0.0.1:8005/api/v1/cache/refresh-record -H "X-Auth-Token: <configured-token>"
```
