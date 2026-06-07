import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from app.config import settings
from app.main import app
from app.database import get_db
from app.Transaction.router import limiter

# Disable rate limiter for testing
limiter.enabled = False

TEST_DATABASE_URL = settings.TEST_DATABASE_URL

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
async_session_test = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture( autouse=True)
async def init_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as session:
        yield session
        await session.rollback()
        await session.close() 

@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()