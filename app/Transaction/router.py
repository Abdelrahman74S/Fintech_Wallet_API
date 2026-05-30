from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Optional
from uuid import UUID

from app.TransactionFee.service import FeeService
from app.database import get_db
from app.auth.service import get_current_active_user
from app.auth.model import User
from app.wallets.models import Wallet
from app.wallets.service import Money
from app.Transaction.models import (
    Transaction,
    TransactionType,
    TransactionStatus,
    TransactionCreate,
    TransactionResponse,
    DepositWithdrawRequest,
)

from app.kyc.models import KYCSubmission, DocStatus

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# router.state.limiter = limiter
# router.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@router.post("/transfer", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def transfer_money(
    request: Request,
    transfer_data: TransactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    
    if transfer_data.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Transfer amount must be greater than zero.")

    if transfer_data.wallet_id == transfer_data.counterparty_wallet_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same wallet.")
        
    kyc = await db.execute(select(KYCSubmission).where(KYCSubmission.user_id == current_user.id))
    kyc_submission = kyc.scalars().first()
    if not kyc_submission or kyc_submission.status != DocStatus.approved:
        raise HTTPException(status_code=403, detail="KYC verification is required and must be approved.")

    wallet_ids = sorted([transfer_data.wallet_id, transfer_data.counterparty_wallet_id])

    try:
        stmt_1 = select(Wallet).where(Wallet.id == wallet_ids[0]).with_for_update()
        stmt_2 = select(Wallet).where(Wallet.id == wallet_ids[1]).with_for_update()
        wallet_1 = (await db.execute(stmt_1)).scalars().first()
        wallet_2 = (await db.execute(stmt_2)).scalars().first()

        if not wallet_1 or not wallet_2:
            raise HTTPException(status_code=404, detail="One or both wallets were not found.")

        source_wallet = wallet_1 if wallet_1.id == transfer_data.wallet_id else wallet_2
        destination_wallet = wallet_2 if wallet_1.id == transfer_data.wallet_id else wallet_1

        if source_wallet.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not own the source wallet.")
        if not source_wallet.is_active or not destination_wallet.is_active:
            raise HTTPException(status_code=400, detail="One of the wallets is inactive.")
        if source_wallet.currency != destination_wallet.currency or source_wallet.currency != transfer_data.currency.upper():
            raise HTTPException(status_code=400, detail="Currency mismatch.")

        transfer_money_obj = Money(amount_minor=transfer_data.amount_cents, currency=source_wallet.currency)
        
        fee_rule, fee_amount_major = await FeeService.calculate_transfer_fee(
            transaction_amount=transfer_money_obj.amount_major, 
            session=db
        )
        
        fee_money_obj = Money.from_major(amount_major=fee_amount_major, currency=source_wallet.currency)

        try:
            source_wallet.withdraw(transfer_money_obj) 
            if fee_money_obj.amount_minor > 0:
                source_wallet.withdraw(fee_money_obj) 
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient funds to cover transfer and fee ({fee_amount_major} {source_wallet.currency})."
            )

        destination_wallet.deposit(transfer_money_obj)

        sender_transaction = Transaction(
            wallet_id=source_wallet.id,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            amount_cents=transfer_data.amount_cents,
            currency=source_wallet.currency,
            description=transfer_data.description or f"Sent transfer to wallet {destination_wallet.id}",
            counterparty_wallet_id=destination_wallet.id
        )
        db.add(sender_transaction)

        recipient_transaction = Transaction(
            wallet_id=destination_wallet.id,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.COMPLETED,
            amount_cents=transfer_data.amount_cents,
            currency=destination_wallet.currency,
            description=transfer_data.description or f"Received transfer from wallet {source_wallet.id}",
            counterparty_wallet_id=source_wallet.id
        )
        db.add(recipient_transaction)

        db.add(source_wallet)
        db.add(destination_wallet)
        
        await db.flush()

        if fee_rule and fee_amount_major > 0:
            fee_record = await FeeService.apply_fee(
                transaction_id=sender_transaction.id,
                user_id=current_user.id,
                rule_id=fee_rule.id,
                transaction_amount=transfer_money_obj.amount_major,
                computed_fee=fee_amount_major,
                session=db
            )
            await FeeService.mark_applied(fee_id=fee_record.id, session=db)
            sender_transaction.fee_id = fee_record.id
            db.add(sender_transaction)

        await db.commit()
        await db.refresh(sender_transaction)
        return sender_transaction

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred during transfer: {str(e)}")

@router.post("/deposit", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def deposit_money(
    request: Request,
    deposit_data: DepositWithdrawRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Safely deposit money into a wallet.
    """
    if deposit_data.amount_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount must be greater than zero."
        )
    
    kyc = await db.execute(
    select(KYCSubmission).where(KYCSubmission.user_id == current_user.id)
    )
    
    kyc_submission = kyc.scalars().first()
    
    if not kyc_submission or kyc_submission.status != DocStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="KYC verification is required and must be approved to perform withdrawals."
        )
    

    try:
        # Load and lock the wallet
        stmt = select(Wallet).where(Wallet.id == deposit_data.wallet_id).with_for_update()
        res = await db.execute(stmt)
        wallet = res.scalars().first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found."
            )

        if wallet.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this wallet."
            )

        if not wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wallet is currently inactive."
            )

        if wallet.currency != deposit_data.currency.upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deposit currency {deposit_data.currency} does not match wallet currency {wallet.currency}."
            )

        deposit_money_obj = Money(amount_minor=deposit_data.amount_cents, currency=wallet.currency)
        wallet.deposit(deposit_money_obj)

        new_transaction = Transaction(
            wallet_id=wallet.id,
            transaction_type=TransactionType.DEPOSIT,
            status=TransactionStatus.COMPLETED,
            amount_cents=deposit_data.amount_cents,
            currency=wallet.currency,
            description=deposit_data.description or "Deposit",
        )

        db.add(wallet)
        db.add(new_transaction)
        await db.commit()

        await db.refresh(new_transaction)
        return new_transaction

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during deposit: {str(e)}"
        )


@router.post("/withdraw", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def withdraw_money(
    request: Request,
    withdraw_data: DepositWithdrawRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Safely withdraw money from a wallet.
    """
    kyc = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == current_user.id)
    )
    kyc_submission = kyc.scalars().first()
    
    if not kyc_submission or kyc_submission.status != DocStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="KYC verification is required and must be approved to perform withdrawals."
        )
    
    if withdraw_data.amount_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawal amount must be greater than zero."
        )

    try:
        # Load and lock the wallet
        stmt = select(Wallet).where(Wallet.id == withdraw_data.wallet_id).with_for_update()
        res = await db.execute(stmt)
        wallet = res.scalars().first()

        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found."
            )

        if wallet.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this wallet."
            )

        if not wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wallet is currently inactive."
            )

        if wallet.currency != withdraw_data.currency.upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Withdrawal currency {withdraw_data.currency} does not match wallet currency {wallet.currency}."
            )

        withdraw_money_obj = Money(amount_minor=withdraw_data.amount_cents, currency=wallet.currency)
        
        try:
            wallet.withdraw(withdraw_money_obj)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        new_transaction = Transaction(
            wallet_id=wallet.id,
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.COMPLETED,
            amount_cents=withdraw_data.amount_cents,
            currency=wallet.currency,
            description=withdraw_data.description or "Withdrawal",
        )

        db.add(wallet)
        db.add(new_transaction)
        await db.commit()

        await db.refresh(new_transaction)
        return new_transaction

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during withdrawal: {str(e)}"
        )


@router.get("/history", response_model=List[TransactionResponse], status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def get_transaction_history(
    request: Request,
    wallet_id: Optional[UUID] = None,
    transaction_type: Optional[TransactionType] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List transaction history for any of the user's active wallets with filters and pagination.
    """
    # 1. Fetch user's wallets to ensure authorization
    wallets_stmt = select(Wallet.id).where(Wallet.user_id == current_user.id)
    wallets_res = await db.execute(wallets_stmt)
    user_wallet_ids = wallets_res.scalars().all()

    if not user_wallet_ids:
        return []

    # 2. Build transaction query
    stmt = select(Transaction)

    # Filter transactions belonging to user's wallets
    if wallet_id:
        if wallet_id not in user_wallet_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this wallet."
            )
        stmt = stmt.where(Transaction.wallet_id == wallet_id)
    else:
        stmt = stmt.where(Transaction.wallet_id.in_(user_wallet_ids))

    if transaction_type:
        stmt = stmt.where(Transaction.transaction_type == transaction_type)

    # 3. Apply pagination and sorting
    stmt = stmt.order_by(Transaction.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    transactions = result.scalars().all()

    return transactions