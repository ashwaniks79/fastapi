


from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from . import database, models, schemas, crud, auth
from .schemas import UserOut
from .auth import get_current_user
from .models import User, Admin
from .database import get_db
import smtplib
from .auth import get_current_admin
from fastapi import Body
from datetime import timezone, timedelta
from app.schemas import LoginRequest, UnifiedLoginResponse
from app.auth import create_access_token, verify_password, get_password_hash
from sqlalchemy import select
from zoneinfo import ZoneInfo
from app import schemas
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.auth import oauth2_scheme, SECRET_KEY, ALGORITHM 

from fastapi import Form
from fastapi import Query
from typing import List
from app.auth import get_password_hash
from fastapi.responses import JSONResponse
from app.auth import create_refresh_token
from app.auth import get_current_admin 
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi import Request
import json
from zoneinfo import ZoneInfo
from fastapi.responses import RedirectResponse
from datetime import datetime
from app.logging_model import RequestLog
import random
from datetime import datetime, timedelta
from email.mime.text import MIMEText

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://170.64.163.105:3001"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now(ZoneInfo("Australia/Sydney"))

    
    # Skip logging for documentation endpoints
    if request.url.path in ["/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
    
    try:
        response = await call_next(request)
    except HTTPException as http_exc:
        process_time = (datetime.now(ZoneInfo("Australia/Sydney")) - start_time).total_seconds() * 1000
        log_data = {
            "timestamp": start_time,
            "method": request.method,
            "path": request.url.path,
            "ip": request.client.host if request.client else None,
            "status_code": http_exc.status_code,
            "process_time_ms": process_time,
            "user_agent": request.headers.get("user-agent"),
            "error": http_exc.detail
        }
        logger.error(json.dumps({**log_data, "timestamp": log_data["timestamp"].isoformat()}))
        raise http_exc
    except Exception as e:
        process_time = (datetime.now(ZoneInfo("Australia/Sydney"))- start_time).total_seconds() * 1000
        logger.error(f"Request failed: {str(e)}")
        raise
    
    process_time = (datetime.now(ZoneInfo("Australia/Sydney")) - start_time).total_seconds() * 1000
    
    log_data = {
        "timestamp": start_time,
        "method": request.method,
        "path": request.url.path,
        "ip": request.client.host if request.client else None,
        "status_code": response.status_code,
        "process_time_ms": process_time,
        "user_agent": request.headers.get("user-agent"),
    }
    
    # Special handling for login attempts
    if request.url.path == "/login":
        try:
            body = await request.json()
            log_data["additional_data"] = {
                "login_attempt": {
                    "email": body.get("email"),
                    "success": response.status_code == 200
                }
            }
        except Exception as e:
            logger.warning(f"Failed to parse login data: {str(e)}")
    
    # Special handling for file uploads
    if request.url.path == "/upload":
        try:
            log_data["additional_data"] = {
                "file_upload": True,
                "content_type": request.headers.get("content-type")
            }
        except Exception as e:
            logger.warning(f"Failed to log upload details: {str(e)}")
    
    # Log to console
    console_log = {**log_data, "timestamp": log_data["timestamp"].isoformat()}
    logger.info(json.dumps(console_log, default=str))
    
    # Store in database
    try:
        db = database.async_session()
        await crud.create_request_log(db, log_data)
    except Exception as e:
        logger.error(f"Database log failed: {str(e)}")
    finally:
        await db.close()
 
    
    return response

@app.on_event("startup")
async def on_startup():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        from .logging_model import RequestLog
        await conn.run_sync(RequestLog.metadata.create_all)



# @app.post("/register", response_model=schemas.UserOut)
# async def register(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
#     existing_user = await auth.get_user_by_email(db, user.email)
#     if existing_user:
#         raise HTTPException(status_code=400, detail="Email already registered")
#     return await crud.create_user(db, user, role="customer")
# Add these endpoints
# @app.post("/register", response_model=schemas.UserOut)
# async def register(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
#     existing_user = await auth.get_user_by_email(db, user.email)
#     if existing_user:
#         raise HTTPException(status_code=400, detail="Email already registered")
    
#     # Create user but mark as not verified
#     new_user = await crud.create_user(db, user, role="customer")
    
#     # Generate and send OTP
#     otp = str(random.randint(1000, 9999))
#     otp_expires = datetime.now() + timedelta(minutes=auth.OTP_EXPIRE_MINUTES)
    
#     # Update user with OTP details
#     new_user.otp_code = otp
#     new_user.otp_verified = False
#     new_user.otp_attempts = 0
#     new_user.otp_expires_at = otp_expires
#     await db.commit()
#     await db.refresh(new_user)
    
#     # Send OTP email
#     await send_otp_email(new_user.email, otp)
    
#     return new_user
@app.post("/register", response_model=schemas.UnifiedLoginResponse)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    existing_user = await auth.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user but mark as not verified
    new_user = await crud.create_user(db, user, role="customer")
    
    # Generate and send OTP
    otp = str(random.randint(1000, 9999))
    # otp_expires = datetime.now() + timedelta(minutes=auth.OTP_EXPIRE_MINUTES)
    otp_expires = datetime.now(ZoneInfo("Australia/Sydney")) + timedelta(minutes=int(auth.OTP_EXPIRE_MINUTES))

    
    # Update user with OTP details
    new_user.otp_code = otp
    new_user.otp_verified = False
    new_user.otp_attempts = 0
    new_user.otp_expires_at = otp_expires
    await db.commit()
    await db.refresh(new_user)
    
    # Send OTP email
    await send_otp_email(new_user.email, otp)
    
    # Create tokens
    access_token = auth.create_access_token(data={"sub": new_user.email, "role": new_user.role})
    refresh_token = auth.create_refresh_token(data={"sub": new_user.email, "role": new_user.role})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "status": "true",
        "role": new_user.role,
        "message": "Registration successful. OTP sent.",
        "user": schemas.UserOut.model_validate(new_user, from_attributes=True)
    }


async def send_otp_email(email: str, otp: str):
    msg = MIMEText(f"""Your OTP verification code is: {otp}

This code will expire in {auth.OTP_EXPIRE_MINUTES} minutes.

If you didn't request this, please ignore this email.""")
    msg["Subject"] = "Your OTP Verification Code"
    msg["From"] = auth.EMAIL_SENDER
    msg["To"] = email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(auth.EMAIL_SENDER, auth.EMAIL_APP_PASSWORD)
            server.sendmail(auth.EMAIL_SENDER, [email], msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {str(e)}")
    return {"message": f"OTP sent to {email}"}
    
@app.post("/verify-otp", response_model=schemas.OTPResponse)
async def verify_otp(otp_data: schemas.OTPVerify, db: AsyncSession = Depends(get_db)):
    # Get user by email
    result = await db.execute(select(models.User).where(models.User.email == otp_data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    
    
    # Check if OTP is already verified
    if user.otp_verified:
        raise HTTPException(status_code=400, detail="OTP already verified")
    
    # Check if OTP attempts exceeded
    # Check if OTP attempts exceeded
    if user.otp_attempts >= auth.OTP_ATTEMPTS_LIMIT:
        await db.delete(user)
        await db.commit()
        raise HTTPException(status_code=400, detail="Email verification attempt exceeded. Please register again.")



    
    # Check if OTP expired
    if user.otp_expires_at and datetime.now(ZoneInfo("Australia/Sydney")) > user.otp_expires_at.astimezone(ZoneInfo("Australia/Sydney")):
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new OTP.")
    
    # Verify OTP
    if user.otp_code != otp_data.otp:
        # Increment attempt counter
        user.otp_attempts += 1
        await db.commit()
        await db.refresh(user)
        
        attempts_left = auth.OTP_ATTEMPTS_LIMIT - user.otp_attempts
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. {attempts_left} attempts remaining."
        )
    
    # Mark as verified
    user.otp_verified = True
    user.otp_code = None  # Clear the OTP after verification
    await db.commit()
    await db.refresh(user)
    
    return {"otp_verified": True, "otp_attempts": user.otp_attempts}



@app.post("/resend-otp", response_model=schemas.OTPResponse)
async def resend_otp(email: str = Body(..., embed=True), db: AsyncSession = Depends(get_db)):
    # Get user by email
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already verified
    if user.otp_verified:
        raise HTTPException(status_code=400, detail="OTP already verified")
    
    # Check if too many resend attempts
    if user.otp_attempts >= auth.OTP_ATTEMPTS_LIMIT:
        wait_time = auth.OTP_EXPIRE_MINUTES
        raise HTTPException(
            status_code=400,
            detail=f"Too many attempts. Please wait {wait_time} minutes before requesting a new OTP."
        )
    
    # Generate new OTP
    otp = str(random.randint(1000, 9999))  
    # otp_expires = datetime.now() + timedelta(minutes=auth.OTP_EXPIRE_MINUTES)
    otp_expires = datetime.now(ZoneInfo("Australia/Sydney")) + timedelta(minutes=int(auth.OTP_EXPIRE_MINUTES))


    # Update user with new OTP
    user.otp_code = otp
    user.otp_attempts = 0  # Reset attempts
    user.otp_expires_at = otp_expires
    await db.commit()
    await db.refresh(user)
    
    # Send new OTP email
    await send_otp_email(user.email, otp)
    
    return {"otp_verified": user.otp_verified, "otp_attempts": user.otp_attempts}

# @app.post("/logout")
# async def logout_user(
#     current_user: models.User = Depends(auth.get_current_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Logout current user by invalidating their token"""
#     # Verify OTP was completed first
#     if not current_user.otp_verified:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Complete OTP verification first"
#         )

#     # Invalidate token (implementation depends on your auth system)
#     # Example 1: Add to blacklist
#     # token = OAuth2PasswordBearer(tokenUrl="token")
#     # await auth.add_to_blacklist(token)
    
#     # Example 2: Clear user's auth token
#     current_user.access_token = None
#     await db.commit()

#     return {"message": "Successfully logged out"}

@app.post("/login", response_model=schemas.UnifiedLoginResponse)
async def unified_login(
    data: schemas.LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    #  check Admin table
    result = await db.execute(select(Admin).where(Admin.email == data.email))
    admin_user = result.scalar_one_or_none()
    if admin_user and await verify_password(data.password, admin_user.hashed_password):
        #  Generate both access and refresh tokens
        access_token = create_access_token(data={"sub": admin_user.email, "role": "admin"})
        refresh_token = create_refresh_token(data={"sub": admin_user.email, "role": "admin"})  

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,  
            "token_type": "bearer",
            "status": "true",
            "role": "admin",
            "message": "Login successful as admin",
            "user": schemas.AdminOut.model_validate(admin_user, from_attributes=True)
        }

    # check in Users table
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not await verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate both access and refresh tokens
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.email, "role": user.role})  

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,  
        "token_type": "bearer",
        "status": "true",
        "role": user.role,
        "message": f"Login successful as {user.role}",
        "user": schemas.UserOut.model_validate(user, from_attributes=True)
    }


@app.post("/refresh-token")
async def refresh_token(request: Request):
    data = await request.json()
    token = data.get("refresh_token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing refresh token")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("scope") != "refresh_token":
            raise HTTPException(status_code=401, detail="Invalid scope for token")

        email = payload.get("sub")
        role = payload.get("role")
        if not email or not role:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        new_access_token = create_access_token(data={"sub": email, "role": role})
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")



@app.get("/users/me/read", response_model=schemas.UserOut)
async def read_customer(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/logout", status_code=status.HTTP_200_OK)
async def logout(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
        if not email or not role:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "message": f"Logout successful for role '{role}' and user '{email}'. Thankyou!"
    }


@app.post("/admin/create-user", response_model=schemas.UserOut)
async def create_user_by_admin(
    user_data: schemas.CreateUserByAdmin,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    
    if user_data.role not in ["staff", "contractor"]:
        raise HTTPException(status_code=400, detail="Admins can only create staff or contractor accounts")

    existing_user = await auth.get_user_by_email_from_users_table(db, user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    return await crud.create_user(db, user=user_data, role=user_data.role)

@app.get("/admin/users", response_model=List[schemas.UserOut])
async def get_all_users(
    db: AsyncSession = Depends(database.get_db),
    current_admin: models.Admin = Depends(auth.get_current_admin)  # admin authentication
):
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users


# @app.get("/admin/users", response_model=List[schemas.UserOut])
# async def get_all_users(
#     db: AsyncSession = Depends(database.get_db),
#     current_admin: models.Admin = Depends(auth.get_current_admin)
# ):
#     if not current_admin:
#         return RedirectResponse(url="/login")
#     result = await db.execute(select(models.User))
#     return result.scalars().all()

@app.put("/user/update/{user_id}", response_model=schemas.UserOut)
async def update_any_user(
    user_id: int,  # Required path parameter (no default)
    user_update: schemas.UnifiedUserUpdate,  # Required request body (no default)
    db: AsyncSession = Depends(database.get_db),  # Dependency with default
    current_user: models.Admin = Depends(get_current_admin)  # Dependency with default
):
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user

@app.delete("/user/delete/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(database.get_db), current_user=Depends(get_current_admin)):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    print(f"User with ID {user_id} deleted successfully.")
    return JSONResponse(content={"message": "User deleted successfully"}, status_code=200)