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

    wallet_data = {"currency": "USD"}
    create_response = await client.post("/wallets/", json=wallet_data, headers=headers)
    assert create_response.status_code == status.HTTP_201_CREATED

    wallet_response = create_response.json()
    wallet_id = wallet_response["id"]

    details_response = await client.get(f"/wallets/{wallet_id}", headers=headers)
    assert details_response.status_code == status.HTTP_200_OK
    
    details_data = details_response.json()
    assert details_data["id"] == wallet_id

async def test_get_wallet_details_balance_success(client: AsyncClient, valid_user_data: dict):
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

    wallet_response = create_response.json()
    wallet_id = wallet_response["id"]

    details_response = await client.get(f"/wallets/{wallet_id}/balance", headers=headers)
    assert details_response.status_code == status.HTTP_200_OK
    
    details_data = details_response.json()
    assert details_data == 0