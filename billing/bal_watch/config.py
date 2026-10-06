import os
from dotenv import load_dotenv

# Import the main project's DB configuration directly
from src.config import config as db_config

# Load bal_watch specific environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "setting.env"))

class WatchConfig:
    INTERVAL_SEC = int(os.getenv('BAL_WATCH_INTERVAL_SEC', 100))
    LOW_BALANCE_THRESHOLD = float(os.getenv('BAL_WATCH_LOW_BALANCE_THRESHOLD', 100))
    
    # Redis configuration
    REDIS_HOST = os.getenv('REDIS_HOST', '10.30.0.2')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_KEY = os.getenv('REDIS_KEY', 'billing:overlimit:log')

watch_config = WatchConfig()
