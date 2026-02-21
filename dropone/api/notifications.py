"""
DropOne — Push Notifications v2
Reads subscriptions from Supabase. No more in-memory loss on restart.
"""

import os
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("dropone.push")

try:
    from pywebpush import webpush, WebPushException
    HAS_WEBPUSH = True
except ImportError:
    HAS_WEBPUSH = False
    logger.warning("pywebpush not installed — push disabled")


@dataclass
class NotificationPayload:
    title: str
    body: str
    icon: str = "/icon-192.png"
    badge: str = "/badge-72.png"
    tag: str = ""
    url: str = "/"
    data: dict = field(default_factory=dict)


class PushManager:
    """Sends Web Push notifications. Reads subs from Supabase."""

    async def notify_sale(self, seller_email: str, product_name: str,
                          amount: float, margin: float, store_name: str, order_id: str):
        payload = NotificationPayload(
            title="💰 Nouvelle vente !",
            body=f"{product_name} — €{amount:.2f}\nTa marge : +€{margin:.2f}",
            tag=f"sale-{order_id}",
            url="/?tab=orders",
            data={"type": "sale", "order_id": order_id, "amount": amount, "margin": margin},
        )
        await self._send(seller_email, payload)

    async def notify_shipped(self, seller_email: str, order_id: str,
                             tracking_number: str, product_name: str):
        payload = NotificationPayload(
            title="🚚 Commande expédiée !",
            body=f"{product_name}\nTracking : {tracking_number}",
            tag=f"ship-{order_id}",
            url="/?tab=orders",
            data={"type": "shipped", "order_id": order_id, "tracking": tracking_number},
        )
        await self._send(seller_email, payload)

    async def notify_delivered(self, seller_email: str, order_id: str, product_name: str):
        payload = NotificationPayload(
            title="✅ Commande livrée !",
            body=f"{product_name} a été livrée avec succès.",
            tag=f"deliver-{order_id}",
            url="/?tab=orders",
            data={"type": "delivered", "order_id": order_id},
        )
        await self._send(seller_email, payload)

    async def _send(self, user_email: str, payload: NotificationPayload):
        """Send push to all subscriptions from Supabase."""
        if not HAS_WEBPUSH:
            logger.debug("pywebpush not available")
            return

        vapid_private = os.getenv("VAPID_PRIVATE_KEY", "")
        vapid_email = os.getenv("VAPID_EMAIL", "mailto:admin@dropone.app")
        if not vapid_private:
            logger.debug("VAPID keys not configured")
            return

        # Read subscriptions from Supabase
        import database as db
        subs = db.get_push_subscriptions(user_email)
        if not subs:
            logger.debug(f"No push subs for {user_email}")
            return

        notification_data = json.dumps({
            "title": payload.title,
            "body": payload.body,
            "icon": payload.icon,
            "badge": payload.badge,
            "tag": payload.tag,
            "data": {"url": payload.url, **payload.data},
        })

        for sub in subs:
            try:
                webpush(
                    subscription_info=sub,
                    data=notification_data,
                    vapid_private_key=vapid_private,
                    vapid_claims={"sub": vapid_email},
                    timeout=10,
                )
                logger.info(f"Push sent to {user_email}: {payload.title}")
            except WebPushException as e:
                logger.error(f"Push failed for {user_email}: {e}")
                if e.response and e.response.status_code in (404, 410):
                    db.remove_push_subscription(user_email)
            except Exception as e:
                logger.error(f"Push error: {e}")
