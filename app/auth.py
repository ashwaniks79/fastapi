# auth.py

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from . import database, models
from .models import User

# Load .env variables
load_dotenv()

# ========= User Role Mapping =========
ROLE_MODEL_MAP = {
    "customer": User,
    "admin": User,
    "staff": User,
    "contractor": User,
}

ROLE_UPDATE_MAP = {
    "staff": User,
    "contractor": User,
    "customer": User
}

# ========= ENV CONFIG =========
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 1))

EMAIL_SECRET = os.getenv("EMAIL_VERIFICATION_SECRET")
EMAIL_EXPIRE_MINUTES = int(os.getenv("EMAIL_VERIFICATION_EXPIRE_MINUTES", 30))

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

# ✅ Mailgun Support
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp")  # fallback to SMTP if not defined

# OTP Settings
OTP_SECRET = os.getenv("OTP_SECRET")
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", 2))
OTP_ATTEMPTS_LIMIT = int(os.getenv("OTP_ATTEMPTS_LIMIT", 3))
OTP_EXPIRE_FOR_RESET_MINUTES = 5

# Password encryption
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# ========= UTILS =========

async def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

async def get_password_hash(password):
    return pwd_context.hash(password)

async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def get_user_by_email_from_users_table(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def authenticate_user(db: AsyncSession, username_input: str, password: str):
    if "@" in username_input:
        result = await db.execute(select(models.User).filter(models.User.email == username_input))
    else:
        result = await db.execute(select(models.User).filter(models.User.username == username_input))

    user = result.scalars().first()
    if not user or not await verify_password(password, user.hashed_password):
        return False
    return user

async def authenticate_user_by_model(db: AsyncSession, model, username_or_email: str, password: str):
    result = await db.execute(select(User).where(User.email == username_or_email))
    user = result.scalar_one_or_none()
    if user and await verify_password(password, user.hashed_password):
        return user
    return None

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: timedelta = None):
    expire = datetime.utcnow() + (expires_delta or timedelta(days=7))
    to_encode = data.copy()
    to_encode.update({"exp": expire, "scope": "refresh_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError("Token is invalid or expired") from e

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(database.get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")

        if not email or not role or role not in ROLE_MODEL_MAP:
            raise credentials_exception

        model = ROLE_MODEL_MAP[role]
        result = await db.execute(select(model).filter(model.email == email))
        user = result.scalars().first()
        if not user:
            raise credentials_exception

        return user
    except JWTError:
        raise credentials_exception

async def get_current_admin(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized as admin")
    return current_user
