from uuid import UUID
from decimal import Decimal
from typing import Optional
from sqlmodel import SQLModel
from .models import FeeType, FeeStatus


# ── FeeRule schemas ──────────────────────────────────────────────────────────

class FeeRuleCreate(SQLModel):
    name: str
    description: Optional[str] = None
    fee_type: FeeType
    flat_amount: Decimal = Decimal("0.00")
    percentage_rate: Decimal = Decimal("0.00")
    min_fee: Optional[Decimal] = None
    max_fee: Optional[Decimal] = None


class FeeRuleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    flat_amount: Optional[Decimal] = None
    percentage_rate: Optional[Decimal] = None
    min_fee: Optional[Decimal] = None
    max_fee: Optional[Decimal] = None
    is_active: Optional[bool] = None


class FeeRuleResponse(SQLModel):
    id: UUID
    name: str
    description: Optional[str]
    fee_type: FeeType
    flat_amount: Decimal
    percentage_rate: Decimal
    min_fee: Optional[Decimal]
    max_fee: Optional[Decimal]
    is_active: bool

    class Config:
        from_attributes = True


# ── TransactionFee schemas ───────────────────────────────────────────────────

class TransactionFeeResponse(SQLModel):
    id: UUID
    transaction_id: UUID
    fee_rule_id: UUID
    user_id: UUID
    fee_type: FeeType
    transaction_amount: Decimal
    flat_amount: Decimal
    percentage_rate: Decimal
    computed_fee: Decimal
    status: FeeStatus
    waived_reason: Optional[str]

    class Config:
        from_attributes = True


class WaiveFeeRequest(SQLModel):
    reason: str