from typing import Annotated, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.service import get_current_active_user, get_current_admin
from app.auth.model import User
from app.auth.role import Roles
from .models import FeeRule, TransactionFee
from .schema import (
    FeeRuleCreate, FeeRuleUpdate, FeeRuleResponse,
    TransactionFeeResponse, WaiveFeeRequest,
)
from .service import FeeService

router = APIRouter(prefix="/fees", tags=["Fees"])



# ── Fee Rules (admin) ────────────────────────────────────────────────────────

@router.post("/rules", response_model=FeeRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_fee_rule(
    data: FeeRuleCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
):
    return await FeeService.create_rule(data, session)


@router.get("/rules", response_model=List[FeeRuleResponse])
async def list_fee_rules(
    session: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = Query(True),
):
    return await FeeService.list_rules(session, active_only=active_only)


@router.get("/rules/{rule_id}", response_model=FeeRuleResponse)
async def get_fee_rule(
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await FeeService.get_rule(rule_id, session)


@router.patch("/rules/{rule_id}", response_model=FeeRuleResponse)
async def update_fee_rule(
    rule_id: UUID,
    data: FeeRuleUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
):
    return await FeeService.update_rule(rule_id, data, session)


# ── Transaction Fees ─────────────────────────────────────────────────────────

@router.get("/transaction/{transaction_id}", response_model=List[TransactionFeeResponse])
async def get_fees_for_transaction(
    transaction_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_active_user)],
):
    return await FeeService.get_fees_for_transaction(transaction_id, session)


@router.get("/me", response_model=List[TransactionFeeResponse])
async def my_fees(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await FeeService.get_fees_for_user(current_user.id, session)


@router.post("/{fee_id}/waive", response_model=TransactionFeeResponse)
async def waive_fee(
    fee_id: UUID,
    body: WaiveFeeRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
):
    return await FeeService.waive_fee(fee_id, body.reason, session)


@router.post("/{fee_id}/apply", response_model=TransactionFeeResponse)
async def apply_fee(
    fee_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_admin)],
):
    return await FeeService.mark_applied(fee_id, session)