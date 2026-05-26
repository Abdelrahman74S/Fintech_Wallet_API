import uuid
from uuid import UUID
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.auth.time import TimestampMixin

if TYPE_CHECKING:
    from app.auth.model import User
    from app.Transaction.models import Transaction


class FeeType(str, Enum):
    flat        = "flat"        # fixed amount, e.g. $1.50
    percentage  = "percentage"  # % of transaction amount, e.g. 2.5%
    hybrid      = "hybrid"      # flat + percentage combined


class FeeStatus(str, Enum):
    pending  = "pending"
    applied  = "applied"
    waived   = "waived"
    refunded = "refunded"


# ── Fee Rule (configuration table) ─────────────────────────────────────────

class FeeRule(TimestampMixin, SQLModel, table=True):
    """
    Defines reusable fee configurations (e.g. 'Withdrawal Fee', 'Conversion Fee').
    Rules are referenced when computing actual fees on transactions.
    """
    __tablename__ = "fee_rules"

    id: UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False,
        ),
    )
    name: str = Field(max_length=128, index=True)
    description: Optional[str] = Field(default=None, max_length=256)

    fee_type: FeeType = Field(
        sa_column=sa.Column(sa.Enum(FeeType), nullable=False)
    )

    # For flat/hybrid
    flat_amount: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=sa.Column(sa.Numeric(precision=18, scale=4), nullable=False, server_default="0"),
    )
    # For percentage/hybrid  (stored as 0-100, e.g. 2.5 means 2.5%)
    percentage_rate: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=sa.Column(sa.Numeric(precision=7, scale=4), nullable=False, server_default="0"),
    )
    # Caps
    min_fee: Optional[Decimal] = Field(
        default=None,
        sa_column=sa.Column(sa.Numeric(precision=18, scale=4), nullable=True),
    )
    max_fee: Optional[Decimal] = Field(
        default=None,
        sa_column=sa.Column(sa.Numeric(precision=18, scale=4), nullable=True),
    )

    is_active: bool = Field(default=True)

    # Relationships
    transaction_fees: list["TransactionFee"] = Relationship(back_populates="fee_rule")


# ── Transaction Fee (ledger table) ─────────────────────────────────────────

class TransactionFee(TimestampMixin, SQLModel, table=True):
    """
    Each row records the computed fee charged on a single transaction.
    """
    __tablename__ = "transaction_fees"

    id: UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False,
        ),
    )

    transaction_id: UUID = Field(
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    fee_rule_id: UUID = Field(
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fee_rules.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )

    user_id: UUID = Field(
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    # Snapshot of computed values (never recalculate from live rule)
    fee_type: FeeType = Field(
        sa_column=sa.Column(sa.Enum(FeeType), nullable=False)
    )
    transaction_amount: Decimal = Field(
        sa_column=sa.Column(sa.Numeric(precision=18, scale=4), nullable=False)
    )
    flat_amount: Decimal = Field(
        sa_column=sa.Column(sa.Numeric(precision=18, scale=4), nullable=False, server_default="0")
    )
    percentage_rate: Decimal = Field(
        sa_column=sa.Column(sa.Numeric(precision=7, scale=4), nullable=False, server_default="0")
    )
    computed_fee: Decimal = Field(
        sa_column=sa.Column(sa.Numeric(precision=18, scale=4), nullable=False)
    )

    status: FeeStatus = Field(
        default=FeeStatus.pending,
        sa_column=sa.Column(
            sa.Enum(FeeStatus), nullable=False, server_default="pending"
        ),
    )

    waived_reason: Optional[str] = Field(default=None, max_length=256)

    # Relationships
    fee_rule: Optional["FeeRule"] = Relationship(back_populates="transaction_fees")