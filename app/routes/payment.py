from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import stripe
from app.database import get_db
from app.models import User
from app.schemas import UpgradeSubscriptionRequest, UpgradeSubscriptionResponse
from app.constants import STRIPE_PRICE_IDS
import os

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: UpgradeSubscriptionRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        if request.tier.lower() not in STRIPE_PRICE_IDS:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[
                {
                    "price": STRIPE_PRICE_IDS[request.tier.lower()],
                    "quantity": 1
                }
            ],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=request.customer_email,
        )

        return {"checkout_url": session.url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
