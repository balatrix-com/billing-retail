import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class TeardownService:
    """
    Automated Hard Service Stop & Teardown Pipeline Enforcer.
    Invoked when tenant available purchasing power reaches $0.00.
    """

    def __init__(self, db_connection=None, redis_client=None):
        self.db = db_connection
        self.redis = redis_client

    def enforce_hard_stop(self, customer_id: str, available_purchasing_power: float = 0.0):
        """
        Enforce immediate multi-layer service stop for customer.
        1. Set status in database to SUSPENDED.
        2. Set Redis routing key tenant:{customer_id}:status = "SUSPENDED".
        3. Publish event on Redis channel tenant:suspended.
        """
        logger.warning(
            f"[HardStopEnforcer] Enforcing HARD SERVICE STOP for customer {customer_id}. "
            f"Available Purchasing Power: ${available_purchasing_power:.4f}"
        )

        # 1. Update Database
        if self.db:
            try:
                cursor = self.db.cursor()
                cursor.execute(
                    """
                    UPDATE subscriptions
                    SET status = 'suspended', updated_at = NOW()
                    WHERE customer_id = %s AND status = 'active';
                    """,
                    (customer_id,)
                )
                self.db.commit()
                cursor.close()
                logger.info(f"[HardStopEnforcer] DB subscription status set to SUSPENDED for {customer_id}")
            except Exception as e:
                logger.error(f"[HardStopEnforcer] Failed to update DB status for {customer_id}: {e}")

        # 2. Publish Redis Suspension Event
        if self.redis:
            try:
                event_payload = json.dumps({
                    'customer_id': customer_id,
                    'status': 'SUSPENDED',
                    'reason': 'ZERO_PURCHASING_POWER',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                self.redis.set(f"tenant:{customer_id}:status", "SUSPENDED")
                self.redis.publish("tenant:suspended", event_payload)
                logger.info(f"[HardStopEnforcer] Published Redis suspension event for {customer_id}")
            except Exception as e:
                logger.error(f"[HardStopEnforcer] Failed to publish Redis event for {customer_id}: {e}")

    def restore_service(self, customer_id: str, available_purchasing_power: float):
        """
        Restore service when wallet top-up brings purchasing power > $0.00.
        """
        logger.info(
            f"[HardStopEnforcer] Restoring service for customer {customer_id}. "
            f"Available Purchasing Power: ${available_purchasing_power:.4f}"
        )

        if self.redis:
            try:
                event_payload = json.dumps({
                    'customer_id': customer_id,
                    'status': 'ACTIVE',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                self.redis.set(f"tenant:{customer_id}:status", "ACTIVE")
                self.redis.publish("tenant:restored", event_payload)
                logger.info(f"[HardStopEnforcer] Published Redis restoration event for {customer_id}")
            except Exception as e:
                logger.error(f"[HardStopEnforcer] Failed to publish Redis restoration event for {customer_id}: {e}")
