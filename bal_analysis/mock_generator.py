import random
import uuid
from datetime import datetime, timedelta
import json

def generate_mock_cdr(cdr_id, customer_id=None):
    """
    Generates a single fake CDR record for testing and development.
    Includes random dates, durations, and costs within realistic ranges.
    """
    start_time = datetime.now() - timedelta(minutes=random.randint(1, 1000))
    duration = random.randint(0, 3600)
    billsec = max(0, duration - random.randint(0, 10)) if random.random() > 0.1 else 0
    
    return {
        "cdr_id": cdr_id,
        "call_uuid": str(uuid.uuid4()),
        "customer_id": customer_id or f"CUST_{random.randint(1, 5)}",
        "caller": f"+1{random.randint(1000000000, 9999999999)}",
        "callee": f"+1{random.randint(1000000000, 9999999999)}",
        "direction": random.choice(['inbound', 'outbound']),
        "start_time": start_time,
        "end_time": start_time + timedelta(seconds=duration),
        "duration_sec": duration,
        "billsec": billsec,
        "billed_amount": round(random.uniform(0.01, 5.0), 4),
        "currency": "USD",
        "dest_type": random.choice(["pstn", "extension", "sip"]),
        "dest_value": f"sip:{random.randint(1000, 9999)}@example.com",
        "status_code": random.choice(["200 OK", "404 Not Found", "486 Busy Here"]),
        "call_status": random.choice(["answered", "no_answer", "busy", "failed"])
    }

if __name__ == "__main__":
    # This script can be expanded to actually insert into DB for full integration test
    print("Mock CDR generator loaded.")
    sample = generate_mock_cdr(1)
    print(json.dumps(sample, indent=2, default=str))
