from uuid import UUID
from decimal import Decimal
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from .models import FeeRule, FeeStatus, FeeType, TransactionFee
from .schema import FeeRuleCreate, FeeRuleUpdate
from .calculator import compute_fee


class FeeService:

    # ── FeeRule CRUD ─────────────────────────────────────────────────────────

    @staticmethod
    async def create_rule(data: FeeRuleCreate, session: AsyncSession) -> FeeRule:
        rule = FeeRule(**data.model_dump())
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    @staticmethod
    async def get_rule(rule_id: UUID, session: AsyncSession) -> FeeRule:
        rule = await session.get(FeeRule, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Fee rule not found.")
        return rule

    @staticmethod
    async def list_rules(session: AsyncSession, active_only: bool = True) -> list[FeeRule]:
        q = select(FeeRule)
        if active_only:
            q = q.where(FeeRule.is_active == True)
        result = await session.execute(q)
        return result.scalars().all()

    @staticmethod
    async def update_rule(rule_id: UUID, data: FeeRuleUpdate, session: AsyncSession) -> FeeRule:
        rule = await FeeService.get_rule(rule_id, session)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    # ── TransactionFee operations ────────────────────────────────────────────

    @staticmethod
    async def apply_fee(
        *,
        transaction_id: UUID,
        user_id: UUID,
        rule_id: UUID,
        transaction_amount: Decimal,
        session: AsyncSession,
    ) -> TransactionFee:
        """Compute and persist a fee for a transaction."""
        rule = await FeeService.get_rule(rule_id, session)

        if not rule.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fee rule '{rule.name}' is inactive.",
            )

        fee_amount = compute_fee(rule, transaction_amount)

        record = TransactionFee(
            transaction_id=transaction_id,
            fee_rule_id=rule.id,
            user_id=user_id,
            fee_type=rule.fee_type,
            transaction_amount=transaction_amount,
            flat_amount=rule.flat_amount,
            percentage_rate=rule.percentage_rate,
            computed_fee=fee_amount,
            status=FeeStatus.pending,
        )

        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def mark_applied(fee_id: UUID, session: AsyncSession) -> TransactionFee:
        fee = await session.get(TransactionFee, fee_id)
        if not fee:
            raise HTTPException(status_code=404, detail="Fee record not found.")
        fee.status = FeeStatus.applied
        session.add(fee)
        await session.commit()
        await session.refresh(fee)
        return fee

    @staticmethod
    async def waive_fee(fee_id: UUID, reason: str, session: AsyncSession) -> TransactionFee:
        fee = await session.get(TransactionFee, fee_id)
        if not fee:
            raise HTTPException(status_code=404, detail="Fee record not found.")
        if fee.status == FeeStatus.applied:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot waive an already-applied fee. Refund it instead.",
            )
        fee.status = FeeStatus.waived
        fee.waived_reason = reason
        session.add(fee)
        await session.commit()
        await session.refresh(fee)
        return fee

    @staticmethod
    async def get_fees_for_transaction(
        transaction_id: UUID, session: AsyncSession
    ) -> list[TransactionFee]:
        result = await session.execute(
            select(TransactionFee).where(
                TransactionFee.transaction_id == transaction_id
            )
        )
        return result.scalars().all()

    @staticmethod
    async def get_fees_for_user(user_id: UUID, session: AsyncSession) -> list[TransactionFee]:
        result = await session.execute(
            select(TransactionFee).where(TransactionFee.user_id == user_id)
        )
        return result.scalars().all()