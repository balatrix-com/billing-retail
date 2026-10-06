import psycopg
import sys
sys.path.insert(0, '.')
from src.config import config

def inspect_db():
    conn = psycopg.connect(host=config.DB_HOST, dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD)
    cur = conn.cursor()
    
    print("--- Tables ---")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    for row in cur.fetchall():
        print(row[0])
        
    print("\n--- customer_ratecard sample ---")
    try:
        cur.execute("SELECT * FROM customer_ratecard LIMIT 5")
        for row in cur.fetchall():
            print(row)
    except:
        print("Table customer_ratecard not found or error.")
        
    print("\n--- rate_cards sample ---")
    try:
        cur.execute("SELECT * FROM rate_cards LIMIT 5")
        for row in cur.fetchall():
            print(row)
    except:
        print("Table rate_cards not found or error.")
        
    conn.close()

if __name__ == "__main__":
    inspect_db()
