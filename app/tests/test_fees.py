import pytest
from httpx import AsyncClient
from fastapi import status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.model import User
from app.auth.role import Roles
from app.TransactionFee.models import  FeeType, FeeStatus
from test_auth import valid_user_data
from test_transactions import setup_approved_kyc

pytestmark = pytest.mark.asyncio


async def set_user_admin(db_session: AsyncSession, user_email: str):
    """Helper to set a user's role to ADMIN in the test database."""
    res = await db_session.execute(select(User).where(User.email == user_email))
    user = res.scalars().first()
    assert user is not None
    user.role = Roles.ADMIN
    db_session.add(user)
    await db_session.commit()
    return user


async def test_admin_create_fee_rule_success(client: AsyncClient, db_session: AsyncSession, valid_user_data: dict):
    # 1. Register, login, and set ADMIN
    await client.post("/auth/register", json=valid_user_data)
    login_response = await client.post("/auth/login", data={"username": valid_user_data["email"], "password": valid_user_data["password"]})
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    await set_user_admin(db_session, valid_user_data["email"])

    # 2. Post fee rule creation
    rule_payload = {
        "name": "Flat Transfer Fee",
        "description": "Charging flat EGP 10 fee on transfers",
        "fee_type": FeeType.flat,
        "flat_amount": "10.00"
    }
    response = await client.post("/fees/rules", json=rule_payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    
    rule = response.json()
    assert rule["name"] == "Flat Transfer Fee"
    assert rule["fee_type"] == FeeType.flat
    assert float(rule["flat_amount"]) == 10.0


async def test_non_admin_create_fee_rule_fails(client: AsyncClient, valid_user_data: dict):
    # Register and login (normal Customer role)
    await client.post("/auth/register", json=valid_user_data)
    login_response = await client.post("/auth/login", data={"username": valid_user_data["email"], "password": valid_user_data["password"]})
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    rule_payload = {
        "name": "Flat Transfer Fee",
        "fee_type": FeeType.flat,
        "flat_amount": "10.00"
    }
    response = await client.post("/fees/rules", json=rule_payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_calculate_and_apply_fee_on_transfer(client: AsyncClient, db_session: AsyncSession, valid_user_data: dict):
    # 1. Setup User A (Sender) and User B (Receiver)
    await client.post("/auth/register", json=valid_user_data)
    login_a = await client.post("/auth/login", data={"username": valid_user_data["email"], "password": valid_user_data["password"]})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    await setup_approved_kyc(db_session, valid_user_data["email"])

    user_b_data = valid_user_data.copy()
    user_b_data["email"] = "userb@example.com"
    user_b_data["username"] = "user_b"
    user_b_data["phone_number"] = "09876543210"
    await client.post("/auth/register", json=user_b_data)
    login_b = await client.post("/auth/login", data={"username": user_b_data["email"], "password": user_b_data["password"]})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # 2. Setup EGP 10.00 Flat Transfer Fee Rule (using Admin privilege briefly)
    await set_user_admin(db_session, valid_user_data["email"])
    rule_payload = {
        "name": "Flat Transfer Fee",
        "fee_type": FeeType.flat,
        "flat_amount": "10.00"
    }
    rule_res = await client.post("/fees/rules", json=rule_payload, headers=headers_a)
    assert rule_res.status_code == status.HTTP_201_CREATED
    
    # Restore User A back to CUSTOMER role so they pay the fee
    res = await db_session.execute(select(User).where(User.email == valid_user_data["email"]))
    user_a = res.scalars().first()
    user_a.role = Roles.CUSTOMER
    db_session.add(user_a)
    await db_session.commit()

    # 3. Get EGP Wallet IDs and deposit 20000 cents to User A
    wallets_a = await client.get("/wallets/my-wallets", headers=headers_a)
    wallet_a_id = wallets_a.json()[0]["id"]
    await client.post("/transactions/deposit", json={"wallet_id": wallet_a_id, "amount": 200.0, "currency": "EGP"}, headers=headers_a)

    wallets_b = await client.get("/wallets/my-wallets", headers=headers_b)
    wallet_b_id = wallets_b.json()[0]["id"]

    # 4. Perform Transfer of 15000 cents (with EGP 10.00 fee)
    transfer_payload = {
        "wallet_id": wallet_a_id,
        "counterparty_wallet_id": wallet_b_id,
        "transaction_type": "transfer",
        "amount": 150.0,
        "currency": "EGP"
    }
    transfer_res = await client.post("/transactions/transfer", json=transfer_payload, headers=headers_a)
    assert transfer_res.status_code == status.HTTP_200_OK

    # 5. Assert remaining balances:
    # User A: 20000 cents - 15000 cents (transfer) - 1000 cents (EGP 10.00 fee) = 4000 cents
    balance_a = await client.get(f"/wallets/{wallet_a_id}/balance", headers=headers_a)
    assert balance_a.json() == 4000

    # User B: 15000 cents
    balance_b = await client.get(f"/wallets/{wallet_b_id}/balance", headers=headers_b)
    assert balance_b.json() == 15000

    # 6. Check Transaction Fee ledger record
    fees_res = await client.get("/fees/me", headers=headers_a)
    assert fees_res.status_code == status.HTTP_200_OK
    fees = fees_res.json()
    assert len(fees) == 1
    assert float(fees[0]["computed_fee"]) == 10.0
    assert fees[0]["status"] == FeeStatus.applied
