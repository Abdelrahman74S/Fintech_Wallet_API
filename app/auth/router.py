from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from datetime import datetime, timedelta
from ..database import get_db 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select 
from .model import (
    User, UserCreate, UserResponse, Token,
    UserUpdate , UserResponseProfile, ProfileUser, 
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from app.wallets.models import Wallet 

from .service import (
    get_user_by_email,authenticate_user,get_password_hash,
    get_current_active_user,get_current_verified_user,
    create_access_token
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_create: UserCreate, db: AsyncSession = Depends(get_db)):
    statement = select(User).where(User.email == user_create.email)
    result = await db.execute(statement)
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User already registered"
        )

    hashed_password = get_password_hash(user_create.password)
    user_data = user_create.model_dump()
    user_data["password"] = hashed_password
    
    new_user = User(**user_data)
    db.add(new_user)
    
    await db.flush() 

    default_wallet = Wallet(
        user_id=new_user.id,
        currency="EGP",
        balance_cents=0,
        is_active=True
    )
    db.add(default_wallet)

    await db.commit()
    await db.refresh(new_user)

    return new_user

@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, user_credentials.username, user_credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/profile", response_model=UserResponseProfile, status_code=status.HTTP_200_OK)
async def profile_user(
    current_user: User = Depends(get_current_active_user),
):

    return current_user

@router.patch("/profile/update",response_model=UserResponseProfile,status_code=status.HTTP_200_OK
)
async def update_user_patch(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):

    update_data = user_data.model_dump( exclude_unset=True,exclude_none=True)
    
    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])
    
    for key, value in update_data.items():
        setattr(current_user, key, value)

    try:
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, 
            detail="Email or Phone number already exists"
        )
    
    return current_user

