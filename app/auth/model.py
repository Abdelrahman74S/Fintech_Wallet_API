from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel
from datetime import UTC, datetime
from typing import Optional, List ,TYPE_CHECKING
from .time import TimestampMixin
from .role import Roles
from uuid import UUID, uuid4
import uuid
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from app.wallets.models import Wallet


class UserBase(SQLModel):
    username: str = Field(max_length=255)
    email: EmailStr = Field(unique=True, index=True)
    first_name: str = Field(max_length=255)
    last_name: str = Field(max_length=255)
    phone_number: str = Field(unique=True)
    age: Optional[int] = None

class User(TimestampMixin,UserBase, table=True):
    __tablename__ = "users"
    
    id: UUID = Field(
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            index=True,
            nullable=False,
        )
    )
    
    password: str = Field(min_length=8, max_length=200)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=True)
    role: Roles =  Field(default=Roles.CUSTOMER)
    
    wallets: List["Wallet"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "lazy": "selectin",
        }
    )
    
class UserCreate(UserBase):
    password: str

class UserUpdate(SQLModel): 
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    first_name: Optional[str] =None
    last_name: Optional[str] =None
    password: Optional[str] = None
    age: Optional[int] = None
    phone_number: Optional[str] = None

class UserResponse(TimestampMixin,UserBase):
    id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    age: int
    role: Roles 
    is_verified: bool
    is_active: bool

class UserResponseProfile(TimestampMixin,UserBase):
    id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    age: int
    role: Roles 
    is_verified: bool
    is_active: bool
    wallets: List["Wallet"] = []

class ProfileUser(SQLModel):
    username: str
    email: EmailStr
    age: Optional[int] = None
    

# --- Token ---
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(SQLModel):
    sub: str
    exp: Optional[int] = None

try:
    from app.wallets.models import Wallet, WalletResponse
    UserResponse.model_rebuild(_types_namespace={"Wallet": Wallet, "WalletResponse": WalletResponse})
    if "UserResponseProfile" in locals():
        UserResponseProfile.model_rebuild(_types_namespace={"Wallet": Wallet, "WalletResponse": WalletResponse})
except ImportError:
    pass


