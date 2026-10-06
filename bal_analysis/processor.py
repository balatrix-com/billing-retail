from datetime import datetime
import logging
from db import (
    upsert_cdr_metrics_day, 
    upsert_cdr_metrics_hourly, 
    upsert_cdr_metrics_did_day, 
    upsert_cdr_metrics_hour_of_day
)

logger = logging.getLogger(__name__)

def process_cdr_analytics(cdrs, dict_cursor):
    """
    Main aggregation logic for pure PostgreSQL approach.
    Iterates through a batch of CDR records, aggregates them in Python dictionaries,
    then performs bulk upserts to PostgreSQL aggregate tables.
    """
    if not cdrs:
        return

    # In-memory dictionaries to hold the aggregated increments for this batch
    daily_aggs = {}
    hourly_aggs = {}
    did_day_aggs = {}
    hod_aggs = {}

    for cdr in cdrs:
        try:
            customer_id = cdr.get('customer_id')
            if not customer_id:
                continue

            billsec = cdr.get('billsec', 0)
            duration = int(cdr.get('duration_sec', 0))
            direction = cdr.get('direction', 'unknown').lower()
            callee = cdr.get('callee')

            start_time = cdr.get('start_time')
            if isinstance(start_time, str):
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                dt = start_time

            bucket_day = dt.date()
            bucket_hour = dt.replace(minute=0, second=0, microsecond=0)
            hour_of_day = dt.hour

            # Use call_status to determine if a call was answered.
            # This is more reliable than billsec > 0, especially for simulation/test data.
            status = (cdr.get('call_status') or '').lower()
            is_answered = 1 if status == 'answered' else 0
            is_missed = 1 if status != 'answered' else 0

            # 1. Day aggregation
            day_key = (customer_id, bucket_day, direction)
            if day_key not in daily_aggs:
                daily_aggs[day_key] = {'total_calls': 0, 'answered_calls': 0, 'missed_calls': 0, 'total_duration_sec': 0, 'total_billsec': 0}
            daily_aggs[day_key]['total_calls'] += 1
            daily_aggs[day_key]['answered_calls'] += is_answered
            daily_aggs[day_key]['missed_calls'] += is_missed
            if is_answered:
                daily_aggs[day_key]['total_duration_sec'] += duration
                daily_aggs[day_key]['total_billsec'] += billsec
 
            # 2. Hourly aggregation
            hour_key = (customer_id, bucket_hour, direction)
            if hour_key not in hourly_aggs:
                hourly_aggs[hour_key] = {'total_calls': 0, 'answered_calls': 0, 'missed_calls': 0, 'total_duration_sec': 0}
            hourly_aggs[hour_key]['total_calls'] += 1
            hourly_aggs[hour_key]['answered_calls'] += is_answered
            hourly_aggs[hour_key]['missed_calls'] += is_missed
            if is_answered:
                hourly_aggs[hour_key]['total_duration_sec'] += duration

            # 3. DID Day aggregation
            if callee and direction == 'inbound':
                did_key = (customer_id, bucket_day, callee)
                if did_key not in did_day_aggs:
                    did_day_aggs[did_key] = {'inbound_calls': 0, 'answered_calls': 0, 'missed_calls': 0}
                did_day_aggs[did_key]['inbound_calls'] += 1
                did_day_aggs[did_key]['answered_calls'] += is_answered
                did_day_aggs[did_key]['missed_calls'] += is_missed

            # 4. Hour of Day aggregation
            hod_key = (customer_id, hour_of_day, direction)
            if hod_key not in hod_aggs:
                hod_aggs[hod_key] = {'total_calls': 0}
            hod_aggs[hod_key]['total_calls'] += 1

        except Exception as e:
            logger.error(f"Error processing CDR {cdr.get('cdr_id')}: {e}")
            continue

    # Convert to tuples and execute upserts if data exists
    if daily_aggs:
        daily_records = [
            (k[0], k[1], k[2], v['total_calls'], v['answered_calls'], v['missed_calls'], v['total_duration_sec'], v['total_billsec'])
            for k, v in daily_aggs.items()
        ]
        upsert_cdr_metrics_day(dict_cursor, daily_records)

    if hourly_aggs:
        hourly_records = [
            (k[0], k[1], k[2], v['total_calls'], v['answered_calls'], v['missed_calls'], v['total_duration_sec'])
            for k, v in hourly_aggs.items()
        ]
        upsert_cdr_metrics_hourly(dict_cursor, hourly_records)

    if did_day_aggs:
        did_records = [
            (k[0], k[1], k[2], v['inbound_calls'], v['answered_calls'], v['missed_calls'])
            for k, v in did_day_aggs.items()
        ]
        upsert_cdr_metrics_did_day(dict_cursor, did_records)

    if hod_aggs:
        hod_records = [
            (k[0], k[1], k[2], v['total_calls'])
            for k, v in hod_aggs.items()
        ]
        upsert_cdr_metrics_hour_of_day(dict_cursor, hod_records)
