from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.schemas import LoginRequest, TokenResponse, UserRegister, UserResponse
from auth.security import create_access_token, hash_password, verify_password
from database import get_db
from models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id), email=user.email)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=str(user.id), email=user.email),
    )


@router.post("/login", status_code=status.HTTP_200_OK, response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(subject=str(user.id), email=user.email)
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=str(user.id), email=user.email),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout() -> dict[str, str]:
    return {"message": "Logged out"}
