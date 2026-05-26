from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .auth.router import router as auth_router
from .wallets.router import router as wallet_router
from .Transaction.router import router as transaction_router
from .kyc.router import router as kyc_router  
from .admin.router import router as admin_router
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic (if any)
    yield
    # Shutdown logic (if any)


app = FastAPI(
    title=settings.APP_NAME,
    description="A comprehensive Fintech Wallet API for managing users, wallets, and transactions.",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint that provides a welcome message and links to documentation.
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}!",
        "version": "1.1.0",
        "status": "online",
        "docs": "/docs",
        "redoc": "/redoc",
    }


# Include Routers
app.include_router(auth_router)
app.include_router(wallet_router)
app.include_router(transaction_router)
app.include_router(kyc_router)
app.include_router(admin_router)
