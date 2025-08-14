# app/routes/agent.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.auth import get_current_user

router = APIRouter()

@router.get("/status")
async def get_agent_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return {
        "message": "Agent system is online",
        "user": current_user.username,
        "plan": current_user.subscription_plan
    }
