from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from db import get_metrics_db_connection
from datetime import datetime, timedelta
import logging
from psycopg2.extras import RealDictCursor

app = FastAPI(title="CDR Analytics Dashboard API")
logger = logging.getLogger(__name__)

def format_duration(seconds: float) -> str:
    """
    Formats seconds into a human-readable string.
    If >= 60, shows minutes and seconds (e.g. 1m 30s).
    Otherwise shows seconds (e.g. 45s).
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    
    minutes = int(seconds // 60)
    remaining_secs = int(seconds % 60)
    
    if remaining_secs == 0:
        return f"{minutes}m"
    return f"{minutes}m {remaining_secs}s"

def get_date_range(range_param: str):
    today = datetime.now().date()
    # Normalize input: remove underscores, spaces, and convert to lowercase
    rp = range_param.lower().replace("_", "").replace(" ", "")
    
    if rp in ['today', '1day', '1']:
        return today, today
    elif rp == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif rp in ['last7days', '7days', '7']:
        return today - timedelta(days=6), today
    elif rp in ['last30days', '30days', '30', '1month', 'month']:
        return today - timedelta(days=29), today
    else:
        # Default to today if unknown to prevent confusion, 
        # but you can log this for debugging
        logger.warning(f"Unknown range parameter received: {range_param}. Defaulting to 'today'.")
        return today, today

@app.get("/analytics/dashboard")
async def get_dashboard(
    customer_id: str | None = Query(None, description="Customer ID (optional; omit for global analytics)"),
    range: str = Query('today', description="Date range: today, yesterday, last_7_days, last_30_days")
):
    start_date, end_date = get_date_range(range)
    
    query = """
    WITH kpi AS (
        SELECT 
            COALESCE(SUM(total_calls), 0) AS total_calls,
            COALESCE(SUM(answered_calls), 0) AS answered_calls,
            COALESCE(SUM(missed_calls), 0) AS missed_calls,
            CASE WHEN SUM(answered_calls) > 0 
                 THEN ROUND(SUM(total_duration_sec)::numeric / SUM(answered_calls)::numeric, 2)
                 ELSE 0 END AS avg_duration_sec
        FROM cdr_metrics_day
        WHERE (%(customer_id)s IS NULL OR %(customer_id)s = '' OR %(customer_id)s = 'all' OR customer_id = %(customer_id)s) 
          AND bucket_day >= %(start_date)s 
          AND bucket_day <= %(end_date)s
    ),
    daily_trend AS (
        SELECT 
            json_agg(
                json_build_object(
                    'bucket_day', bucket_day,
                    'direction', direction,
                    'total_calls', total_calls
                )
            ) AS items
        FROM cdr_metrics_day
        WHERE (%(customer_id)s IS NULL OR %(customer_id)s = '' OR %(customer_id)s = 'all' OR customer_id = %(customer_id)s) 
          AND bucket_day >= %(start_date)s 
          AND bucket_day <= %(end_date)s
    ),
    top_dids AS (
        SELECT 
            json_agg(
                json_build_object(
                    'did_value', did_value,
                    'inbound_calls', sum_inbound
                )
            ) AS items
        FROM (
            SELECT did_value, SUM(inbound_calls) as sum_inbound
            FROM cdr_metrics_did_day
            WHERE (%(customer_id)s IS NULL OR %(customer_id)s = '' OR %(customer_id)s = 'all' OR customer_id = %(customer_id)s) 
              AND bucket_day >= %(start_date)s 
              AND bucket_day <= %(end_date)s
            GROUP BY did_value
            ORDER BY sum_inbound DESC
            LIMIT 10
        ) sub
    ),
    hod_dist AS (
        SELECT 
            json_agg(
                json_build_object(
                    'hour_of_day', hour_num,
                    'direction', direction,
                    'total_calls', total_calls
                )
            ) AS items
        FROM (
            SELECT 
                EXTRACT(HOUR FROM bucket_hour) as hour_num,
                direction,
                SUM(total_calls) as total_calls
            FROM cdr_metrics_hourly
            WHERE (%(customer_id)s IS NULL OR %(customer_id)s = '' OR %(customer_id)s = 'all' OR customer_id = %(customer_id)s)
              AND bucket_hour >= %(start_date)s::date 
              AND bucket_hour < (%(end_date)s::date + INTERVAL '1 day')
            GROUP BY hour_num, direction
            ORDER BY hour_num ASC
        ) sub
    )
    SELECT 
        (SELECT row_to_json(kpi.*) FROM kpi) AS kpi_cards,
        COALESCE((SELECT items FROM daily_trend), '[]'::json) AS daily_trend,
        COALESCE((SELECT items FROM top_dids), '[]'::json) AS top_dids,
        COALESCE((SELECT items FROM hod_dist), '[]'::json) AS hour_of_day_distribution;
    """
    
    conn = None
    try:
        conn = get_metrics_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, {
                'customer_id': customer_id,
                'start_date': start_date,
                'end_date': end_date
            })
            result = cursor.fetchone()
            
            kpi_cards = result.get('kpi_cards') or {}
            if 'avg_duration_sec' in kpi_cards:
                kpi_cards['avg_duration_display'] = format_duration(kpi_cards['avg_duration_sec'])
            
            # Formulating final JSON object
            payload = {
                "range": range,
                "customer_id": customer_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "kpi_cards": kpi_cards,
                "daily_trend": result.get('daily_trend') or [],
                "top_inbound_dids": result.get('top_dids') or [],
                "hour_of_day_distribution": result.get('hour_of_day_distribution') or []
            }
            
            return JSONResponse(content=payload)
    except Exception as e:
        logger.error(f"Error fetching dashboard data for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        if conn:
            conn.close()
