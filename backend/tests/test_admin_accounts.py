from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.common.enums import Role
from app.core.email import EmailDeliveryStatus
from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.admin.accounts.service import AdminAccountService
from app.modules.admin.schemas import CreateAdminRequest


class _FakeRepo:
    def __init__(self) -> None:
        self.user = None
        self.profile = None

    async def get_by_email(self, _email):
        return None

    async def create_user(self, user):
        user.id = uuid4()
        self.user = user
        return user

    async def create_profile(self, profile):
        self.profile = profile
        self.user.profile = profile
        return profile

    async def get_by_id(self, _user_id):
        return self.user


class _FakeAudit:
    def __init__(self) -> None:
        self.details = None

    async def log(self, **kwargs):
        self.details = kwargs["details"]


class _FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self):
        self.commits += 1
        return None


class TestAdminAccountService:
    def test_non_app_admin_is_rejected(self) -> None:
        service = AdminAccountService.__new__(AdminAccountService)
        user = SimpleNamespace(role=Role.ADMIN)

        with pytest.raises(ForbiddenException):
            service._ensure_app_admin(user, "crear administradores")

    @pytest.mark.asyncio
    async def test_app_admin_cannot_delete_own_account(self) -> None:
        service = AdminAccountService.__new__(AdminAccountService)
        service.user_repo = SimpleNamespace()
        service.audit = SimpleNamespace()
        service.db = SimpleNamespace()
        app_admin_id = uuid4()
        app_admin = SimpleNamespace(id=app_admin_id, role=Role.APP_ADMIN)

        with pytest.raises(BadRequestException):
            await service.delete_admin(app_admin, app_admin_id)

    @pytest.mark.asyncio
    async def test_create_admin_sends_temporary_credentials_and_requires_change(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = AdminAccountService.__new__(AdminAccountService)
        service.user_repo = _FakeRepo()
        service.audit = _FakeAudit()
        service.db = _FakeDb()
        app_admin = SimpleNamespace(id=uuid4(), role=Role.APP_ADMIN)
        sent = []

        async def fake_admin_email(email: str, **context):
            sent.append((email, context))
            return EmailDeliveryStatus.ACCEPTED

        monkeypatch.setattr(
            "app.modules.admin.accounts.service.send_admin_account_created_email",
            fake_admin_email,
        )
        password = "SyntheticAdmin123!"

        result = await service.create_admin(
            app_admin,
            CreateAdminRequest(
                email="normal.admin@test.com",
                password=password,
                first_name="Ana",
                last_name="Perez",
                job_title="Coordinadora",
                program="Medicina",
                campus="Cali",
            ),
        )
        admin = result.user
        assert result.email_delivery_status == EmailDeliveryStatus.ACCEPTED

        assert admin.profile.first_name == "Ana"
        assert admin.profile.last_name == "Perez"
        assert admin.profile.job_title == "Coordinadora"
        assert admin.must_change_password is True
        assert service.audit.details["job_title"] == "Coordinadora"
        assert "password" not in service.audit.details
        assert len(sent) == 1
        email, context = sent[0]
        assert email == admin.email
        assert context == {
            "full_name": "Ana Perez",
            "temporary_password": password,
        }

        from app.core.security import verify_password

        assert verify_password(password, admin.hashed_password)

    @pytest.mark.asyncio
    async def test_create_admin_generates_credential_when_client_omits_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = AdminAccountService.__new__(AdminAccountService)
        service.user_repo = _FakeRepo()
        service.audit = _FakeAudit()
        service.db = _FakeDb()
        app_admin = SimpleNamespace(id=uuid4(), role=Role.APP_ADMIN)
        sent = []
        monkeypatch.setattr(
            "app.modules.admin.accounts.service.secrets.token_urlsafe",
            lambda _length: "SyntheticGeneratedCredential",
        )

        async def fake_admin_email(email: str, **context):
            sent.append((email, context))
            return EmailDeliveryStatus.ACCEPTED

        monkeypatch.setattr(
            "app.modules.admin.accounts.service.send_admin_account_created_email",
            fake_admin_email,
        )

        result = await service.create_admin(
            app_admin,
            CreateAdminRequest(
                email="generated.admin@test.com",
                program="Medicina",
                campus="Cali",
            ),
        )
        admin = result.user
        assert result.email_delivery_status == EmailDeliveryStatus.ACCEPTED

        generated_password = "SyntheticGeneratedCredentialAa1!"
        from app.core.security import verify_password

        assert verify_password(generated_password, admin.hashed_password)
        assert admin.must_change_password is True
        assert sent == [
            (
                admin.email,
                {
                    "full_name": "generated.admin",
                    "temporary_password": generated_password,
                },
            )
        ]
        from app.modules.users.schemas import UserResponse

        assert "hashed_password" not in UserResponse.model_fields
        assert "password" not in UserResponse.model_fields

    @pytest.mark.asyncio
    async def test_admin_account_creation_survives_disabled_email(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = AdminAccountService.__new__(AdminAccountService)
        service.user_repo = _FakeRepo()
        service.audit = _FakeAudit()
        service.db = _FakeDb()
        app_admin = SimpleNamespace(id=uuid4(), role=Role.APP_ADMIN)

        async def disabled_email(*_args, **_kwargs):
            return EmailDeliveryStatus.DISABLED

        monkeypatch.setattr(
            "app.modules.admin.accounts.service.send_admin_account_created_email",
            disabled_email,
        )
        result = await service.create_admin(
            app_admin,
            CreateAdminRequest(
                email="normal.admin@test.com",
                password="SyntheticAdmin123!",
                program="Medicina",
                campus="Cali",
            ),
        )
        admin = result.user

        assert admin.email == "normal.admin@test.com"
        assert result.email_delivery_status == EmailDeliveryStatus.DISABLED
        assert service.db.commits == 1
