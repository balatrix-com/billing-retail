from datetime import datetime
from redis_client import redis_client
from processor import process_cdr_analytics
import json

def verify_windowed():
    print("--- Starting Windowed Analytics Verification ---")
    
    # 1. Create a mock CDR for RIGHT NOW
    now = datetime.now()
    mock_cdr = {
        "cdr_id": 999999,
        "start_time": now.isoformat(),
        "billsec": 60,
        "duration_sec": 60,
        "billed_amount": 1.50,
        "direction": "inbound",
        "callee": "1234567890",
        "customer_id": "test_cust"
    }

    print(f"Processing mock CDR at {now}")
    process_cdr_analytics([mock_cdr], redis_client)

    # 2. Check Redis for the expected window keys
    date_str = now.strftime('%Y-%m-%d')
    hour = now.hour
    minute_30 = "00" if now.minute < 30 else "30"
    even_hour = (hour // 2) * 2

    keys_to_check = {
        "Day": f"analytics:window:day:{date_str}",
        "Hour": f"analytics:window:hour:{date_str}:{hour:02d}",
        "30Min": f"analytics:window:30min:{date_str}:{hour:02d}:{minute_30}",
        "2Hour": f"analytics:window:2hour:{date_str}:{even_hour:02d}"
    }

    print("\nChecking Redis keys:")
    all_passed = True
    for label, key in keys_to_check.items():
        # Global Check
        global_data = redis_client.get_windowed_metrics(key)
        print(f"[{label}] Global Key: {key}")
        print(f"      Data: {global_data}")
        
        if global_data['total_calls'] >= 1:
            print(f"      ✅ PASSED: Global metric found")
        else:
            print(f"      ❌ FAILED: No global metric found")
            all_passed = False

        # Customer Check
        suffix = key.split(':', 1)[1]
        cust_key = f"analytics:customer:test_cust:{suffix}"
        cust_data = redis_client.get_windowed_metrics(cust_key)
        print(f"[{label}] Customer Key: {cust_key}")
        print(f"      Data: {cust_data}")
        
        if cust_data['total_calls'] >= 1:
            print(f"      ✅ PASSED: Customer metric found")
        else:
            print(f"      ❌ FAILED: No customer metric found")
            all_passed = False

    if all_passed:
        print("\n--- ALL VERIFICATIONS PASSED ---")
    else:
        print("\n--- SOME VERIFICATIONS FAILED ---")

if __name__ == "__main__":
    verify_windowed()
