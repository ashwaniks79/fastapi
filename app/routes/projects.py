from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import stripe
from app.database import get_db
from app.models import User
from app.schemas import UpgradeSubscriptionRequest, UpgradeSubscriptionResponse
from app.constants import STRIPE_PRICE_IDS
from app.auth import get_current_user
import os

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: UpgradeSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ Get logged-in user
):
    try:
        tier = request.tier.lower()
        if tier not in STRIPE_PRICE_IDS:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[
                {
                    "price": STRIPE_PRICE_IDS[tier],
                    "quantity": 1
                }
            ],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=request.customer_email,
            metadata={  
                "plan": tier,
                "user_id": str(current_user.id)  # ✅ Inject user ID
            }
        )

        return {"checkout_url": session.url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
