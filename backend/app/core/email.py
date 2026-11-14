"""Production-ready email service using aiosmtplib and Jinja2 templates."""

import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import StrEnum
from html import unescape
from pathlib import Path
from urllib.parse import quote

import aiosmtplib
import anyio
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

# Setup Jinja2 environment
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"])
)


class EmailDeliveryStatus(StrEnum):
    """Provider acceptance, not proof of delivery to the recipient's inbox."""

    ACCEPTED = "accepted"
    DISABLED = "disabled"
    FAILED = "failed"


def _azure_communication_email_payload(
    subject: str,
    recipient: str,
    html_content: str,
) -> dict:
    """Build an ACS payload without putting recipient or content in logs."""
    plain_text = unescape(re.sub(r"<[^>]+>", " ", html_content))
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    return {
        "senderAddress": settings.AZURE_COMMUNICATION_EMAIL_SENDER,
        "recipients": {"to": [{"address": recipient}]},
        "content": {
            "subject": subject,
            "plainText": plain_text,
            "html": html_content,
        },
    }


def _send_azure_communication_email_sync(endpoint: str, message: dict) -> str:
    """Send through ACS using the App Service managed identity."""
    from azure.communication.email import EmailClient
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    client = None
    try:
        client = EmailClient(endpoint, credential)
        poller = client.begin_send(message)
        result = poller.result(timeout=settings.AZURE_COMMUNICATION_EMAIL_TIMEOUT_SECONDS)
        return str(result.get("status", ""))
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            credential.close()


async def _send_azure_communication_email(
    subject: str,
    recipient: str,
    html_content: str,
) -> EmailDeliveryStatus:
    endpoint = settings.AZURE_COMMUNICATION_EMAIL_ENDPOINT
    sender = settings.AZURE_COMMUNICATION_EMAIL_SENDER
    if not endpoint or not sender:
        logger.error(
            "Email provider configuration incomplete; transport=azure_communication_services"
        )
        return EmailDeliveryStatus.FAILED

    message = _azure_communication_email_payload(subject, recipient, html_content)
    try:
        status = await anyio.to_thread.run_sync(
            _send_azure_communication_email_sync,
            endpoint,
            message,
        )
        if status != "Succeeded":
            logger.error(
                "Email provider did not accept message; transport=azure_communication_services"
            )
            return EmailDeliveryStatus.FAILED
        logger.info("Email accepted; transport=azure_communication_services")
        return EmailDeliveryStatus.ACCEPTED
    except Exception as exc:
        logger.error(
            "Email provider failed; transport=azure_communication_services error=%s",
            type(exc).__name__,
        )
        return EmailDeliveryStatus.FAILED


async def send_email(
    subject: str,
    recipient: str,
    template_name: str,
    context: dict,
) -> EmailDeliveryStatus:
    """Send an HTML email using Azure Communication Services, SendGrid, or SMTP."""
    if not settings.EMAIL_ENABLED:
        logger.warning("Email disabled; template=%s", template_name)
        return EmailDeliveryStatus.DISABLED

    try:
        template = jinja_env.get_template(template_name)
        html_content = template.render(context)
    except Exception:
        logger.error("Email rendering failed; template=%s", template_name)
        return EmailDeliveryStatus.FAILED

    # ACS is selected explicitly by endpoint configuration and uses managed identity.
    # Do not fall through to a different transport if this configured provider fails.
    if settings.AZURE_COMMUNICATION_EMAIL_ENDPOINT or settings.AZURE_COMMUNICATION_EMAIL_SENDER:
        return await _send_azure_communication_email(
            subject,
            recipient,
            html_content,
        )

    # 1. Try SendGrid API first if key is present
    if settings.SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=settings.SMTP_FROM,
                to_emails=recipient,
                subject=subject,
                html_content=html_content,
            )
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            # Use anyio.to_thread since sendgrid is synchronous
            import anyio

            response = await anyio.to_thread.run_sync(sg.send, message)
            if not 200 <= response.status_code < 300:
                raise RuntimeError("Provider did not accept email")
            logger.info("Email accepted; transport=sendgrid template=%s", template_name)
            return EmailDeliveryStatus.ACCEPTED
        except ModuleNotFoundError:
            logger.error("SendGrid API key configured, but sendgrid is not installed")
        except Exception:
            logger.error("Email provider failed; transport=sendgrid template=%s", template_name)
            # Fallback to SMTP if SendGrid fails? For now just log and continue to SMTP

    # 2. Fallback to SMTP
    try:
        message = MIMEMultipart()
        message["From"] = settings.SMTP_FROM
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(html_content, "html"))

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
            use_tls=settings.SMTP_PORT == 465,
            start_tls=settings.SMTP_PORT == 587,
        )
        logger.info("Email accepted; transport=smtp template=%s", template_name)
        return EmailDeliveryStatus.ACCEPTED
    except Exception as exc:
        logger.error(
            "Email provider failed; transport=smtp template=%s error=%s",
            template_name,
            type(exc).__name__,
        )
        return EmailDeliveryStatus.FAILED


async def send_password_reset_email(email: str, token: str) -> EmailDeliveryStatus:
    """Send a password reset email with a secure token link."""
    reset_base = settings.PASSWORD_RESET_URL_BASE or settings.FRONTEND_URL
    if reset_base.startswith("immunoclinic://"):
        reset_base = settings.FRONTEND_URL
    reset_link = f"{reset_base.rstrip('/')}/reset-password?token={quote(token, safe='')}"

    return await send_email(
        subject="Restablece tu contraseña - ImmunoClinic",
        recipient=email,
        template_name="reset_password.html",
        context={"reset_link": reset_link},
    )


async def send_account_created_email(
    email: str,
    *,
    full_name: str,
    temporary_password: str,
) -> EmailDeliveryStatus:
    """Send account creation instructions to a new student."""
    return await send_email(
        subject="Tu cuenta de ImmunoClinic ha sido creada",
        recipient=email,
        template_name="account_created.html",
        context={
            "full_name": full_name,
            "email": email,
            "temporary_password": temporary_password,
            "app_name": settings.APP_NAME,
            "login_url": f"{settings.FRONTEND_URL.rstrip('/')}/login",
        },
    )


async def send_admin_account_created_email(
    email: str,
    *,
    full_name: str,
    temporary_password: str,
) -> EmailDeliveryStatus:
    """Send first-login instructions to a newly-created normal administrator."""
    return await send_email(
        subject="Tu cuenta de administrador de ImmunoClinic ha sido creada",
        recipient=email,
        template_name="admin_account_created.html",
        context={
            "full_name": full_name,
            "email": email,
            "temporary_password": temporary_password,
            "app_name": settings.APP_NAME,
            "login_url": f"{settings.FRONTEND_URL.rstrip('/')}/login",
        },
    )


async def send_vaccine_due_email(
    email: str,
    *,
    full_name: str,
    vaccine_name: str,
    dose_label: str,
    due_date: str,
    days_until_due: int,
) -> EmailDeliveryStatus:
    """Send an email reminder for a due vaccine dose."""
    if days_until_due == 0:
        subject = f"Tu vacuna vence hoy - {settings.APP_NAME}"
        due_text = "hoy"
    elif days_until_due == 1:
        subject = f"Tu vacuna vence en 1 dia - {settings.APP_NAME}"
        due_text = "en 1 dia"
    else:
        subject = f"Tu vacuna vence en {days_until_due} dias - {settings.APP_NAME}"
        due_text = f"en {days_until_due} dias"

    return await send_email(
        subject=subject,
        recipient=email,
        template_name="vaccine_due.html",
        context={
            "full_name": full_name,
            "vaccine_name": vaccine_name,
            "dose_label": dose_label,
            "due_date": due_date,
            "days_until_due": days_until_due,
            "due_text": due_text,
            "app_name": settings.APP_NAME,
        },
    )
