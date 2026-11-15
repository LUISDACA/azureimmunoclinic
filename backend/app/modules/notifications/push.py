"""Firebase Cloud Messaging push delivery."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from functools import lru_cache

import firebase_admin
from app.core.config import settings
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)


def safe_fcm_error_code(error: Exception | None) -> str:
    """Return a short error identifier without logging payloads or tokens."""
    if error is None:
        return "unknown"
    code = getattr(error, "code", None)
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-"
    if (
        isinstance(code, str)
        and 0 < len(code) <= 100
        and all(character in allowed for character in code)
    ):
        return code
    return type(error).__name__


@lru_cache(maxsize=1)
def _firebase_app() -> firebase_admin.App | None:
    if not settings.FCM_ENABLED:
        logger.info("FCM dispatch skipped: sender is disabled")
        return None

    if firebase_admin._apps:
        return firebase_admin.get_app()

    if settings.FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
    elif settings.FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    else:
        logger.error("FCM dispatch unavailable: Firebase credentials are not configured")
        return None

    return firebase_admin.initialize_app(cred)


class PushNotificationSender:
    """Sends push notifications through Firebase when configured."""

    async def send_to_tokens(
        self,
        tokens: list[str],
        *,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> None:
        if not tokens:
            logger.info("FCM dispatch skipped: no active device tokens")
            return
        app = _firebase_app()
        if app is None:
            logger.error("FCM dispatch skipped: Firebase Admin app is unavailable")
            return

        payload = {"event": "updates_available"}
        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(
                title="ImmunoClinic",
                body="Tienes una actualización. Abre la aplicación para consultarla.",
            ),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="immuno_clinic_updates",
                ),
            ),
            data=payload,
        )
        response = await asyncio.to_thread(
            messaging.send_each_for_multicast,
            message,
            app=app,
        )
        failure_codes = Counter(
            safe_fcm_error_code(item.exception) for item in response.responses if not item.success
        )
        logger.info(
            "FCM multicast completed: targets=%d successes=%d failures=%d failure_codes=%s",
            len(tokens),
            response.success_count,
            response.failure_count,
            dict(failure_codes),
        )
