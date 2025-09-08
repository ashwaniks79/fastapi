# app/routes/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.utils.usage_checker import usage_summary
from app.models import User
from app.auth import get_current_user

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    usage = await usage_summary(current_user, db)
    return {
        "username": current_user.username,
        "plan": current_user.subscription_plan,
        "usage": usage
    }
