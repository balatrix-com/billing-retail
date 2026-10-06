from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from decimal import Decimal

@dataclass
class CDR:
    cdr_id: Optional[int]
    call_uuid: str
    customer_id: str
    caller: str
    callee: str
    last_destination: Optional[str]
    direction: str  # 'inbound' or 'outbound'
    start_time: datetime
    answer_time: Optional[datetime]
    end_time: datetime
    duration_sec: int
    billsec: int
    dest_type: Optional[str]
    dest_value: Optional[str]
    status_code: Optional[str]
    call_status: Optional[str]
    ingress_trunk: Optional[str]
    egress_trunk: Optional[str]
    route_id: Optional[str]
    gateway_id: Optional[str]
    currency: str  # 'USD' or 'CAD'
    ratecard_id: Optional[int]
    billed_amount: Decimal
    transaction_id: Optional[int]
    is_rated: bool
    rated_at: Optional[datetime]
    created_at: datetime
    
    @classmethod
    def from_db_row(cls, row: dict):
        """Create CDR instance from database row"""
        return cls(**row)