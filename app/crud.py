from sqlalchemy.ext.asyncio import AsyncSession
from . import models, schemas
from .auth import get_password_hash
from typing import Union
from app.odoo_services import  create_odoo_user
from datetime import datetime, timedelta
import logging
from .logging_model import RequestLog
from sqlalchemy.future import select
from .models import User
logger = logging.getLogger(__name__)

async def create_user(db: AsyncSession, user: Union[schemas.UserCreate, schemas.CreateUserByAdmin], role: str = "customer", user_id: str = None):
    hashed_password = await get_password_hash(user.password)
    db_user = models.User(
        id=user_id, 
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        company_name=user.company_name,
        phone_number=user.phone_number,
        country=user.country,
        timezone=user.timezone,
        subscription_plan=user.subscription_plan,
        role=role,
        trial_start_date=datetime.utcnow(),
        trial_expiry_date=datetime.utcnow() + timedelta(days=5),
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


# In crud.py add this function
async def create_request_log(db: AsyncSession, log_data: dict):
 
    try:
        db_log = RequestLog(
            timestamp=log_data["timestamp"],
            method=log_data["method"],
            path=log_data["path"],
            ip=log_data["ip"],
            status_code=log_data["status_code"],
            process_time_ms=log_data["process_time_ms"],
            user_agent=log_data["user_agent"],
            additional_data=log_data.get("additional_data")
        )
        db.add(db_log)
        await db.commit()
        await db.refresh(db_log)
        return db_log
    except Exception as e:
        await db.rollback()
        raise e
    
async def get_user_by_id(db: AsyncSession, user_id: str):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()