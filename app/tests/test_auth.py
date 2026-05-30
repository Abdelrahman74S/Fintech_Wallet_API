import pytest
from httpx import AsyncClient
from fastapi import status

pytestmark = pytest.mark.asyncio


@pytest.fixture
def valid_user_data():
    return {
        "username": "abdo_elashri",
        "email": "testuser@example.com",
        "first_name": "Abdelrahman",
        "last_name": "Ramadan",
        "phone_number": "01234567890",
        "password": "StrongPassword123",
        "age": 22
    }


# --------------- Test Cases for Authentication Endpoints ---------------
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "online"


async def test_user_registration_success(client: AsyncClient, valid_user_data: dict):
    response = await client.post("/auth/register", json=valid_user_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    data = response.json()
    assert data["email"] == valid_user_data["email"]
    assert "id" in data  


async def test_user_login_success(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED 
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": valid_user_data["password"]
    }
    
    response = await client.post("/auth/login", data=login_form_data)
    
    assert response.status_code == status.HTTP_200_OK
    
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

async def test_user_profile_access_with_token(client: AsyncClient, valid_user_data: dict):
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
    
    profile_response = await client.get("/auth/profile", headers=headers)
    
    assert profile_response.status_code == status.HTTP_200_OK
    
    profile_data = profile_response.json()
    assert profile_data["email"] == valid_user_data["email"]


async def test_user_profile_access_without_token(client: AsyncClient):
    response = await client.get("/auth/profile")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_user_profile_update_access(client: AsyncClient, valid_user_data: dict):
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
    
    update_data = {
        "first_name": "UpdatedName",
        "age": 30
    }
    
    update_response = await client.patch("/auth/profile/update", json=update_data, headers=headers)
    
    assert update_response.status_code == status.HTTP_200_OK
    
    updated_profile = update_response.json()
    assert updated_profile["first_name"] == "UpdatedName"
    assert updated_profile["age"] == 30

# --------------- Additional Test Cases for Edge Scenarios ---------------
async def test_registration_with_existing_email(client: AsyncClient, valid_user_data: dict):
    response1 = await client.post("/auth/register", json=valid_user_data)
    assert response1.status_code == status.HTTP_201_CREATED
    
    response2 = await client.post("/auth/register", json=valid_user_data)
    assert response2.status_code == status.HTTP_400_BAD_REQUEST
    assert response2.json()["detail"] == "User already registered"


async def test_user_login_incorrect_password(client: AsyncClient, valid_user_data: dict):
    reg_response = await client.post("/auth/register", json=valid_user_data)
    assert reg_response.status_code == status.HTTP_201_CREATED
    
    login_form_data = {
        "username": valid_user_data["email"], 
        "password": "WrongPassword123"
    }
    response = await client.post("/auth/login", data=login_form_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid Credentials"


async def test_user_login_non_existent_user(client: AsyncClient):
    login_form_data = {
        "username": "nonexistent@example.com", 
        "password": "SomePassword123"
    }
    response = await client.post("/auth/login", data=login_form_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid Credentials"


async def test_user_profile_access_invalid_token(client: AsyncClient):
    headers = {"Authorization": "Bearer malformed_token_value_here"}
    response = await client.get("/auth/profile", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Could not validate credentials"


