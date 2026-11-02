import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    DB_HOST = os.getenv('DB_HOST', '10.30.0.60')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'bala_billing')
    DB_USER = os.getenv('DB_USER', 'bill_eng1')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    # DB connection retry/backoff
    DB_CONNECT_RETRIES = int(os.getenv('DB_CONNECT_RETRIES', '3'))
    DB_CONNECT_BACKOFF_SEC = int(os.getenv('DB_CONNECT_BACKOFF_SEC', '2'))
    DB_CONNECT_TIMEOUT_SEC = int(os.getenv('DB_CONNECT_TIMEOUT_SEC', '10'))
    
    # Application
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    BILLING_BATCH_SIZE = int(os.getenv('BILLING_BATCH_SIZE', '100'))
    PROCESSING_INTERVAL_SEC = int(os.getenv('PROCESSING_INTERVAL_SEC', '60'))
    REFRESH_CACHE_TOKEN = os.getenv('REFRESH_CACHE_TOKEN', '')
    BILLING_API_HOST = os.getenv('BILLING_API_HOST', '127.0.0.1')
    BILLING_API_PORT = int(os.getenv('BILLING_API_PORT', '8005'))

    # Shared recording gate (same Redis DB used by t_2002.py)
    REDIS_HOST = os.getenv('LOOKUP_REDIS_HOST', os.getenv('REDIS_HOST', '127.0.0.1'))
    REDIS_PORT = int(os.getenv('LOOKUP_REDIS_PORT', os.getenv('REDIS_PORT', '6379')))
    REDIS_DB = int(os.getenv('LOOKUP_REDIS_DB', os.getenv('REDIS_DB', '2')))
    REDIS_PASSWORD = os.getenv('LOOKUP_REDIS_PASSWORD', os.getenv('REDIS_PASSWORD', ''))
    RECORDING_OVERLIMIT_SET_KEY = os.getenv(
        'RECORDING_OVERLIMIT_SET_KEY',
        'blacklist:customers:recording_overlimit'
    )
    
    @property
    def database_url(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

config = Config()
