#!/usr/bin/env python3
"""
Refresh both recording rate cards and customer recording ratecard caches.
Run this script manually whenever recording rate cards or customer assignments change.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "src" / "cache"
REC_RATE_CARDS_CACHE = CACHE_DIR / "rec_rate_cards.json"
CUSTOMER_REC_RC_CACHE = CACHE_DIR / "customer_rec_rc.json"

def round_to_decimals(value, decimals=10):
    if value is None:
        return None
    return round(float(value), decimals)

def to_string(value):
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return value

def load_rec_rate_cards_from_db():
    query = """
        SELECT 
            id,
            name,
            currency,
            rate_per_min,
            retention_period,
            billing_increments
        FROM rec_rate_card
        ORDER BY id
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    
    rec_rate_cards = []
    for row in rows:
        rate_per_min = float(row['rate_per_min'])
        rate_per_sec = round_to_decimals(rate_per_min / 60, 10)
        
        # Ensure billing_increments defaults to 60 if null
        billing_increments = row['billing_increments']
        if billing_increments is None:
            billing_increments = 60
            
        rec_rate_cards.append({
            'id': row['id'],
            'name': to_string(row['name']),
            'currency': to_string(row['currency']),
            'rate_per_min': round_to_decimals(rate_per_min, 10),
            'rate_per_sec': rate_per_sec,
            'retention_period': row['retention_period'],
            'billing_increments': billing_increments
        })
    
    return rec_rate_cards

def load_customer_rec_rc_from_db():
    query = """
        SELECT 
            cust_id,
            rec_rc_id
        FROM customer_rec_rc
        ORDER BY cust_id
    """
    
    with db.get_cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    
    customer_rec_rc = []
    for row in rows:
        customer_rec_rc.append({
            'cust_id': to_string(row['cust_id']),
            'rec_rc_id': row['rec_rc_id']
        })
    
    return customer_rec_rc

def save_cache(cache_file, data_key, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    cache_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        data_key: data,
        'total': len(data)
    }
    
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
    
    logger.info(f"{data_key} cache saved ({len(data)} total)")

def run_refresh_record():
    try:
        logger.info("Refreshing recording caches...")
        
        rec_rate_cards = load_rec_rate_cards_from_db()
        save_cache(REC_RATE_CARDS_CACHE, 'rec_rate_cards', rec_rate_cards)
        
        customer_rec_rc = load_customer_rec_rc_from_db()
        save_cache(CUSTOMER_REC_RC_CACHE, 'customer_rec_rc', customer_rec_rc)
        
        return {
            "status": "success",
            "rec_rate_cards_count": len(rec_rate_cards),
            "customer_rec_rc_count": len(customer_rec_rc),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error refreshing recording caches: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

if __name__ == '__main__':
    print("\nRefreshing recording caches...\n")
    stats = run_refresh_record()
    
    if stats["status"] == "success":
        print(f"Recording cache refresh complete!")
        print(f"   • Rec Rate cards: {stats['rec_rate_cards_count']}")
        print(f"   • Customer mappings: {stats['customer_rec_rc_count']}")
        print(f"   • Cache location: {CACHE_DIR}\n")
    else:
        print(f"\nError: {stats['message']}")
        sys.exit(1)
