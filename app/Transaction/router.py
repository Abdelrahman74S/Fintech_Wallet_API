from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Optional
from uuid import UUID

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

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/transfer", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
async def transfer_money(
    transfer_data: TransactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Safely transfer money between two wallets in a deadlock-free and race-condition-protected transaction.
    """
    # 1. Basic validation
    if transfer_data.amount_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transfer amount must be greater than zero."
        )

    if transfer_data.wallet_id == transfer_data.counterparty_wallet_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer to the same wallet."
        )

    if not transfer_data.counterparty_wallet_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Counterparty wallet ID is required for a transfer."
        )

    # 2. Acquire locks in a consistent UUID-sorted order to prevent deadlocks under concurrency
    wallet_ids = sorted([transfer_data.wallet_id, transfer_data.counterparty_wallet_id])

    try:
        # Load and lock the wallets using row-level write locks (FOR UPDATE)
        stmt_1 = select(Wallet).where(Wallet.id == wallet_ids[0]).with_for_update()
        stmt_2 = select(Wallet).where(Wallet.id == wallet_ids[1]).with_for_update()

        res_1 = await db.execute(stmt_1)
        wallet_1 = res_1.scalars().first()

        res_2 = await db.execute(stmt_2)
        wallet_2 = res_2.scalars().first()

        if not wallet_1 or not wallet_2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both of the specified wallets were not found."
            )

        # Identify source and destination wallets from locked records
        if wallet_1.id == transfer_data.wallet_id:
            source_wallet = wallet_1
            destination_wallet = wallet_2
        else:
            source_wallet = wallet_2
            destination_wallet = wallet_1

        # 3. Ownership and Business logic checks
        if source_wallet.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own the source wallet."
            )

        if not source_wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source wallet is currently inactive."
            )

        if not destination_wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Destination wallet is currently inactive."
            )

        if source_wallet.currency != destination_wallet.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Currency mismatch. Source wallet is in {source_wallet.currency} while destination wallet is in {destination_wallet.currency}."
            )

        if source_wallet.currency != transfer_data.currency.upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested currency {transfer_data.currency} does not match source wallet currency {source_wallet.currency}."
            )

        # 4. Perform the balance updates
        transfer_money_obj = Money(amount_minor=transfer_data.amount_cents, currency=source_wallet.currency)
        
        try:
            source_wallet.withdraw(transfer_money_obj)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        destination_wallet.deposit(transfer_money_obj)

        # 5. Create transaction ledger records for both wallets
        # Sender's transaction
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

        # Recipient's transaction
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

        # Save all changes to the database
        db.add(source_wallet)
        db.add(destination_wallet)
        await db.commit()

        await db.refresh(sender_transaction)
        return sender_transaction

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during transfer: {str(e)}"
        )


@router.post("/deposit", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
async def deposit_money(
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
async def withdraw_money(
    withdraw_data: DepositWithdrawRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Safely withdraw money from a wallet.
    """
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
async def get_transaction_history(
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