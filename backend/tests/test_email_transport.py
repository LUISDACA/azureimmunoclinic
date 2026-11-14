"""Real local SMTP; no external mail credentials or delivery assumed."""

import pytest
from app.core.config import settings
from app.core.email import (
    EmailDeliveryStatus,
    _azure_communication_email_payload,
    send_account_created_email,
    send_admin_account_created_email,
    send_email,
    send_password_reset_email,
    send_vaccine_due_email,
)


@pytest.mark.asyncio
async def test_account_and_operational_flows_reach_local_smtp(smtp_inbox):
    assert (
        await send_account_created_email(
            "synthetic@example.com",
            full_name="Synthetic <script>name</script>",
            temporary_password="SyntheticOnly123!",
        )
        == EmailDeliveryStatus.ACCEPTED
    )
    assert (
        await send_admin_account_created_email(
            "synthetic-admin@example.com",
            full_name="Synthetic <script>admin</script>",
            temporary_password="SyntheticAdminOnly123!",
        )
        == EmailDeliveryStatus.ACCEPTED
    )
    assert (
        await send_password_reset_email("synthetic@example.com", "synthetic-reset-only")
        == EmailDeliveryStatus.ACCEPTED
    )
    assert (
        await send_vaccine_due_email(
            "synthetic@example.com",
            full_name="Synthetic",
            vaccine_name="Synthetic vaccine",
            dose_label="First",
            due_date="01/01/2027",
            days_until_due=1,
        )
        == EmailDeliveryStatus.ACCEPTED
    )
    assert len(smtp_inbox.messages) == 4
    bodies = [
        message.get_body(preferencelist=("html",)).get_content() for message in smtp_inbox.messages
    ]
    assert "SyntheticOnly123!" in bodies[0]
    assert 'href="https://app.example.com/login"' in bodies[0]
    assert "https://app.example.com/login" in bodies[0]
    assert "<script>name</script>" not in bodies[0]
    assert "&lt;script&gt;" in bodies[0]
    assert "SyntheticAdminOnly123!" in bodies[1]
    assert 'href="https://app.example.com/login"' in bodies[1]
    assert "https://app.example.com/login" in bodies[1]
    assert "&lt;script&gt;admin&lt;/script&gt;" in bodies[1]
    assert "cambiar la contraseña en tu primer inicio" in bodies[1]
    assert "https://app.example.com/reset-password?token=synthetic-reset-only" in bodies[2]
    assert "Synthetic vaccine" in bodies[3]


@pytest.mark.asyncio
async def test_disabled_and_rejected_mail_do_not_log_tokens_or_recipient(
    smtp_inbox, monkeypatch, caplog
):
    token = "synthetic-reset-do-not-log"
    recipient = "synthetic-private@example.com"
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    assert await send_password_reset_email(recipient, token) == EmailDeliveryStatus.DISABLED
    assert (
        await send_account_created_email(
            recipient,
            full_name="Synthetic",
            temporary_password="SyntheticStudentOnly123!",
        )
        == EmailDeliveryStatus.DISABLED
    )
    assert (
        await send_admin_account_created_email(
            recipient,
            full_name="Synthetic Admin",
            temporary_password="SyntheticAdminOnly123!",
        )
        == EmailDeliveryStatus.DISABLED
    )
    assert smtp_inbox.messages == []
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    smtp_inbox.reject = True
    assert await send_password_reset_email(recipient, token) == EmailDeliveryStatus.FAILED
    assert smtp_inbox.messages == []
    assert token not in caplog.text and token[:8] not in caplog.text
    assert recipient not in caplog.text


@pytest.mark.asyncio
async def test_transport_failure_and_missing_template_return_failed(smtp_inbox, monkeypatch):
    from app.core.email import send_email

    assert (
        await send_email("Synthetic", "synthetic@example.com", "missing.html", {})
        == EmailDeliveryStatus.FAILED
    )
    monkeypatch.setattr(settings, "SMTP_PORT", 1)
    assert (
        await send_password_reset_email("synthetic@example.com", "synthetic-reset")
        == EmailDeliveryStatus.FAILED
    )


@pytest.mark.asyncio
async def test_sendgrid_failure_falls_back_to_local_smtp_without_logging_payload(
    smtp_inbox, monkeypatch, caplog
):
    import sendgrid

    class FailingProvider:
        def __init__(self, key):
            pass

        def send(self, message):
            raise RuntimeError("synthetic-provider-sensitive-canary")

    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "synthetic-no-real-key")
    monkeypatch.setattr(sendgrid, "SendGridAPIClient", FailingProvider)
    assert (
        await send_password_reset_email("synthetic@example.com", "synthetic-reset")
        == EmailDeliveryStatus.ACCEPTED
    )
    assert len(smtp_inbox.messages) == 1
    assert "synthetic-provider-sensitive-canary" not in caplog.text


def test_azure_communication_email_payload_has_expected_contract(monkeypatch):
    monkeypatch.setattr(
        settings, "AZURE_COMMUNICATION_EMAIL_SENDER", "DoNotReply@synthetic.azurecomm.net"
    )
    payload = _azure_communication_email_payload(
        "Synthetic subject",
        "synthetic-recipient@example.test",
        '<p>Hello &amp; welcome</p><p><a href="https://app.example.com/login">'
        "https://app.example.com/login</a></p>",
    )

    assert payload == {
        "senderAddress": "DoNotReply@synthetic.azurecomm.net",
        "recipients": {"to": [{"address": "synthetic-recipient@example.test"}]},
        "content": {
            "subject": "Synthetic subject",
            "plainText": "Hello & welcome https://app.example.com/login",
            "html": '<p>Hello &amp; welcome</p><p><a href="https://app.example.com/login">'
            "https://app.example.com/login</a></p>",
        },
    }


def test_azure_communication_email_sync_uses_sdk_and_closes_identity(monkeypatch):
    from app.core import email
    from azure import identity
    from azure.communication import email as azure_email

    calls = []

    class FakeCredential:
        def close(self):
            calls.append(("credential.close",))

    class FakePoller:
        def result(self, *, timeout):
            calls.append(("result", timeout))
            return {"status": "Succeeded"}

    class FakeEmailClient:
        def __init__(self, endpoint, credential):
            calls.append(("client.init", endpoint, credential))

        def begin_send(self, message):
            calls.append(("begin_send", message))
            return FakePoller()

        def close(self):
            calls.append(("client.close",))

    monkeypatch.setattr(identity, "DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(azure_email, "EmailClient", FakeEmailClient)
    monkeypatch.setattr(settings, "AZURE_COMMUNICATION_EMAIL_TIMEOUT_SECONDS", 12.0)

    result = email._send_azure_communication_email_sync(
        "https://synthetic.communication.azure.com",
        {"senderAddress": "noreply@synthetic.azurecomm.net"},
    )

    assert result == "Succeeded"
    assert calls[0][:2] == ("client.init", "https://synthetic.communication.azure.com")
    assert isinstance(calls[0][2], FakeCredential)
    assert calls[1] == ("begin_send", {"senderAddress": "noreply@synthetic.azurecomm.net"})
    assert calls[2] == ("result", 12.0)
    assert calls[3:] == [("client.close",), ("credential.close",)]


@pytest.mark.asyncio
async def test_azure_communication_email_uses_configured_transport_without_smtp_fallback(
    smtp_inbox, monkeypatch, caplog
):
    from app.core import email

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "AZURE_COMMUNICATION_EMAIL_ENDPOINT",
        "https://synthetic.communication.azure.com",
    )
    monkeypatch.setattr(
        settings,
        "AZURE_COMMUNICATION_EMAIL_SENDER",
        "DoNotReply@synthetic.azurecomm.net",
    )
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "synthetic-unused-key")
    calls = []

    async def failed_acs(subject, recipient, html_content):
        calls.append((subject, recipient, html_content))
        return EmailDeliveryStatus.FAILED

    monkeypatch.setattr(email, "_send_azure_communication_email", failed_acs)
    status = await send_email(
        "Synthetic subject",
        "synthetic-recipient@example.test",
        "account_created.html",
        {
            "full_name": "Synthetic User",
            "email": "synthetic-recipient@example.test",
            "temporary_password": "SyntheticOnly123!",
            "app_name": "Synthetic App",
        },
    )

    assert status == EmailDeliveryStatus.FAILED
    assert len(calls) == 1
    assert smtp_inbox.messages == []
    assert "synthetic-recipient@example.test" not in caplog.text
    assert "SyntheticOnly123!" not in caplog.text


@pytest.mark.asyncio
async def test_azure_communication_email_adapter_reports_provider_acceptance(monkeypatch):
    from app.core import email

    monkeypatch.setattr(
        settings, "AZURE_COMMUNICATION_EMAIL_ENDPOINT", "https://synthetic.communication.azure.com"
    )
    monkeypatch.setattr(
        settings, "AZURE_COMMUNICATION_EMAIL_SENDER", "DoNotReply@synthetic.azurecomm.net"
    )
    monkeypatch.setattr(settings, "AZURE_COMMUNICATION_EMAIL_TIMEOUT_SECONDS", 5.0)
    captured = []

    def sent(endpoint, message):
        captured.append((endpoint, message))
        return "Succeeded"

    async def run_sync(callback, endpoint, message):
        return callback(endpoint, message)

    monkeypatch.setattr(email, "_send_azure_communication_email_sync", sent)
    monkeypatch.setattr(email.anyio.to_thread, "run_sync", run_sync)

    result = await email._send_azure_communication_email(
        "Synthetic",
        "synthetic@example.test",
        "<p>Safe test</p>",
    )

    assert result == EmailDeliveryStatus.ACCEPTED
    assert captured == [
        (
            "https://synthetic.communication.azure.com",
            {
                "senderAddress": "DoNotReply@synthetic.azurecomm.net",
                "recipients": {"to": [{"address": "synthetic@example.test"}]},
                "content": {
                    "subject": "Synthetic",
                    "plainText": "Safe test",
                    "html": "<p>Safe test</p>",
                },
            },
        )
    ]
