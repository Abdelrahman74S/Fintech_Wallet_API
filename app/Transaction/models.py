import uuid
from uuid import UUID
from enum import Enum
from datetime import datetime
import random
import string
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel
from app.auth.time import TimestampMixin
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pydantic import computed_field

if TYPE_CHECKING:
    from app.wallets.models import Wallet, WalletResponse
    from app.TransactionFee.models import TransactionFee


class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    FEE = "fee"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


def generate_transaction_reference() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    random_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TXN-{timestamp}-{random_str}"


class Transaction(TimestampMixin, SQLModel, table=True):
    __tablename__ = "transactions"

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

    wallet_id: UUID = Field(
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id"),
            nullable=False,
            index=True,
        )
    )

    transaction_type: TransactionType = Field(
        sa_column=sa.Column(
            sa.Enum(TransactionType, name="transaction_type"),
            nullable=False,
            index=True,
        )
    )

    amount_cents: int = Field(
        sa_column=sa.Column(
            sa.BigInteger,
            nullable=False,
        )
    )

    currency: str = Field(
        sa_column=sa.Column(
            sa.String(3),
            nullable=False,
            index=True,
        )
    )

    status: TransactionStatus = Field(
        default=TransactionStatus.PENDING,
        sa_column=sa.Column(
            sa.Enum(TransactionStatus, name="transaction_status"),
            nullable=False,
            index=True,
        )
    )

    reference: str = Field(
        default_factory=generate_transaction_reference,
        sa_column=sa.Column(
            sa.String(100),
            unique=True,
            index=True,
            nullable=False,
        )
    )

    description: Optional[str] = Field(
        default=None,
        sa_column=sa.Column(
            sa.String(255),
            nullable=True,
        )
    )

    counterparty_wallet_id: Optional[UUID] = Field(
        default=None,
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id"),
            nullable=True,
            index=True,
        )
    )
    
    fee_id: Optional[UUID] = Field(
        default=None,
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transaction_fees.id"),
            nullable=True,
            index=True,
        )
    )


    # Relationships
    wallet: Optional["Wallet"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "Transaction.wallet_id",
            "lazy": "selectin",
        }
    )

    counterparty_wallet: Optional["Wallet"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "Transaction.counterparty_wallet_id",
            "lazy": "selectin",
        }
    )
    
    transaction_fee: Optional["TransactionFee"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "Transaction.fee_id",
            "lazy": "selectin",
        }
    )


class TransactionBase(SQLModel):
    wallet_id: UUID
    transaction_type: TransactionType
    amount_cents: int
    currency: str = Field(max_length=3)
    status: TransactionStatus = Field(default=TransactionStatus.PENDING)
    reference: str
    description: Optional[str] = None
    counterparty_wallet_id: Optional[UUID] = None


class TransactionCreate(SQLModel):
    wallet_id: UUID
    transaction_type: TransactionType
    transaction_status: TransactionStatus = Field(default=TransactionStatus.PENDING)
    amount_cents: int
    currency: str = Field(default="EGP", max_length=3)
    description: Optional[str] = None
    counterparty_wallet_id: Optional[UUID] = None


class TransactionResponse(TransactionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    wallet: Optional["WalletResponse"] = None
    counterparty_wallet: Optional["WalletResponse"] = None
    
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def amount_decimal(self) -> float:
        return self.amount_cents / 100.0


class DepositWithdrawRequest(SQLModel):
    wallet_id: UUID
    amount_cents: int
    currency: str = Field(default="EGP", max_length=3)
    description: Optional[str] = None


try:
    from app.wallets.models import Wallet, WalletResponse
    TransactionResponse.model_rebuild(_types_namespace={"Wallet": Wallet, "WalletResponse": WalletResponse})
except ImportError:
    pass
