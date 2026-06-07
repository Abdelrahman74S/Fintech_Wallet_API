import pytest
from httpx import AsyncClient
from fastapi import status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.model import User
from app.wallets.models import Wallet
from app.kyc.models import KYCSubmission, DocType, DocStatus
from app.Transaction.models import Transaction, TransactionType, TransactionStatus
from test_auth import valid_user_data

pytestmark = pytest.mark.asyncio


async def setup_approved_kyc(db_session: AsyncSession, user_email: str):
    """Helper to create and insert an approved KYC submission for a user."""
    res = await db_session.execute(select(User).where(User.email == user_email))
    user = res.scalars().first()
    assert user is not None
    
    kyc = KYCSubmission(
        user_id=user.id,
        document_type=DocType.passport,
        full_name=f"{user.first_name} {user.last_name}",
        document_number="A12345678",
        status=DocStatus.approved
    )
    db_session.add(kyc)
    await db_session.commit()
    return user


async def test_deposit_money_success(client: AsyncClient, db_session: AsyncSession, valid_user_data: dict):
    # 1. Register and login
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    token_data = login_response.json()
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}

    # 2. Setup approved KYC
    user = await setup_approved_kyc(db_session, valid_user_data["email"])

    # 3. Get default EGP wallet ID
    wallets_response = await client.get("/wallets/my-wallets", headers=headers)
    assert wallets_response.status_code == status.HTTP_200_OK
    wallet = wallets_response.json()[0]
    wallet_id = wallet["id"]

    # 4. Perform deposit
    deposit_payload = {
        "wallet_id": wallet_id,
        "amount": 100.0,
        "currency": "EGP",
        "description": "Bank deposit"
    }
    deposit_response = await client.post("/transactions/deposit", json=deposit_payload, headers=headers)
    assert deposit_response.status_code == status.HTTP_200_OK
    
    tx = deposit_response.json()
    assert tx["amount_cents"] == 10000
    assert tx["currency"] == "EGP"
    assert tx["transaction_type"] == TransactionType.DEPOSIT
    assert tx["status"] == TransactionStatus.COMPLETED

    # 5. Verify wallet balance
    balance_response = await client.get(f"/wallets/{wallet_id}/balance", headers=headers)
    assert balance_response.status_code == status.HTTP_200_OK
    assert balance_response.json() == 10000


async def test_deposit_money_without_kyc_fails(client: AsyncClient, valid_user_data: dict):
    # Register and login
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    token_data = login_response.json()
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}

    # Get default wallet ID
    wallets_response = await client.get("/wallets/my-wallets", headers=headers)
    wallet_id = wallets_response.json()[0]["id"]

    # Try depositing without KYC
    deposit_payload = {
        "wallet_id": wallet_id,
        "amount": 100.0,
        "currency": "EGP",
        "description": "Bank deposit"
    }
    deposit_response = await client.post("/transactions/deposit", json=deposit_payload, headers=headers)
    # KYC is missing/pending, so it should return 403 Forbidden
    assert deposit_response.status_code == status.HTTP_403_FORBIDDEN


async def test_withdraw_money_success(client: AsyncClient, db_session: AsyncSession, valid_user_data: dict):
    # Register, login, setup KYC
    await client.post("/auth/register", json=valid_user_data)
    login_form_data = {"username": valid_user_data["email"], "password": valid_user_data["password"]}
    login_response = await client.post("/auth/login", data=login_form_data)
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    await setup_approved_kyc(db_session, valid_user_data["email"])

    # Get default EGP wallet ID
    wallets_response = await client.get("/wallets/my-wallets", headers=headers)
    wallet_id = wallets_response.json()[0]["id"]

    # Deposit 10000 cents first
    deposit_payload = {"wallet_id": wallet_id, "amount": 100.0, "currency": "EGP", "description": "Deposit"}
    await client.post("/transactions/deposit", json=deposit_payload, headers=headers)

    # Withdraw 4000 cents
    withdraw_payload = {
        "wallet_id": wallet_id,
        "amount": 40.0,
        "currency": "EGP",
        "description": "ATM withdrawal"
    }
    withdraw_response = await client.post("/transactions/withdraw", json=withdraw_payload, headers=headers)
    assert withdraw_response.status_code == status.HTTP_200_OK
    
    tx = withdraw_response.json()
    assert tx["amount_cents"] == 4000
    assert tx["transaction_type"] == TransactionType.WITHDRAWAL
    assert tx["status"] == TransactionStatus.COMPLETED

    # Verify wallet balance
    balance_response = await client.get(f"/wallets/{wallet_id}/balance", headers=headers)
    assert balance_response.json() == 6000


async def test_withdraw_insufficient_funds_fails(client: AsyncClient, db_session: AsyncSession, valid_user_data: dict):
    await client.post("/auth/register", json=valid_user_data)
    login_form_data = {"username": valid_user_data["email"], "password": valid_user_data["password"]}
    login_response = await client.post("/auth/login", data=login_form_data)
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    await setup_approved_kyc(db_session, valid_user_data["email"])

    wallets_response = await client.get("/wallets/my-wallets", headers=headers)
    wallet_id = wallets_response.json()[0]["id"]

    # Withdraw 5000 cents when balance is 0
    withdraw_payload = {"wallet_id": wallet_id, "amount": 50.0, "currency": "EGP"}
    withdraw_response = await client.post("/transactions/withdraw", json=withdraw_payload, headers=headers)
    assert withdraw_response.status_code == status.HTTP_400_BAD_REQUEST


async def test_transfer_money_success(client: AsyncClient, db_session: AsyncSession, valid_user_data: dict):
    # 1. Setup User A (Sender)
    await client.post("/auth/register", json=valid_user_data)
    login_a = await client.post("/auth/login", data={"username": valid_user_data["email"], "password": valid_user_data["password"]})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    await setup_approved_kyc(db_session, valid_user_data["email"])
    
    wallets_a = await client.get("/wallets/my-wallets", headers=headers_a)
    wallet_a_id = wallets_a.json()[0]["id"]

    # Deposit 20000 cents to User A EGP wallet
    await client.post("/transactions/deposit", json={"wallet_id": wallet_a_id, "amount": 200.0, "currency": "EGP"}, headers=headers_a)

    # 2. Setup User B (Receiver)
    user_b_data = valid_user_data.copy()
    user_b_data["email"] = "userb@example.com"
    user_b_data["username"] = "user_b"
    user_b_data["phone_number"] = "09876543210"
    await client.post("/auth/register", json=user_b_data)
    login_b = await client.post("/auth/login", data={"username": user_b_data["email"], "password": user_b_data["password"]})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    
    wallets_b = await client.get("/wallets/my-wallets", headers=headers_b)
    wallet_b_id = wallets_b.json()[0]["id"]

    # 3. Perform transfer from A to B
    transfer_payload = {
        "wallet_id": wallet_a_id,
        "counterparty_wallet_id": wallet_b_id,
        "transaction_type": "transfer",
        "amount": 150.0,
        "currency": "EGP",
        "description": "Gift to B"
    }
    transfer_response = await client.post("/transactions/transfer", json=transfer_payload, headers=headers_a)
    assert transfer_response.status_code == status.HTTP_200_OK

    # 4. Verify balances
    balance_a = await client.get(f"/wallets/{wallet_a_id}/balance", headers=headers_a)
    assert balance_a.json() == 5000

    balance_b = await client.get(f"/wallets/{wallet_b_id}/balance", headers=headers_b)
    assert balance_b.json() == 15000


async def test_transaction_history_scenario(client: AsyncClient, db_session: AsyncSession, valid_user_data: dict):
    # 1. Setup User A, KYC and EGP wallet
    await client.post("/auth/register", json=valid_user_data)
    login_response = await client.post("/auth/login", data={"username": valid_user_data["email"], "password": valid_user_data["password"]})
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    await setup_approved_kyc(db_session, valid_user_data["email"])

    wallets_response = await client.get("/wallets/my-wallets", headers=headers)
    wallet_id = wallets_response.json()[0]["id"]

    # 2. Seed multiple transactions with different details
    # Deposit: Salary 10000 cents
    await client.post("/transactions/deposit", json={"wallet_id": wallet_id, "amount": 100.0, "currency": "EGP", "description": "Deposit Salary"}, headers=headers)
    # Withdrawal: Supermarket 2000 cents
    await client.post("/transactions/withdraw", json={"wallet_id": wallet_id, "amount": 20.0, "currency": "EGP", "description": "Supermarket buy"}, headers=headers)
    # Deposit: Refund from Amazon 5000 cents
    await client.post("/transactions/deposit", json={"wallet_id": wallet_id, "amount": 50.0, "currency": "EGP", "description": "Refund from Amazon"}, headers=headers)
    # Withdrawal: Coffee 1000 cents
    await client.post("/transactions/withdraw", json={"wallet_id": wallet_id, "amount": 10.0, "currency": "EGP", "description": "Coffee purchase"}, headers=headers)

    # 3. Test SEARCH function (Search: "amazon")
    search_res = await client.get("/transactions/history?search=amazon", headers=headers)
    assert search_res.status_code == status.HTTP_200_OK
    search_data = search_res.json()
    assert len(search_data) == 1
    assert "Amazon" in search_data[0]["description"]

    # 4. Test FILTER function (Filter: transaction_type = withdrawal)
    filter_res = await client.get("/transactions/history?transaction_type=withdrawal", headers=headers)
    assert filter_res.status_code == status.HTTP_200_OK
    filter_data = filter_res.json()
    assert len(filter_data) == 2
    assert all(tx["transaction_type"] == "withdrawal" for tx in filter_data)

    # 5. Test SORT function (Sort by: amount_cents, order: asc)
    sort_res = await client.get("/transactions/history?sort_by=amount_cents&sort_order=asc", headers=headers)
    assert sort_res.status_code == status.HTTP_200_OK
    sort_data = sort_res.json()
    assert len(sort_data) == 4
    amounts = [tx["amount_cents"] for tx in sort_data]
    assert amounts == [1000, 2000, 5000, 10000]

    # 6. Test PAGE function (Limit: 2, Offset: 1, Sort: amount_cents asc)
    # Ordered amounts: [1000, 2000, 5000, 10000]. Offset 1 skips 1000. Limit 2 takes [2000, 5000].
    page_res = await client.get("/transactions/history?sort_by=amount_cents&sort_order=asc&limit=2&offset=1", headers=headers)
    assert page_res.status_code == status.HTTP_200_OK
    page_data = page_res.json()
    assert len(page_data) == 2
    page_amounts = [tx["amount_cents"] for tx in page_data]
    assert page_amounts == [2000, 5000]

