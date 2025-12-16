from __future__ import annotations

from typing import Optional

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def create_user(session: AsyncSession, email: str, password: str) -> User:
    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
