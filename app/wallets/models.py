import uuid
from uuid import UUID
from sqlmodel import Field, Relationship, SQLModel
from typing import Optional, List, TYPE_CHECKING
from app.auth.time import TimestampMixin
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pydantic import computed_field

if TYPE_CHECKING:
    from app.auth.model import User, UserResponse, UserResponseProfile

from .service import Money


class Wallet(TimestampMixin, SQLModel, table=True):
    __tablename__ = "wallets"

    id: UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            primary_key=True,      
            default=uuid.uuid4,
            index=True,
            nullable=False,
        )

    )

    user_id: UUID = Field(
        sa_column=sa.Column(
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        )
    )

    balance_cents: int = Field(
        sa_column=sa.Column(
            sa.BigInteger,
            nullable=False,
            server_default="0",
            default=0
        )
    )

    currency: str = Field(index=True, max_length=3)
    is_active: bool = Field(default=True)

    user: Optional["User"] = Relationship(back_populates="wallets")

    __table_args__ = (
        sa.UniqueConstraint("user_id", "currency", name="unique_user_wallet_currency"),
    )

    @property
    def money(self) -> Money:
        return Money(amount_minor=self.balance_cents, currency=self.currency)

    def deposit(self, money_obj: Money):
        if money_obj.currency != self.currency:
            raise ValueError("Currency mismatch")
        self.balance_cents += money_obj.amount_minor

    def withdraw(self, money_obj: Money):
        new_money = self.money - money_obj
        self.balance_cents = new_money.amount_minor


class WalletBase(SQLModel):
    currency: str = Field(max_length=3)
    is_active: bool = Field(default=True)


class WalletCreate(SQLModel):
    currency: str = Field(default="EGP", max_length=3)


class WalletResponse(WalletBase):
    id: UUID
    user_id: UUID
    balance_cents: int
    is_active: bool

    user: Optional["UserResponse"] = None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def balance_decimal(self) -> float:
        return self.balance_cents / 100.0


class WalletUpdate(SQLModel):
    is_active: Optional[bool] = None


try:
    from app.auth.model import User, UserResponse, UserResponseProfile
    WalletResponse.model_rebuild(_types_namespace={
        "User": User,
        "UserResponse": UserResponse,
        "UserResponseProfile": UserResponseProfile
    })
except ImportError:
    pass