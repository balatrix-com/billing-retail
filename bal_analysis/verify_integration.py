import time
from db import get_source_db_connection
from mock_generator import generate_mock_cdr
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def insert_cdrs(count):
    conn = get_source_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get max ID
            cursor.execute("SELECT MAX(cdr_id) FROM cdr")
            max_id = cursor.fetchone()[0] or 0
            
            logger.info(f"Inserting {count} mock CDRs starting from ID {max_id + 1}...")
            for i in range(1, count + 1):
                cdr = generate_mock_cdr(max_id + i)
                cursor.execute("""
                    INSERT INTO cdr (cdr_id, call_uuid, customer_id, caller, callee, direction, start_time, end_time, duration_sec, billsec, billed_amount, currency, status_code, call_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    cdr['cdr_id'], cdr['call_uuid'], cdr['customer_id'], cdr['caller'], 
                    cdr['callee'], cdr['direction'], cdr['start_time'], cdr['end_time'], 
                    cdr['duration_sec'], cdr['billsec'], cdr['billed_amount'], cdr['currency'],
                    cdr.get('status_code'), cdr.get('call_status')
                ))
            conn.commit()
            logger.info(f"Done inserting {count} CDRs.")
    finally:
        conn.close()

if __name__ == "__main__":
    # 1. Insert 5 CDRs
    insert_cdrs(5)
    
    # 2. Insert 1000 CDRs (full batch)
    # insert_cdrs(SETTINGS.BATCH_SIZE)
    
    print("\nVerification data inserted. Now run 'python main.py' and observe logs.")
    print("Expected: Process 5, then sleep 5s. If you insert 1000, it should process and immediately check again.")
