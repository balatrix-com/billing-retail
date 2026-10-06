import time
import logging
import multiprocessing
import uvicorn
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

def run_processor():
    """
    Main continuous processing loop with Dual-DB support.
    Fetches raw CDRs from Source DB and writes aggregated metrics to Metrics DB.
    """
    logger.info("Starting CDR Analytics Processor Service (Dual-DB Mode)...")

    while True:
        source_conn = None
        metrics_conn = None
        try:
            source_conn = get_source_db_connection()
            metrics_conn = get_metrics_db_connection()
            from psycopg2.extras import RealDictCursor

            # --- Inner loop: reuse connections during peak load ---
            while True:
                with source_conn.cursor(cursor_factory=RealDictCursor) as source_cursor, \
                     metrics_conn.cursor(cursor_factory=RealDictCursor) as metrics_cursor:
                    
                    # 1. Get state from Metrics DB
                    last_id = fetch_last_processed_id(metrics_cursor)
                    
                    # 2. Fetch batch from Source DB
                    cdrs = fetch_cdr_batch(source_cursor, last_id, settings.BATCH_SIZE)

                    if not cdrs:
                        logger.debug(f"Checked for new data: last_id={last_id}. No new records.")
                        break

                    start_id = cdrs[0]['cdr_id']
                    end_id = cdrs[-1]['cdr_id']
                    processed_count = len(cdrs)
                    
                    logger.info(f"PROCESSING START: IDs {start_id} to {end_id} ({processed_count} records)")

                    # 3. Process and write to Metrics DB
                    process_cdr_analytics(cdrs, metrics_cursor)

                    # 4. Update state in Metrics DB
                    update_last_processed_id(metrics_cursor, end_id)
                    
                    # 5. Commit Metrics DB changes
                    metrics_conn.commit()
                    
                    # --- SAFETY CHECK: VERIFY PERSISTENCE ---
                    # We start a fresh transaction/cursor to see what the DB actually saved
                    metrics_conn.commit() # Ensure previous one is clean
                    with metrics_conn.cursor(cursor_factory=RealDictCursor) as verify_cursor:
                        saved_id = fetch_last_processed_id(verify_cursor)
                        if saved_id != end_id:
                            logger.error(f"CRITICAL: State persistence failure! Expected {end_id} but found {saved_id} in DB.")
                            logger.error("Stopping processor to prevent over-counting.")
                            return # Terminate the loop immediately
                        else:
                            logger.info(f"VERIFIED: State successfully advanced to {end_id}")

                    if processed_count < settings.BATCH_SIZE:
                        logger.info(f"Caught up with data. Sleeping.")
                        break 
                    else:
                        logger.info("Moving to next batch immediately...")

        except Exception as e:
            logger.error(f"Error in processing loop: {e}")
            if metrics_conn:
                try: metrics_conn.rollback()
                except: pass
        finally:
            for c in [source_conn, metrics_conn]:
                if c:
                    try: c.close()
                    except: pass

        # Smart Sleep: we only reach here when caught up or on error
        logger.info(f"Smart Sleep: sleeping {settings.LOOP_INTERVAL_SEC}s before next poll.")
        time.sleep(settings.LOOP_INTERVAL_SEC)

def run_api():
    """
    Starts the FastAPI server using settings from config.
    """
    logger.info(f"Starting API Server on {settings.API_HOST}:{settings.API_PORT}...")
    uvicorn.run("api:app", host=settings.API_HOST, port=settings.API_PORT, log_level="info")

if __name__ == "__main__":
    # Create separate processes for the Processor and the API
    processor_process = multiprocessing.Process(target=run_processor, name="ProcessorProcess")
    api_process = multiprocessing.Process(target=run_api, name="APIProcess")

    logger.info("Launching CDR Analytics System (Processor + API)...")
    
    processor_process.start()
    api_process.start()

    try:
        # Wait for processes to complete (which they won't unless they crash or are stopped)
        processor_process.join()
        api_process.join()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received (Ctrl+C). Terminating processes...")
        processor_process.terminate()
        api_process.terminate()
        processor_process.join()
        api_process.join()
        logger.info("System shutdown complete.")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        processor_process.terminate()
        api_process.terminate()

