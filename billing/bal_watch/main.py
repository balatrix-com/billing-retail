import sys
import os
import traceback
import time
import os
import traceback

# Ensure the parent directory is in sys.path so we can import bal_watch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bal_watch.config import watch_config
from bal_watch.db import fetch_wallets
from bal_watch.processor import process_wallets
from bal_watch.printer import print_results
from bal_watch.publisher import publish_overlimit
from bal_watch.redis_manager import sync_blacklist_set
def main():
    print(f"Starting bal_watch... Scan interval: {watch_config.INTERVAL_SEC} seconds\n")
    try:
        while True:
            try:
                # fetch wallets from DB
                wallets = fetch_wallets()
                
                # process wallets
                results = process_wallets(wallets)
                
                # print results
                print_results(results)
                
                # Push overlimit data to Redis
                for wallet in results['overlimit_wallets']:
                    publish_overlimit(wallet)
                
                # Maintain live blacklist set in Redis
                sync_blacklist_set(results['overlimit_wallets'])
                
            except Exception as e:
                print(f"Error during scan cycle: {e}")
                traceback.print_exc()
                
            # sleep for configured interval
            time.sleep(watch_config.INTERVAL_SEC)
            
    except KeyboardInterrupt:
        print("\nStopping bal_watch...")
        sys.exit(0)

if __name__ == "__main__":
    main()
