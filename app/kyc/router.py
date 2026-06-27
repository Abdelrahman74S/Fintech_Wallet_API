from .models import KYCSubmission, DocType , DocStatus, KYCSubmissionResponse
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Optional , Annotated
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
import aiofiles
from pathlib import Path
from app.auth.service import get_current_admin , get_current_user
from app.auth.model import User
from app.database import get_db
from app.boto import generate_presigned_download_url
from app.boto import upload_file_obj


router = APIRouter(prefix="/kyc", tags=["KYC"])



UPLOAD_DIR = Path("media/kyc")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


async def _validate_and_save(file: UploadFile, user_id: uuid.UUID) -> str:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{file.content_type}'. "
                f"Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
        )
    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {MAX_FILE_SIZE_MB} MB limit.",
        )
    await file.seek(0)
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "bin"
    filename = f"{user_id}_{uuid.uuid4().hex}.{ext}"
    upload_file_obj(
        file_obj=file.file,
        bucket_name="kyc-documents",
        object_name=filename,
        content_type=file.content_type
    )
    return filename



@router.post(
    "/submit",
    response_model=KYCSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit KYC document",
)
async def submit_kyc(
    document_type: Annotated[DocType, Form(...)],
    full_name: Annotated[str, Form(..., min_length=2, max_length=128)],
    document_number: Annotated[str, Form(..., min_length=4, max_length=64)],
    document_file: Annotated[UploadFile, File(..., description="ID scan (JPEG/PNG/PDF, ≤10 MB)")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KYCSubmissionResponse:
    
    file_url = await _validate_and_save(document_file, current_user.id)
    submission = KYCSubmission(
        user_id=current_user.id,
        document_type=document_type,
        full_name=full_name.strip(),
        document_number=document_number.strip(),
        status=DocStatus.pending,
        file_url=file_url, 
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
