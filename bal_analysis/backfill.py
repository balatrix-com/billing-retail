import logging
import time
from config import settings
from db import (
    get_source_db_connection, 
    get_metrics_db_connection,
    fetch_last_processed_id, 
    fetch_cdr_batch, 
    update_last_processed_id
)
from processor import process_cdr_analytics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_backfill():
    """
    Dedicated script for processing historical data at high speed with Dual-DB support.
    """
    logger.info("Starting Historical CDR Backfill Processor (Dual-DB Mode)...")
    
    backfill_batch_size = 5000 
    total_processed = 0
    source_conn = None
    metrics_conn = None
    try:
        source_conn = get_source_db_connection()
        metrics_conn = get_metrics_db_connection()
        
        while True:
            from psycopg2.extras import RealDictCursor
            with source_conn.cursor(cursor_factory=RealDictCursor) as source_cursor, \
                 metrics_conn.cursor(cursor_factory=RealDictCursor) as metrics_cursor:
                
                # 1. Get state from Metrics DB
                last_id = fetch_last_processed_id(metrics_cursor)
                
                # 2. Fetch from Source DB
                cdrs = fetch_cdr_batch(source_cursor, last_id, backfill_batch_size)
                
                if not cdrs:
                    logger.info("No more historical records found. Backfill complete.")
                    break
                
                start_id = cdrs[0]['cdr_id']
                end_id = cdrs[-1]['cdr_id']
                logger.info(f"BACKFILL START: IDs {start_id} to {end_id} ({len(cdrs)} records)")

                # 3. Process and write to Metrics DB
                process_cdr_analytics(cdrs, metrics_cursor)
                
                # 4. Update state in Metrics DB
                update_last_processed_id(metrics_cursor, end_id)
                
                # 5. Commit Metrics DB
                metrics_conn.commit()
                
                # --- SAFETY CHECK: VERIFY PERSISTENCE ---
                # Fresh select to confirm DB actually saved the ID
                with metrics_conn.cursor(cursor_factory=RealDictCursor) as verify_cursor:
                    saved_id = fetch_last_processed_id(verify_cursor)
                    if saved_id != end_id:
                        logger.error(f"CRITICAL: Backfill state persistence failure! Expected {end_id} but found {saved_id}")
                        break
                    else:
                        logger.info(f"VERIFIED: Backfill state advanced to {end_id}")
                
                total_processed += len(cdrs)
                logger.info(f"Total historical records processed so far: {total_processed}")

    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        if metrics_conn:
            metrics_conn.rollback()
    finally:
        for c in [source_conn, metrics_conn]:
            if c:
                try: c.close()
                except: pass

if __name__ == "__main__":
    run_backfill()
