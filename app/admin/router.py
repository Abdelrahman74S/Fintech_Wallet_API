from app.auth.service import get_current_admin
from app.database import get_db
from typing import  Annotated
from app.auth.model import User
from app.kyc.models import KYCSubmission, DocType , DocStatus, KYCSubmissionResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/", response_model=KYCSubmissionResponse)
def get_kyc(
    current_user: Annotated[User, Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    
    submission = session.exec(
        select(KYCSubmission)
    ).all()
    if not submission:
        raise HTTPException(status_code=404, detail="No KYC submission found.")
    return [KYCSubmissionResponse.model_validate(s) for s in submission]