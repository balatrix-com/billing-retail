# CDR Processor Optimization Verification

The recent changes to `src/services/cdr_processor.py` optimized database interactions from loop-based individual queries to large, set-based bulk `INSERT` and `UPDATE` mechanisms. Follow the steps below to verify the correctness and performance of this update.

## Prerequisites
1. Ensure your local PostgreSQL database is up and configured.
2. The `api_server` or core billing test suite should be functional.

## Step 1: Pre-populate Test Data
Ensure that you have an unrated batch of CDRs alongside the associated rate cards and customer wallets. 

```sql
-- Check current unrated CDRs
SELECT COUNT(*) FROM cdr WHERE is_rated = false;

-- Check wallet balances before running the processor
SELECT customer_id, fiat_balance, version FROM customer_wallets;
```

## Step 2: Run the Processor
You can test the logic by manually running the CDR batch processing loop.
```bash
python -c "from src.services.cdr_processor import CDRProcessor; CDRProcessor().process_batch()"
```

## Step 3: Verify Transactions and CDR Updates
Ensure the database accurately reflects the computations without any missing records.

**a. CDRs updated correctly:**
```sql
-- Ensure all recently processed CDRs have a corresponding non-null transaction_id and is_rated = true
SELECT cdr_id, is_rated, transaction_id, billed_amount 
FROM cdr 
WHERE is_rated = true
ORDER BY rated_at DESC 
LIMIT 100;
```

**b. Transactions inserted correctly:**
```sql
-- Ensure valid transactions were inserted
SELECT * FROM transactions ORDER BY created_at DESC LIMIT 100;
```

**c. Wallets updated correctly:**
```sql
-- Ensure balances reduced and the version bumped
SELECT customer_id, fiat_balance, version FROM customer_wallets;
```

## Step 4: Verify Logging
Confirm that your application logs read properly. A single `INSERT` message and a single `UPDATE` message should appear per batch step, instead of 100 recurring loop executions.

```log
INFO: Fetching up to 100 unrated CDRs...
DEBUG: Inserted 100 transactions
INFO: Updated 100/100 CDR records in database
DEBUG: Updated X wallets
INFO: Successfully committed batch: 100 CDRs processed
```

curl -X POST http://10.30.0.61:5005/api/v1/cache/refresh
sudo kill -9 <415772>
