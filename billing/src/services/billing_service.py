from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
import hashlib
import math
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class BillingService:
    """
    Core billing calculation engine.
    Handles rate lookup, increment calculation, free seconds deduction, and transaction prep.
    """
    
    def generate_idempotency_key(self, call_uuid: str) -> str:
        """
        Generate SHA256 hash for idempotency.
        Based on call_uuid to prevent duplicate charges.
        """
        data = f"cdr-{call_uuid}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def get_rate_card(self, customer_id: str, customer_ratecards: Dict, rate_cards: Dict) -> Optional[Dict]:
        """
        Lookup rate card for customer.
        
        Args:
            customer_id: Customer identifier
            customer_ratecards: {customer_id → {ratecard_id, ...}}
            rate_cards: {ratecard_id → rate card details}
        
        Returns:
            Rate card dict or None if not found
        """
        if customer_id not in customer_ratecards:
            logger.warning(f"Customer {customer_id} not in ratecard mapping")
            return None
        
        ratecard_id = customer_ratecards[customer_id]['ratecard_id']
        
        if ratecard_id not in rate_cards:
            logger.warning(f"Ratecard {ratecard_id} not in rate cards cache")
            return None
            
        rc = rate_cards[ratecard_id]
        if rc.get('in_rate_per_sec') is None or rc.get('ob_rate_per_sec') is None:
            logger.error(
                f"Ratecard {ratecard_id} has NULL per-second rates. "
                f"Run: UPDATE rate_cards SET in_rate_per_sec=in_rate_per_min/60.0, "
                f"ob_rate_per_sec=ob_rate_per_min/60.0 WHERE ratecard_id={ratecard_id}; "
                f"Then refresh cache."
            )
            return None
            
        return rc
    
    def calculate_billable_seconds(
        self,
        duration_sec: int,
        initial_increment_sec: int,
        increment_sec: int
    ) -> int:
        """
        Calculate billable seconds with increment logic.
        
        Formula:
        - If duration <= initial_increment: bill for initial_increment
        - Else: bill for initial + ceil((duration - initial) / increment) * increment
        
        Args:
            duration_sec: Actual call duration in seconds
            initial_increment_sec: First billing pulse (e.g., 60s minimum)
            increment_sec: Subsequent billing pulses (e.g., 60s blocks)
        
        Returns:
            Billable seconds after applying increments
        """
        if duration_sec <= 0:
            return 0
            
        if duration_sec <= initial_increment_sec:
            return initial_increment_sec
        
        remaining = duration_sec - initial_increment_sec
        increments_needed = math.ceil(remaining / increment_sec)
        billable_sec = initial_increment_sec + (increments_needed * increment_sec)
        
        return billable_sec
    
    def calculate_billing(
        self,
        cdr: Dict,
        rate_cards: Dict,
        customer_ratecards: Dict,
        rec_rate_cards: Dict,
        customer_rec_rc: Dict,
        wallet: Optional[Dict],
        batch_timestamp: datetime
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Calculate complete billing for a single CDR.
        
        Process:
        1. Get rate card for customer
        2. Select rate by direction (inbound/outbound)
        3. Calculate billable seconds (apply increments)
        4. Deduct free seconds first
        5. Calculate fiat charge for remaining seconds
        6. Prepare transaction and CDR update records
        
        Args:
            cdr: CDR record {cdr_id, call_uuid, customer_id, direction, duration_sec, ...}
            rate_cards: {ratecard_id → {in_rate_per_sec, ob_rate_per_sec, ...}}
            customer_ratecards: {customer_id → {ratecard_id, ...}}
            wallet: {fiat_balance, free_seconds, ...}
            batch_timestamp: Timestamp for this batch
        
        Returns:
            (transaction_dict, cdr_update_dict) or (None, None) if error
        """
        try:
            direction = str(cdr.get('direction', '')).strip().lower()
            cdr_currency = cdr.get('currency') or 'USD'

            # INTERNAL calls are rated with zero charge (no wallet debit).
            if direction == 'internal':
                idempotency_key = self.generate_idempotency_key(cdr['call_uuid'])
                transaction = {
                    'customer_id': cdr['customer_id'],
                    'source_type': 'cdr',
                    'source_ref': str(cdr['cdr_id']),
                    'idempotency_key': idempotency_key,
                    'currency': cdr_currency,
                    'free_used_sec': 0,
                    'wallet_debit_amount': Decimal('0'),
                    'amount_total': wallet['fiat_balance'] if wallet else Decimal('0'),
                    'ratecard_id': None,
                    'rate_per_min': Decimal('0'),
                    'billing_increment_sec': 0,
                    'status': 'posted',
                    'notes': f"Internal call (no charge): {cdr['call_uuid']}",
                    'created_at': batch_timestamp,
                    'wallet_update_required': False,
                    'recording_amount': Decimal('0'),
                    'rec_ratecard_id': None
                }
                cdr_update = {
                    'cdr_id': cdr['cdr_id'],
                    'billsec': cdr.get('billsec', 0) or 0,
                    'currency': cdr_currency,
                    'ratecard_id': None,
                    'billed_amount': Decimal('0'),
                    'recording_amount': Decimal('0'),
                    'total_amount': Decimal('0'),
                    'recording_days': 0,
                    'is_rated': True,
                    'rated_at': batch_timestamp
                }
                return transaction, cdr_update

            if wallet is None:
                logger.warning(f"Skipping CDR {cdr['cdr_id']}: no wallet found for {cdr['customer_id']}")
                return None, None

            # STEP 1: Get rate card
            ratecard = self.get_rate_card(cdr['customer_id'], customer_ratecards, rate_cards)
            if not ratecard:
                logger.warning(f"Skipping CDR {cdr['cdr_id']}: no rate card found")
                return None, None
            
            # STEP 2: Select rate based on direction
            if direction == 'inbound':
                rate_per_sec = Decimal(str(ratecard['in_rate_per_sec']))
                rate_per_min = Decimal(str(ratecard['in_rate_per_min']))
                initial_increment = ratecard['in_initial_increment_sec']
                increment = ratecard['in_increment_sec']
            elif direction == 'outbound':
                rate_per_sec = Decimal(str(ratecard['ob_rate_per_sec']))
                rate_per_min = Decimal(str(ratecard['ob_rate_per_min']))
                initial_increment = ratecard['ob_initial_increment_sec']
                increment = ratecard['ob_increment_sec']
            else:
                logger.error(f"Invalid direction {cdr['direction']} for CDR {cdr['cdr_id']}")
                return None, None
            
            # STEP 3: Calculate billable seconds from source billsec (not duration_sec)
            # For answered calls, billsec can be 0 due to SIP race conditions — fall back to duration_sec
            source_billsec = int(cdr.get('billsec', 0) or 0)
            if source_billsec == 0:
                source_billsec = int(cdr.get('duration_sec', 0) or 0)
            billable_sec = self.calculate_billable_seconds(
                source_billsec,
                initial_increment,
                increment
            )
            
            # STEP 4: Deduct free seconds first
            free_used_sec = min(wallet['free_seconds'], billable_sec)
            wallet['free_seconds'] -= free_used_sec
            remaining_sec = billable_sec - free_used_sec
            
            # STEP 5: Calculate fiat charge
            if remaining_sec > 0:
                fiat_charge = Decimal(remaining_sec) * rate_per_sec
            else:
                fiat_charge = Decimal('0')
            
            # --- RECORDING BILLING LOGIC ---
            recording_amount = Decimal('0')
            rec_ratecard_id = None
            recording_days = 0
            
            rec_val = cdr.get('recording')
            if isinstance(rec_val, (bytes, bytearray, memoryview)):
                try:
                    rec_val = bytes(rec_val).decode('utf-8')
                except Exception:
                    rec_val = str(rec_val)
            
            rec_val_str = str(rec_val).strip().lower() if rec_val is not None else ''
            is_recording = rec_val is True or rec_val_str in ('true', 't', '1', 'yes')
            
            if is_recording:
                cust_id_str = str(cdr['customer_id'])
                rec_rc_mapping = customer_rec_rc.get(cust_id_str)
                if rec_rc_mapping:
                    rec_ratecard_id = rec_rc_mapping['rec_rc_id']
                    rec_ratecard = rec_rate_cards.get(str(rec_ratecard_id))
                    
                    if rec_ratecard:
                        duration_sec = int(cdr.get('duration_sec', 0) or 0)
                        rec_increment = int(rec_ratecard.get('billing_increments') or 60)
                        
                        rec_billable_sec = self.calculate_billable_seconds(
                            duration_sec,
                            rec_increment,
                            rec_increment
                        )
                        
                        rec_rate_per_sec = Decimal(str(rec_ratecard['rate_per_sec']))
                        recording_amount = Decimal(rec_billable_sec) * rec_rate_per_sec
                        recording_days = int(rec_ratecard.get('retention_period', 0) or 0)
                        logger.info(
                            f"[RecordingBilling] CDR {cdr.get('cdr_id')} customer {cust_id_str}: "
                            f"recording=true, duration_sec={duration_sec}s, rec_billable_sec={rec_billable_sec}s, "
                            f"rate_per_sec={rec_rate_per_sec}, recording_amount=${recording_amount}"
                        )
                    else:
                        logger.warning(f"[RecordingBilling] Rec ratecard {rec_ratecard_id} not in cache")
                else:
                    logger.warning(f"[RecordingBilling] Customer {cust_id_str} not in customer_rec_rc cache")
            
            # Total amount to deduct includes normal call charge + recording cost
            total_amount = fiat_charge + recording_amount
            
            # Multi-Tier Debit Logic for total_amount (fiat_balance -> credit_used)
            fiat = Decimal(str(wallet.get('fiat_balance', 0) or 0))
            credit_limit = Decimal(str(wallet.get('credit_limit', 0) or 0))
            credit_used = Decimal(str(wallet.get('credit_used', 0) or 0))

            if fiat >= total_amount:
                wallet['fiat_balance'] = fiat - total_amount
                wallet['credit_used'] = credit_used
            else:
                remaining_charge = total_amount - fiat
                wallet['fiat_balance'] = Decimal('0')
                wallet['credit_used'] = credit_used + remaining_charge

            # Store total available purchasing power in wallet
            available_power = wallet['fiat_balance'] + max(Decimal('0'), credit_limit - wallet['credit_used'])
            wallet['available_purchasing_power'] = available_power
            wallet['hard_stop_triggered'] = available_power <= Decimal('0')
            
            # Show the full value of the call in the CDR
            billed_sec = billable_sec
            
            # The charged amount to the user (fiat_charge) - if covered by free seconds, this is 0
            billed_amount = fiat_charge

            # Store wallet balance after this charge in amount_total for audit visibility
            wallet_balance_after = wallet['fiat_balance']
            
            currency = wallet.get('currency') or cdr.get('currency') or 'USD'
            
            # STEP 6: Prepare transaction record
            idempotency_key = self.generate_idempotency_key(cdr['call_uuid'])
            
            transaction = {
                'customer_id': cdr['customer_id'],
                'source_type': 'cdr',
                'source_ref': str(cdr['cdr_id']),
                'idempotency_key': idempotency_key,
                'currency': currency,
                'free_used_sec': free_used_sec,
                'wallet_debit_amount': total_amount,
                'amount_total': wallet_balance_after,
                'ratecard_id': ratecard['ratecard_id'],
                'rate_per_min': rate_per_min,
                'billing_increment_sec': increment,
                'status': 'posted',
                'notes': f"Call billing: {cdr['call_uuid']}",
                'created_at': batch_timestamp,
                'wallet_update_required': True,
                'recording_amount': recording_amount,
                'rec_ratecard_id': rec_ratecard_id
            }
            
            # STEP 7: Prepare CDR update
            cdr_update = {
                'cdr_id': cdr['cdr_id'],
                'billsec': billed_sec,
                'currency': currency,
                'ratecard_id': ratecard['ratecard_id'],
                'billed_amount': billed_amount,
                'recording_amount': recording_amount,
                'total_amount': total_amount,
                'recording_days': recording_days,
                'is_rated': True,
                'rated_at': batch_timestamp
                # transaction_id will be added after bulk insert
            }
            
            logger.debug(
                f"CDR {cdr['cdr_id']} ({cdr.get('dest_type')}:{cdr.get('dest_value')} | Status: {cdr.get('status_code')}): "
                f"{cdr['direction']} {cdr['duration_sec']}s → "
                f"bill {billable_sec}s, free {free_used_sec}s, charge ${fiat_charge}"
            )
            
            return transaction, cdr_update
            
        except Exception as e:
            logger.error(f"Error calculating billing for CDR {cdr['cdr_id']}: {e}", exc_info=True)
            return None, None
