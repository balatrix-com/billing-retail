import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings
import logging

logger = logging.getLogger(__name__)

def get_source_db_connection():
    """
    Creates and returns a connection to the SOURCE PostgreSQL database (bala_billing).
    """
    try:
        conn = psycopg2.connect(
            host=settings.SOURCE_DB_HOST,
            port=settings.SOURCE_DB_PORT,
            user=settings.SOURCE_DB_USER,
            password=settings.SOURCE_DB_PASSWORD,
            dbname=settings.SOURCE_DB_NAME
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to SOURCE PostgreSQL: {e}")
        raise

def get_metrics_db_connection():
    """
    Creates and returns a connection to the METRICS PostgreSQL database.
    """
    try:
        conn = psycopg2.connect(
            host=settings.METRICS_DB_HOST,
            port=settings.METRICS_DB_PORT,
            user=settings.METRICS_DB_USER,
            password=settings.METRICS_DB_PASSWORD,
            dbname=settings.METRICS_DB_NAME
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to METRICS PostgreSQL: {e}")
        raise

# For backward compatibility / convenience
def get_db_connection():
    return get_metrics_db_connection()

def fetch_last_processed_id(cursor):
    """
    Retrieves the last processed CDR ID from the metrics_job_state table.
    This ensures the processor resumes from where it left off.
    """
    query = "SELECT last_processed_cdr_id FROM metrics_job_state WHERE job_name = %s"
    cursor.execute(query, (settings.PROCESSOR_NAME,))
    result = cursor.fetchone()
    return result['last_processed_cdr_id'] if result else 0

def fetch_cdr_batch(cursor, last_id, batch_size):
    """
    Fetches a batch of CDR records from the database that have a higher ID than last_id.
    Ordered by ID to ensure sequential processing.
    """
    query = """
        SELECT * FROM cdr 
        WHERE cdr_id > %s 
        ORDER BY cdr_id ASC 
        LIMIT %s
    """
    cursor.execute(query, (last_id, batch_size))
    return cursor.fetchall()

def update_last_processed_id(cursor, last_id):
    """
    Updates the metrics_job_state table with the ID of the last successfully processed CDR.
    Uses UPSERT logic to ensure the row exists.
    """
    query = """
        INSERT INTO metrics_job_state (job_name, last_processed_cdr_id, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (job_name) DO UPDATE SET 
            last_processed_cdr_id = EXCLUDED.last_processed_cdr_id,
            updated_at = EXCLUDED.updated_at
    """
    cursor.execute(query, (settings.PROCESSOR_NAME, last_id))

def upsert_cdr_metrics_day(cursor, records):
    """
    Bulk upsert array of tuples into cdr_metrics_day
    records format: [(customer_id, bucket_day, direction, total_calls, answered_calls, missed_calls, total_duration_sec, total_billsec), ...]
    """
    if not records: return
    query = """
        INSERT INTO cdr_metrics_day 
        (customer_id, bucket_day, direction, total_calls, answered_calls, missed_calls, total_duration_sec, total_billsec)
        VALUES %s
        ON CONFLICT (customer_id, bucket_day, direction) DO UPDATE SET 
            total_calls = cdr_metrics_day.total_calls + EXCLUDED.total_calls,
            answered_calls = cdr_metrics_day.answered_calls + EXCLUDED.answered_calls,
            missed_calls = cdr_metrics_day.missed_calls + EXCLUDED.missed_calls,
            total_duration_sec = cdr_metrics_day.total_duration_sec + EXCLUDED.total_duration_sec,
            total_billsec = cdr_metrics_day.total_billsec + EXCLUDED.total_billsec,
            updated_at = NOW()
    """
    from psycopg2.extras import execute_values
    execute_values(cursor, query, records)

def upsert_cdr_metrics_hourly(cursor, records):
    """
    Bulk upsert array of tuples into cdr_metrics_hourly
    records format: [(customer_id, bucket_hour, direction, total_calls, answered_calls, missed_calls, total_duration_sec), ...]
    """
    if not records: return
    query = """
        INSERT INTO cdr_metrics_hourly 
        (customer_id, bucket_hour, direction, total_calls, answered_calls, missed_calls, total_duration_sec)
        VALUES %s
        ON CONFLICT (customer_id, bucket_hour, direction) DO UPDATE SET 
            total_calls = cdr_metrics_hourly.total_calls + EXCLUDED.total_calls,
            answered_calls = cdr_metrics_hourly.answered_calls + EXCLUDED.answered_calls,
            missed_calls = cdr_metrics_hourly.missed_calls + EXCLUDED.missed_calls,
            total_duration_sec = cdr_metrics_hourly.total_duration_sec + EXCLUDED.total_duration_sec,
            updated_at = NOW()
    """
    from psycopg2.extras import execute_values
    execute_values(cursor, query, records)

def upsert_cdr_metrics_did_day(cursor, records):
    """
    Bulk upsert array of tuples into cdr_metrics_did_day
    records format: [(customer_id, bucket_day, did_value, inbound_calls, answered_calls, missed_calls), ...]
    """
    if not records: return
    query = """
        INSERT INTO cdr_metrics_did_day 
        (customer_id, bucket_day, did_value, inbound_calls, answered_calls, missed_calls)
        VALUES %s
        ON CONFLICT (customer_id, bucket_day, did_value) DO UPDATE SET 
            inbound_calls = cdr_metrics_did_day.inbound_calls + EXCLUDED.inbound_calls,
            answered_calls = cdr_metrics_did_day.answered_calls + EXCLUDED.answered_calls,
            missed_calls = cdr_metrics_did_day.missed_calls + EXCLUDED.missed_calls,
            updated_at = NOW()
    """
    from psycopg2.extras import execute_values
    execute_values(cursor, query, records)

def upsert_cdr_metrics_hour_of_day(cursor, records):
    """
    Bulk upsert array of tuples into cdr_metrics_hour_of_day
    records format: [(customer_id, hour_of_day, direction, total_calls), ...]
    """
    if not records: return
    query = """
        INSERT INTO cdr_metrics_hour_of_day 
        (customer_id, hour_of_day, direction, total_calls)
        VALUES %s
        ON CONFLICT (customer_id, hour_of_day, direction) DO UPDATE SET 
            total_calls = cdr_metrics_hour_of_day.total_calls + EXCLUDED.total_calls,
            updated_at = NOW()
    """
    from psycopg2.extras import execute_values
    execute_values(cursor, query, records)
