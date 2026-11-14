"""Azure Blob adapter tests use in-memory clients and no Azure credentials."""

import re

import pytest
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.storage import azure_blob
from app.storage.azure_blob import AzureBlobStorageService
from app.storage.base import get_storage_service


class FakeDownloader:
    def __init__(self, payload: bytes):
        self.payload = payload

    def readall(self) -> bytes:
        return self.payload


class FakeBlobClient:
    def __init__(self):
        self.payload = None
        self.content_settings = None
        self.overwrite = None
        self.deleted = False

    def upload_blob(self, payload, *, overwrite, content_settings):
        self.payload = payload
        self.overwrite = overwrite
        self.content_settings = content_settings

    def download_blob(self):
        if self.payload is None:
            raise azure_blob.ResourceNotFoundError("not found")
        return FakeDownloader(self.payload)

    def delete_blob(self):
        self.deleted = True
        self.payload = None


class FakeContainerClient:
    def __init__(self):
        self.blobs = {}

    def get_blob_client(self, key):
        return self.blobs.setdefault(key, FakeBlobClient())


class FakeServiceClient:
    def __init__(self):
        self.container = FakeContainerClient()

    def get_container_client(self, name):
        assert name == "synthetic-evidence"
        return self.container

    def close(self):
        pass


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONTAINER", "synthetic-evidence")
    return AzureBlobStorageService(service_client=FakeServiceClient())


@pytest.mark.asyncio
async def test_upload_download_delete_and_private_url_contract(service):
    key = await service.upload(b"synthetic-file", "evidence.pdf", "application/pdf")

    assert re.fullmatch(r"\d{4}/\d{2}/[0-9a-f]{32}\.pdf", key)
    assert await service.get_url(key) == key
    assert await service.download(key) == b"synthetic-file"

    blob = service._container.get_blob_client(key)
    assert blob.overwrite is False
    assert blob.content_settings.content_type == "application/pdf"

    await service.delete(key)
    assert blob.deleted is True


@pytest.mark.asyncio
async def test_download_missing_blob_maps_to_file_not_found(service):
    with pytest.raises(FileNotFoundError):
        await service.download("missing/synthetic-file.pdf")


def test_requires_account_url_and_container_without_network_or_credentials(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_STORAGE_ACCOUNT_URL", None)
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONTAINER", "synthetic-evidence")

    with pytest.raises(BadRequestException, match="AZURE_STORAGE_ACCOUNT_URL"):
        AzureBlobStorageService()

    monkeypatch.setattr(settings, "AZURE_STORAGE_ACCOUNT_URL", "https://example.invalid")
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONTAINER", None)
    with pytest.raises(BadRequestException, match="AZURE_STORAGE_CONTAINER"):
        AzureBlobStorageService()


def test_factory_does_not_silently_fall_back_for_unknown_storage_type(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_TYPE", "azure_blob_typo")

    with pytest.raises(BadRequestException, match="STORAGE_TYPE"):
        get_storage_service()
