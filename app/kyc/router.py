from .models import KYCSubmission , DocStatus, KYCSubmissionResponse , UploadRequest , KYCSubmitRequest
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Optional , Annotated
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.auth.service import get_current_admin , get_current_user
from app.auth.model import User
from app.boto import generate_presigned_download_url, generate_presigned_upload_post

router = APIRouter(prefix="/kyc", tags=["KYC"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_FILE_SIZE_MB = 10


@router.post(
    "/request-upload",
    summary="Get presigned upload details for direct upload to MinIO",
)
async def request_upload(
    request: UploadRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    if request.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{request.content_type}'. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
        )
    
    ext = request.file_name.rsplit(".", 1)[-1] if "." in request.file_name else "bin"
    object_name = f"{current_user.id}_{uuid.uuid4().hex}.{ext}"
    
    upload_data = generate_presigned_upload_post(
        bucket_name="kyc-documents",
        object_name=object_name,
        content_type=request.content_type,
        max_size_mb=MAX_FILE_SIZE_MB
    )
    
    return {
        "upload_data": upload_data,
        "object_name": object_name
    }

@router.post(
    "/submit",
    response_model=KYCSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit KYC document metadata",
)
async def submit_kyc(
    request: KYCSubmitRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KYCSubmissionResponse:
    
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.user_id == current_user.id)
    )
    existing = result.scalars().first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"KYC already submitted with status '{existing.status.value}'. Contact support to re-submit.",
        )
    
    submission = KYCSubmission(
        user_id=current_user.id,
        document_type=request.document_type,
        full_name=request.full_name.strip(),
        document_number=request.document_number.strip(),
        status=DocStatus.pending,
        file_url=request.object_name, 
    )
    
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    
    response_data = KYCSubmissionResponse.model_validate(submission)
    if response_data.file_url:
        response_data.file_url = generate_presigned_download_url(
            bucket_name="kyc-documents", 
            object_name=response_data.file_url,
            expires_in=3600 
        )
    return response_data
