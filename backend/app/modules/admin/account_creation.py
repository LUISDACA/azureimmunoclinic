"""Result of creating an account and attempting its onboarding email."""

from dataclasses import dataclass

from app.core.email import EmailDeliveryStatus
from app.modules.users.models import User


@dataclass(frozen=True)
class AccountCreationResult:
    user: User
    email_delivery_status: EmailDeliveryStatus
