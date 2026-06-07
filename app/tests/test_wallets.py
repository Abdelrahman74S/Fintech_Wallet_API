import pytest
from httpx import AsyncClient
from fastapi import status
from test_auth import valid_user_data 

pytestmark = pytest.mark.asyncio


async def test_create_wallet_success(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    
    token_data = login_response.json()
    access_token = token_data["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}

    wallet_data = {"currency": "USD"}
    response = await client.post("/wallets/", json=wallet_data, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED
    
    wallet_response = response.json()
    assert wallet_response["currency"] == "USD"


async def test_my_wallets_success(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    
    token_data = login_response.json()
    access_token = token_data["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}

    wallet_data = {"currency": "USD"}
    create_response = await client.post("/wallets/", json=wallet_data, headers=headers)
    assert create_response.status_code == status.HTTP_201_CREATED

    my_wallets_response = await client.get("/wallets/my-wallets", headers=headers)
    assert my_wallets_response.status_code == status.HTTP_200_OK
    
    wallets_list = my_wallets_response.json()
    assert isinstance(wallets_list, list)
    assert len(wallets_list) == 2


async def test_create_duplicate_currency_wallet_fails(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    
    token_data = login_response.json()
    access_token = token_data["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}

    # EGP wallet is already created automatically during registration
    wallet_data = {"currency": "EGP"}
    response = await client.post("/wallets/", json=wallet_data, headers=headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already have a wallet with currency EGP" in response.json()["detail"]


async def test_get_wallet_details_success(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    
    token_data = login_response.json()
    access_token = token_data["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}

    # Create a USD wallet
    wallet_data = {"currency": "USD"}
    create_response = await client.post("/wallets/", json=wallet_data, headers=headers)
    assert create_response.status_code == status.HTTP_201_CREATED
    wallet_id = create_response.json()["id"]

    # Fetch wallet details
    details_response = await client.get(f"/wallets/{wallet_id}", headers=headers)
    assert details_response.status_code == status.HTTP_200_OK
    
    details = details_response.json()
    assert details["id"] == wallet_id
    assert details["currency"] == "USD"
    assert details["balance_cents"] == 0


async def test_get_wallet_details_not_found(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    
    token_data = login_response.json()
    access_token = token_data["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}

    import uuid
    random_uuid = str(uuid.uuid4())

    details_response = await client.get(f"/wallets/{random_uuid}", headers=headers)
    assert details_response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_wallet_balance_success(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    
    login_response = await client.post("/auth/login", data=login_form_data)
    assert login_response.status_code == status.HTTP_200_OK
    
    token_data = login_response.json()
    access_token = token_data["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch default EGP wallet ID from my-wallets
    my_wallets_response = await client.get("/wallets/my-wallets", headers=headers)
    assert my_wallets_response.status_code == status.HTTP_200_OK
    default_egp_wallet = my_wallets_response.json()[0]
    wallet_id = default_egp_wallet["id"]

    # Fetch balance
    balance_response = await client.get(f"/wallets/{wallet_id}/balance", headers=headers)
    assert balance_response.status_code == status.HTTP_200_OK
    assert balance_response.json() == 0