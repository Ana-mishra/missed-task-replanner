from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.config import VAPID_PUBLIC_KEY
from app.database import get_db
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.notifications import (
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    VapidPublicKeyResponse,
)

router = APIRouter(prefix="/notifications/push", tags=["notifications"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def get_vapid_public_key(current_user: User = Depends(get_current_user)):
    """Return the VAPID public key the frontend needs for pushManager.subscribe()."""
    return VapidPublicKeyResponse(public_key=VAPID_PUBLIC_KEY or None)


@router.post("/subscribe", response_model=PushSubscriptionResponse)
def subscribe_push(
    request: PushSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update the current user's push subscription (idempotent).

    Ownership always comes from the authenticated JWT user; the frontend
    never supplies a user_id.
    """
    subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id)
        .first()
    )
    if subscription is None:
        subscription = PushSubscription(
            user_id=current_user.id,
            endpoint=request.endpoint,
            p256dh=request.keys.p256dh,
            auth=request.keys.auth,
        )
        db.add(subscription)
    else:
        subscription.endpoint = request.endpoint
        subscription.p256dh = request.keys.p256dh
        subscription.auth = request.keys.auth
    db.commit()
    db.refresh(subscription)
    return subscription


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_push(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the current user's push subscription (idempotent)."""
    subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id)
        .first()
    )
    if subscription is not None:
        db.delete(subscription)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
