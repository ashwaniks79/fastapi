# app/odoo_routes.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import crud
from app.odoo_services import create_odoo_user

router = APIRouter()

@router.post("/odoo/sync-user/{user_id}")
async def sync_user_to_odoo(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_id(db, user_id)
    print("User fetched from DB:", user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        partner_id = create_odoo_user(user)
        return {"partner_id": partner_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Odoo sync failed: {str(e)}")
