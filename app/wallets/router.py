from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from app.database import get_db
from app.auth.service import get_current_active_user
from app.auth.model import User
from .models import Wallet, WalletCreate, WalletResponse

router = APIRouter(prefix="/wallets", tags=["Wallets"])


@router.post("/", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def create_wallet(
    wallet_data: WalletCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    statement = select(Wallet).where(
        Wallet.user_id == current_user.id, 
        Wallet.currency == wallet_data.currency.upper()
    )
    result = await db.execute(statement)
    existing_wallet = result.scalars().first()

    if existing_wallet:
        raise HTTPException(
            status_code=400, 
            detail=f"You already have a wallet with currency {wallet_data.currency}"
        )
    
    new_wallet = Wallet(
        user_id=current_user.id,
        currency=wallet_data.currency.upper(),
        balance_cents=0
    )
    
    db.add(new_wallet)
    await db.commit()
    await db.refresh(new_wallet)
    return new_wallet


@router.get("/my-wallets", response_model=List[WalletResponse])
async def get_my_wallets(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):

    statement = select(Wallet).where(Wallet.user_id == current_user.id)
    result = await db.execute(statement)
    wallets = result.scalars().all()
    return wallets


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet_details(
    wallet_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):

    statement = select(Wallet).where(
        Wallet.id == wallet_id, 
        Wallet.user_id == current_user.id
    )
    result = await db.execute(statement)
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
        
    return wallet

@router.get("/{wallet_id}/balance", response_model=int)
async def get_wallet_balance(
    wallet_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> int:
    statement = select(Wallet).where(
        Wallet.id == wallet_id, 
        Wallet.user_id == current_user.id
    )
    result = await db.execute(statement)
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return wallet.balance_cents     

