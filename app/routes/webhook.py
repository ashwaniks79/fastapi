import select
from fastapi import APIRouter, Request, Header, HTTPException, Depends
import stripe
import os
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Subscription, User
from app.constants import TIER_FEATURES, STRIPE_PRICE_IDS
from datetime import datetime, timedelta
from sqlalchemy import update

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, endpoint_secret
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session["customer_email"]
        price_id = session["display_items"][0]["price"] if "display_items" in session else session["subscription"]

        selected_plan = None
        for plan, stripe_id in STRIPE_PRICE_IDS.items():
            if stripe_id == price_id:
                selected_plan = plan
                break

        if not selected_plan:
            raise HTTPException(status_code=400, detail="Plan not matched")

        result = await db.execute(select(Subscription).join(User).filter(User.email == customer_email))
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.subscriptions_plan = selected_plan
            subscription.active = True
            subscription.start_date = datetime.utcnow()
            subscription.end_date = datetime.utcnow() + timedelta(days=30)
            subscription.features_enabled = TIER_FEATURES[selected_plan]

            # Reset usage counters on upgrade
            subscription.projects_used = 0
            subscription.documents_uploaded = 0
            subscription.queries_made = 0

            # Mark trial as used if it was free before
            if selected_plan != "free":
                subscription.trial_used = True
            await db.commit()

    return {"status": "success"}
