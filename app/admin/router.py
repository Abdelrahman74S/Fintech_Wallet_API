from app.auth.service import get_current_admin
from app.database import get_db
from typing import  Annotated, Optional
from app.auth.model import User
from app.kyc.models import KYCSubmission, DocType , DocStatus, KYCSubmissionResponse
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

router = APIRouter(prefix="/admin", tags=["Admin"])


from app.auth.service import get_current_admin
from app.database import get_db
from typing import Annotated, List 
from app.auth.model import User
from app.kyc.models import KYCSubmission, KYCSubmissionResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import APIRouter, Depends, HTTPException, status
from app.Transaction.models import Transaction , TransactionResponse
from app.wallets.models import Wallet, WalletResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/kyc-submissions", response_model=List[KYCSubmissionResponse])
async def get_kyc(
    current_user: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    
    result = await session.execute(select(KYCSubmission))
    submissions = result.scalars().all()
    
    if not submissions:
        raise HTTPException(status_code=404, detail="No KYC submissions found.")
        
    return submissions


@router.patch("/kyc/{submission_id}/review")
async def review_kyc(
    current_user: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    submission_id: uuid.UUID,
    status: DocStatus,
    rejection_reason: Optional[str] = None,
):
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    
    result = await session.execute(
        select(KYCSubmission).where(KYCSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    
    if not submission:
        raise HTTPException(status_code=404, detail="KYC submission not found.")
    
    if status == DocStatus.rejected and not rejection_reason:
        raise HTTPException(
            status_code=400,
            detail="Rejection reason is required when rejecting a submission."
        )
    
    submission.status = status
    submission.rejection_reason = rejection_reason if status == DocStatus.rejected else None
    

    session.add(submission)
    await session.commit()
    await session.refresh(submission)
    
    return {"message": f"KYC submission {status.value} successfully."}


@router.get("/Transactions", response_model=List[TransactionResponse])
async def get_all_transactions(
    current_user: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")

    result = await session.execute(select(Transaction))
    transactions = result.scalars().all()

    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions found.")

    return transactions


@router.get("/Wallets", response_model=List[WalletResponse])
async def get_frozen_wallets(
    current_user: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")

    result = await session.execute(select(Wallet).where(Wallet.is_active == False))
    frozen_wallets = result.scalars().all()

    if not frozen_wallets:
        raise HTTPException(status_code=404, detail="No frozen wallets found.")

    return frozen_wallets


@router.patch("/Wallets/frozen/{wallet_id}", response_model=WalletResponse)
async def update_wallet_status(
    current_user: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    wallet_id: uuid.UUID,
    is_frozen: bool,
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")

    result = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    wallet.is_active = not is_frozen
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)

    return wallet
