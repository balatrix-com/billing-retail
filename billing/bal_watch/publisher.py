import json
from decimal import Decimal
from bal_watch.config import watch_config
from bal_watch.redis_manager import get_redis_client
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def publish_overlimit(wallet_data):
    """
    Pushes overlimit wallet data to Redis list using the centralized manager.
    """
    client = get_redis_client()
    if not client:
        logger.error("Redis client not available. Cannot publish event.")
        return False

    try:
        payload = {
            "event_type": "wallet.overlimit",
            "data": wallet_data
        }
        
        message = json.dumps(payload, default=_decimal_default)
        client.rpush(watch_config.REDIS_KEY, message)
        
        logger.info(f"Published overlimit event for customer {wallet_data['customer_id']} to Redis")
        return True
    except Exception as e:
        logger.error(f"Error publishing to Redis: {e}")
        return False

def publish_event(event_type, wallet):
    """Legacy dispatcher"""
    if event_type == "wallet.overlimit":
        return publish_overlimit(wallet)
    return False
