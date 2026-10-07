import time
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
import psycopg
import redis
from psycopg.rows import dict_row

from src.services.billing_service import BillingService
from src.config import config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class CDRProcessor:
    """
    Main batch processing orchestrator.
    Handles 11-step billing flow: fetch → lock → process → commit
    """
    
    def __init__(self, redis_client=None):
        self.billing_service = BillingService()
        self.batch_size = config.BILLING_BATCH_SIZE
        self.cache_dir = Path(__file__).parent.parent / 'cache'
        self.redis = redis_client or redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            password=config.REDIS_PASSWORD or None,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        self._ensure_caches_exist()

    def _sync_recording_gates(self, wallets: dict, customer_ids) -> None:
        """Reflect committed wallet purchasing power into the recording gate."""
        for customer_id in customer_ids:
            wallet = wallets.get(customer_id)
            if not wallet:
                continue
            fiat = Decimal(str(wallet.get('fiat_balance', 0) or 0))
            credit_limit = Decimal(str(wallet.get('credit_limit', 0) or 0))
            credit_used = Decimal(str(wallet.get('credit_used', 0) or 0))
            available_power = fiat + max(Decimal('0'), credit_limit - credit_used)
            try:
                if available_power <= Decimal('0'):
                    self.redis.sadd(config.RECORDING_OVERLIMIT_SET_KEY, customer_id)
                    logger.warning(
                        f"[RecordingGate] Customer {customer_id} reached $0 purchasing power. "
                        "Added to recording overlimit block."
                    )
                else:
                    self.redis.srem(config.RECORDING_OVERLIMIT_SET_KEY, customer_id)
            except Exception as exc:
                logger.error(f"[RecordingGate] Redis sync failed for {customer_id}: {exc}")
        
    def _ensure_caches_exist(self):
        rec_rc_cache = self.cache_dir / 'rec_rate_cards.json'
        rec_cc_cache = self.cache_dir / 'customer_rec_rc.json'

        if not rec_rc_cache.exists() or not rec_cc_cache.exists():
            logger.info("Recording cache files missing. Auto-generating via refresh_record_cache.py...")
            rec_script_path = Path(__file__).parent.parent.parent / 'scripts' / 'refresh_record_cache.py'
            try:
                subprocess.run([sys.executable, str(rec_script_path)], check=True)
                logger.info("Recording caches auto-generated successfully.")
            except Exception as e:
                logger.error(f"Failed to auto-generate recording cache: {e}")

    def load_rate_cards_cache(self) -> dict:
        """
        Load rate cards from JSON cache file.
        Cache should be refreshed via refresh_cache.py when rates change.
        
        Returns:
            {ratecard_id → {name, in_rate_per_sec, ob_rate_per_sec, ...}}
        """
        cache_file = self.cache_dir / 'rate_cards.json'
        
        try:
            with open(cache_file) as f:
                data = json.load(f)
            
            # Convert list to dict keyed by ratecard_id
            rate_cards = {}
            for rc in data.get('rate_cards', []):
                rate_cards[rc['ratecard_id']] = rc
            
            logger.debug(f"Loaded {len(rate_cards)} rate cards from cache")
            return rate_cards
            
        except Exception as e:
            logger.error(f"Failed to load rate cards cache: {e}")
            return {}
    
    def load_customer_ratecard_cache(self) -> dict:
        """
        Load customer→ratecard mappings from JSON cache file.
        Cache should be refreshed via refresh_cache.py when mappings change.
        
        Returns:
            {customer_id → {ratecard_id, effective_from, ...}}
        """
        cache_file = self.cache_dir / 'customer_ratecard.json'
        
        try:
            with open(cache_file) as f:
                data = json.load(f)
            
            # Convert list to dict keyed by customer_id
            customer_ratecards = {}
            for cr in data.get('customer_ratecard', []):
                customer_ratecards[cr['customer_id']] = cr
            
            logger.debug(f"Loaded {len(customer_ratecards)} customer ratecards from cache")
            return customer_ratecards
            
        except Exception as e:
            logger.error(f"Failed to load customer ratecard cache: {e}")
            return {}
    
    def load_rec_rate_cards_cache(self) -> dict:
        cache_file = self.cache_dir / 'rec_rate_cards.json'
        try:
            with open(cache_file) as f:
                data = json.load(f)
            rate_cards = {}
            for rc in data.get('rec_rate_cards', []):
                rate_cards[str(rc['id'])] = rc
            return rate_cards
        except Exception as e:
            logger.error(f"Failed to load rec rate cards cache: {e}")
            return {}
            
    def load_customer_rec_rc_cache(self) -> dict:
        cache_file = self.cache_dir / 'customer_rec_rc.json'
        try:
            with open(cache_file) as f:
                data = json.load(f)
            customer_rec_rc = {}
            for cr in data.get('customer_rec_rc', []):
                customer_rec_rc[str(cr['cust_id'])] = cr
            return customer_rec_rc
        except Exception as e:
            logger.error(f"Failed to load customer rec rc cache: {e}")
            return {}




    def process_batch(self) -> int:
        """
        Process one batch of unrated CDRs.
        Implements the complete 11-step billing flow.
        
        Steps:
        1. Fetch unrated CDRs
        2. Load caches (only if CDRs exist)
        3. Extract unique customer IDs
        4. BEGIN transaction
        5. Lock customer wallets
        6. Process each CDR in memory
        7. Bulk insert transactions
        8. Bulk update CDRs
        9. Bulk update wallets
        10. COMMIT
        11. Return count
        
        Returns:
            Number of CDRs successfully processed
        """
        conn = None
        cursor = None
        
        try:
            # Establish DB connection with retry + exponential backoff
            conn = None
            last_exc = None
            retries = getattr(config, 'DB_CONNECT_RETRIES', 3)
            backoff = getattr(config, 'DB_CONNECT_BACKOFF_SEC', 2)

            for attempt in range(1, retries + 1):
                try:
                    conn = psycopg.connect(
                        host=config.DB_HOST,
                        port=config.DB_PORT,
                        dbname=config.DB_NAME,
                        user=config.DB_USER,
                        password=config.DB_PASSWORD
                    )
                    break
                except Exception as e:
                    last_exc = e
                    logger.warning(f"DB connect attempt {attempt}/{retries} failed: {e}")
                    if attempt < retries:
                        sleep_for = backoff * (2 ** (attempt - 1))
                        logger.info(f"Retrying DB connect in {sleep_for}s...")
                        time.sleep(sleep_for)
                    else:
                        # re-raise to be handled by outer except and logged
                        raise
            cursor = conn.cursor(row_factory=dict_row)
            
            # STEP 1: Fetch unrated CDRs
            logger.info(f"Fetching up to {self.batch_size} unrated CDRs...")
            
            query = """
                SELECT 
                    cdr_id, call_uuid, customer_id, direction, duration_sec, billsec,
                    currency, ratecard_id, start_time, dest_type, dest_value, status_code, call_status, recording
                FROM cdr
                WHERE is_rated = false
                  AND (
                    lower(call_status) = 'answered'
                    OR lower(direction) = 'internal'
                  )
                ORDER BY cdr_id ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            """
            cursor.execute(query, (self.batch_size,))
            cdrs = cursor.fetchall()

            def _to_str(val):
                if isinstance(val, (bytes, bytearray, memoryview)):
                    try:
                        return bytes(val).decode('utf-8')
                    except Exception:
                        return str(val)
                return val
            
            if not cdrs:
                logger.info("No unrated CDRs found")
                cursor.close()
                conn.close()
                return 0
            
            logger.info(f"Found {len(cdrs)} CDRs to process")
            
            # STEP 2: Load caches (only if CDRs exist)
            rate_cards = {}
            customer_ratecards = {}
            rec_rate_cards = self.load_rec_rate_cards_cache()
            customer_rec_rc = self.load_customer_rec_rc_cache()
            batch_timestamp = datetime.now(timezone.utc)
            
            # STEP 3: Extract unique customer IDs
            # Normalize CDR fields that may come back as bytes
            for cdr in cdrs:
                cdr['customer_id'] = _to_str(cdr['customer_id'])
                cdr['direction'] = _to_str(cdr['direction'])
                cdr['currency'] = _to_str(cdr['currency'])
            customer_ids = list(set([cdr['customer_id'] for cdr in cdrs]))
            logger.info(f"Customer IDs for batch: {customer_ids} | types={[type(x).__name__ for x in customer_ids]}")
            logger.debug(f"Processing {len(customer_ids)} unique customers")
            
            # STEP 5: Lock customer wallets
            valid_customer_ids = [cid for cid in customer_ids if cid and str(cid).strip().lower() not in ('unknown', 'none', 'null')]
            logger.debug(f"Locking {len(valid_customer_ids)} valid customer wallets...")
            
            wallets = {}
            if valid_customer_ids:
                placeholders = ','.join(['%s'] * len(valid_customer_ids))
                wallet_query = f"""
                    SELECT 
                        customer_id, currency, fiat_balance, free_seconds,
                        credit_limit, credit_used, version
                    FROM customer_wallets
                    WHERE customer_id IN ({placeholders})
                    ORDER BY customer_id
                    FOR UPDATE
                """
                logger.info(f"Locking wallets for: {valid_customer_ids} | param types={[type(x).__name__ for x in valid_customer_ids]}")
                cursor.execute(wallet_query, tuple(valid_customer_ids))
                wallet_rows = cursor.fetchall()
                
                # Convert to dict
                for row in wallet_rows:
                    cust_id = _to_str(row['customer_id'])
                    currency = _to_str(row['currency'])
                    wallets[cust_id] = {
                        'currency': currency,
                        'fiat_balance': Decimal(str(row['fiat_balance'])),
                        'free_seconds': row['free_seconds'],
                        'credit_limit': Decimal(str(row['credit_limit'] or 0)),
                        'credit_used': Decimal(str(row['credit_used'] or 0)),
                        'version': row['version']
                    }
                logger.info(f"Locked {len(wallets)} wallets for customers: {list(wallets.keys())}")
            else:
                logger.info("No valid/known customer IDs to lock wallets for in this batch.")
            
            missing = sorted(set(valid_customer_ids) - set(wallets.keys()))
            if missing:
                logger.warning(f"Wallets missing for valid customers: {missing}")
            
            # STEP 6: Process each CDR in memory
            transactions_to_insert = []
            cdrs_to_update = []
            skipped_no_wallet = 0
            calc_failed = 0
            
            for cdr in cdrs:
                direction_norm = str(cdr.get('direction', '')).strip().lower()
                cust_id_norm = str(cdr.get('customer_id', '')).strip()
                
                # Handle unbillable / unknown customers or customers without wallets
                if (cust_id_norm.lower() in ('unknown', '', 'none', 'null') or cust_id_norm not in wallets) and direction_norm != 'internal':
                    logger.warning(f"CDR {cdr['cdr_id']}: unbillable customer '{cust_id_norm}' (no wallet). Marking as rated with $0.")
                    skipped_no_wallet += 1
                    cdrs_to_update.append({
                        'cdr_id': cdr['cdr_id'],
                        'transaction_id': None,
                        'billsec': cdr.get('billsec', 0) or 0,
                        'currency': cdr.get('currency') or 'USD',
                        'ratecard_id': None,
                        'billed_amount': Decimal('0'),
                        'recording_amount': Decimal('0'),
                        'total_amount': Decimal('0'),
                        'recording_days': 0,
                        'is_rated': True,
                        'rated_at': batch_timestamp
                    })
                    continue
                
                # Calculate billing
                transaction, cdr_update = self.billing_service.calculate_billing(
                    cdr,
                    rate_cards,
                    customer_ratecards,
                    rec_rate_cards,
                    customer_rec_rc,
                    wallets.get(cdr['customer_id']),
                    batch_timestamp
                )
                
                if transaction and cdr_update:
                    transactions_to_insert.append(transaction)
                    cdrs_to_update.append(cdr_update)
                else:
                    calc_failed += 1
                    logger.warning(f"CDR {cdr['cdr_id']}: billing calculation failed. Marking as rated with $0 to prevent stuck queue.")
                    cdrs_to_update.append({
                        'cdr_id': cdr['cdr_id'],
                        'transaction_id': None,
                        'billsec': cdr.get('billsec', 0) or 0,
                        'currency': cdr.get('currency') or 'USD',
                        'ratecard_id': None,
                        'billed_amount': Decimal('0'),
                        'recording_amount': Decimal('0'),
                        'total_amount': Decimal('0'),
                        'recording_days': 0,
                        'is_rated': True,
                        'rated_at': batch_timestamp
                    })
            
            if not cdrs_to_update:
                logger.info(
                    f"No CDRs to update after processing. "
                    f"CDRs: {len(cdrs)}, skipped_no_wallet={skipped_no_wallet}, calc_failed={calc_failed}"
                )
                cursor.close()
                conn.close()
                return 0
            
            # STEP 7: Bulk insert transactions (if any)
            if transactions_to_insert:
                logger.info(f"Processing {len(transactions_to_insert)} transactions...")
                tx_data = []
                for txn in transactions_to_insert:
                    tx_data.extend([
                        txn['customer_id'],
                        txn['source_type'],
                        txn['source_ref'],
                        txn['idempotency_key'],
                        txn['currency'],
                        txn['free_used_sec'],
                        txn['wallet_debit_amount'],
                        txn['amount_total'],
                        txn['ratecard_id'],
                        txn['rate_per_min'],
                        txn['billing_increment_sec'],
                        txn['status'],
                        txn['notes'],
                        txn['created_at'],
                        txn['recording_amount'],
                        txn['rec_ratecard_id']
                    ])
                
                num_txns = len(transactions_to_insert)
                tx_placeholders = ', '.join(['(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'] * num_txns)
                tx_insert_query = f"""
                    INSERT INTO transactions (
                        customer_id, source_type, source_ref, idempotency_key,
                        currency, free_used_sec, wallet_debit_amount, amount_total,
                        ratecard_id, rate_per_min, billing_increment_sec, status, notes, created_at,
                        recording_amount, rec_ratecard_id
                    )
                    VALUES {tx_placeholders}
                    RETURNING transaction_id, source_ref
                """
                
                cursor.execute(tx_insert_query, tx_data)
                results = cursor.fetchall()
                tx_by_cdr = {str(r['source_ref']): r['transaction_id'] for r in results}
                logger.debug(f"Inserted {len(results)} transactions")
                
                # Link transaction IDs to CDR updates
                for cdr_update in cdrs_to_update:
                    if str(cdr_update['cdr_id']) in tx_by_cdr:
                        cdr_update['transaction_id'] = tx_by_cdr[str(cdr_update['cdr_id'])]
            
            # STEP 8: Bulk update CDRs
            cdrs_data = []
            for cdr_update in cdrs_to_update:
                cdrs_data.extend([
                    cdr_update['cdr_id'],
                    cdr_update['transaction_id'],
                    cdr_update['billsec'],
                    cdr_update['currency'],
                    cdr_update['ratecard_id'],
                    cdr_update['billed_amount'],
                    cdr_update['recording_amount'],
                    cdr_update['total_amount'],
                    cdr_update['recording_days'],
                    cdr_update['rated_at']
                ])
            
            num_cdrs = len(cdrs_to_update)
            cdr_placeholders = ', '.join(['(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'] * num_cdrs)
            cdr_update_query = f"""
                UPDATE cdr AS c
                SET 
                    transaction_id = v.transaction_id::bigint,
                    billsec = v.billsec::integer,
                    currency = v.currency::varchar,
                    ratecard_id = v.ratecard_id::integer,
                    billed_amount = v.billed_amount::numeric,
                    recording_amount = v.recording_amount::numeric,
                    total_amount = v.total_amount::numeric,
                    recording_days = v.recording_days::integer,
                    is_rated = true,
                    rated_at = v.rated_at::timestamptz
                FROM (VALUES {cdr_placeholders}) AS v(cdr_id, transaction_id, billsec, currency, ratecard_id, billed_amount, recording_amount, total_amount, recording_days, rated_at)
                WHERE c.cdr_id = v.cdr_id::bigint
            """
            
            cursor.execute(cdr_update_query, cdrs_data)
            updated_cdrs = cursor.rowcount
            
            logger.info(f"Updated {updated_cdrs}/{len(cdrs_to_update)} CDR records in database")
            
            # STEP 9: Bulk update wallets
            wallets_to_update = []
            processed_customer_ids = {
                txn['customer_id']
                for txn in transactions_to_insert
                if txn.get('wallet_update_required', True)
            }
            
            for customer_id, wallet in wallets.items():
                if customer_id in processed_customer_ids:
                    wallets_to_update.extend([
                        customer_id,
                        wallet['fiat_balance'],
                        wallet['credit_used'],
                        batch_timestamp
                    ])
            
            num_wallets = len(wallets_to_update) // 4
            if num_wallets > 0:
                wallet_placeholders = ', '.join(['(%s, %s, %s, %s)'] * num_wallets)
                wallet_update_query = f"""
                    UPDATE customer_wallets AS cw
                    SET 
                        fiat_balance = v.fiat_balance::numeric,
                        credit_used = v.credit_used::numeric,
                        last_updated = v.last_updated::timestamptz,
                        version = cw.version + 1
                    FROM (VALUES {wallet_placeholders}) AS v(customer_id, fiat_balance, credit_used, last_updated)
                    WHERE cw.customer_id = v.customer_id::varchar
                """
                cursor.execute(wallet_update_query, wallets_to_update)
                updated_wallets = cursor.rowcount
            else:
                updated_wallets = 0
            
            logger.debug(f"Updated {updated_wallets} wallets")
            
            # STEP 10: Commit
            conn.commit()
            self._sync_recording_gates(wallets, valid_customer_ids)
            logger.info(f"Successfully committed batch: {len(cdrs_to_update)} CDRs processed")
            
            return len(cdrs_to_update)
        
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            return 0
        
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def run_continuous(self):
        """
        Run continuous processing loop.
        
        Sleep pattern:
        - 1 second after processing (check again quickly)
        - 60 seconds if no CDRs found (wait longer)
        - 5 seconds on error (retry)
        """
        logger.info("=" * 60)
        logger.info("Starting CDR processor in continuous mode...")
        logger.info(f"Batch size: {self.batch_size}, Interval: {config.PROCESSING_INTERVAL_SEC}s")
        logger.info("=" * 60)
        
        while True:
            try:
                processed = self.process_batch()
                
                if processed > 0:
                    # CDRs processed, check again soon
                    logger.debug(f"Sleeping 1s before next batch...")
                    time.sleep(1)
                else:
                    # No CDRs, wait longer
                    logger.info(f"Waiting {config.PROCESSING_INTERVAL_SEC}s for new CDRs...")
                    time.sleep(config.PROCESSING_INTERVAL_SEC)
            
            except KeyboardInterrupt:
                logger.info("Shutting down CDR processor...")
                break
            
            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                time.sleep(5)  # Wait before retrying on error
