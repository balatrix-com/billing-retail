import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def reset_and_backfill():
    print("Resetting state and aggregate tables...")
    conn = psycopg2.connect(
        host=os.getenv("METRICS_DB_HOST", "localhost"),
        port=int(os.getenv("METRICS_DB_PORT", 5432)),
        user=os.getenv("METRICS_DB_USER", "postgres"),
        password=os.getenv("METRICS_DB_PASSWORD", "postgres"),
        dbname=os.getenv("METRICS_DB_NAME", "analytics_db")
    )
    conn.autocommit = True
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO metrics_job_state (job_name, last_processed_cdr_id)
            VALUES ('cdr_analytics_processor', 0)
            ON CONFLICT (job_name) DO UPDATE SET 
                last_processed_cdr_id = 0,
                updated_at = NOW()
        """)
        cursor.execute("TRUNCATE cdr_metrics_day, cdr_metrics_hourly, cdr_metrics_did_day, cdr_metrics_hour_of_day")
    conn.close()
    print("Reset complete.")

if __name__ == "__main__":
    reset_and_backfill()
