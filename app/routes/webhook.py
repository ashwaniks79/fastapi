from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Subscription, User
from app.constants import TIER_FEATURES, STRIPE_PRICE_IDS
from datetime import datetime, timedelta
import stripe
import os

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
        event = stripe.Webhook.construct_event(payload, stripe_signature, endpoint_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        print("✅ Webhook received:", event["type"])
        session = event["data"]["object"]
        customer_email = session["customer_email"]
        subscription_id = session.get("subscription")

        # ✅ Get the subscription object from Stripe
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        price_id = stripe_sub['items']['data'][0]['price']['id']

        selected_plan = next((plan for plan, stripe_id in STRIPE_PRICE_IDS.items() if stripe_id == price_id), None)

        if not selected_plan:
            raise HTTPException(status_code=400, detail="Plan not matched")

        result = await db.execute(select(User).where(User.email == customer_email))
        user = result.scalar_one_or_none()

        if user:
            # Update User and Subscription
            user.subscription_plan = selected_plan

            result = await db.execute(select(Subscription).where(Subscription.subscription_id == user.id))
            subscription = result.scalar_one_or_none()

            if not subscription:
                subscription = Subscription(subscription_id=user.id)
                db.add(subscription)

            subscription.subscriptions_plan = selected_plan
            subscription.active = True
            subscription.start_date = datetime.utcnow()
            subscription.end_date = datetime.utcnow() + timedelta(days=30)
            subscription.features_enabled = TIER_FEATURES[selected_plan]
            subscription.projects_used = 0
            subscription.documents_uploaded = 0
            subscription.queries_made = 0
            subscription.trial_used = True

            await db.commit()

    return {"status": "success"}
