import redis
from bal_watch.config import watch_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class RedisManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
            cls._instance.client = cls._instance._create_client()
        return cls._instance

    def _create_client(self):
        """Initialize and return a Redis client instance."""
        try:
            client = redis.StrictRedis(
                host=watch_config.REDIS_HOST,
                port=watch_config.REDIS_PORT,
                password=watch_config.REDIS_PASSWORD,
                db=watch_config.REDIS_DB,
                decode_responses=True,
                socket_timeout=5
            )
            # Test connection
            client.ping()
            logger.info(f"Connected to Redis at {watch_config.REDIS_HOST}:{watch_config.REDIS_PORT}")
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return None

    def get_client(self):
        """Public accessor for the Redis client."""
        return self.client

def get_redis_client():
    """Helper function to get the singleton Redis client."""
    return RedisManager().get_client()

def sync_blacklist_set(overlimit_wallets):
    """
    Maintains a 'live' set of over-limit customers.
    Logic: DELETE the key, then SADD current IDs.
    """
    client = get_redis_client()
    if not client:
        logger.error("Redis client not available. Cannot sync blacklist set.")
        return False

    set_key = "blacklist:customers:overlimit"
    try:
        # Extract unique customer IDs
        customer_ids = list(set([w['customer_id'] for w in overlimit_wallets]))
        
        # Use a pipeline for atomicity
        pipe = client.pipeline()
        pipe.delete(set_key)
        if customer_ids:
            pipe.sadd(set_key, *customer_ids)
        pipe.execute()
        
        logger.info(f"Synchronized {len(customer_ids)} customers to Redis set '{set_key}'")
        return True
    except Exception as e:
        logger.error(f"Error syncing Redis set '{set_key}': {e}")
        return False

def check_blacklist():
    """
    Main logic requested: fetches and prints members of the 
    blacklist:customers:overlimit set.
    """
    client = get_redis_client()
    if not client:
        print("Error: Could not connect to Redis.")
        return

    set_key = "blacklist:customers:overlimit"
    try:
        members = client.smembers(set_key)
        print(f"\n--- Blacklisted Customers ({set_key}) ---")
        if members:
            for member in members:
                print(f" - {member}")
        else:
            print("No blacklisted customers found in this set.")
        print("-" * 40 + "\n")
    except Exception as e:
        logger.error(f"Error fetching members from {set_key}: {e}")

if __name__ == "__main__":
    # When run directly, this performs the blacklist check as requested.
    check_blacklist()
