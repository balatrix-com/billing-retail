"""Compatibility shim: wallet exhaustion controls recording, not paid subscriptions.

The subscription lifecycle worker in sub-billing-retail is the sole authority
for expiry, grace, freeze and reactivation. Retain the old class/method names
for integrations, but never overwrite independently paid subscription states.
"""
import logging
import os

logger = logging.getLogger(__name__)


class TeardownService:
    def __init__(self, db_connection=None, redis_client=None):
        self.db = db_connection  # Compatibility only; no subscription DB mutations.
        self.redis = redis_client
        self.recording_key = os.getenv(
            'RECORDING_OVERLIMIT_SET_KEY', 'blacklist:customers:recording_overlimit'
        )

    def enforce_hard_stop(self, customer_id: str, available_purchasing_power: float = 0.0):
        if available_purchasing_power > 0:
            return self.restore_service(customer_id, available_purchasing_power)
        if self.redis:
            self.redis.sadd(self.recording_key, customer_id)
        logger.warning('Wallet recording gate enabled for %s; paid subscriptions remain unchanged', customer_id)

    def restore_service(self, customer_id: str, available_purchasing_power: float):
        if available_purchasing_power <= 0:
            return self.enforce_hard_stop(customer_id, available_purchasing_power)
        if self.redis:
            self.redis.srem(self.recording_key, customer_id)
        logger.info('Wallet recording gate cleared for %s; subscription renewal is managed by sub-billing', customer_id)
