import uuid
from uuid import UUID
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel
from app.auth.time import TimestampMixin
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from app.auth.model import User  

class DocType(str, Enum):
    passport = "passport"
    national_id = "national_id"
    drivers_license = "drivers_license"

class DocStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    
class KYCSubmission(TimestampMixin, SQLModel, table=True):
    __tablename__ = "kyc_submissions" 

    id: UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            index=True,
            nullable=False,
        ),
    )
    
    user_id: UUID = Field(
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), 
            nullable=False,
            index=True,
            unique=True, 
        )
    )
    
    document_type: DocType = Field(
        sa_column=sa.Column(sa.Enum(DocType), nullable=False)
    )
    full_name: str
    document_number: str
    
    status: DocStatus = Field(
        default=DocStatus.pending,
        sa_column=sa.Column(sa.Enum(DocStatus), nullable=False, server_default="pending")
    )
    
    file_url: Optional[str] = None
    rejection_reason: Optional[str] = Field(default=None, nullable=True) 

    user: Optional["User"] = Relationship(back_populates="kyc_submission")


class KYCSubmissionResponse(TimestampMixin,SQLModel):
    id: UUID
    user_id: UUID
    document_type: DocType
    full_name: str
    document_number: str
    status: DocStatus
    file_url: Optional[str] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True
