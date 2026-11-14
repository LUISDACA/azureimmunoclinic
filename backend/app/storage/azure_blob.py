"""Private Azure Blob storage backed by the application's managed identity."""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.storage.base import StorageService


class AzureBlobStorageService(StorageService):
    """Store files in a private Blob container using managed identity."""

    def __init__(self, service_client=None):
        if service_client is not None:
            self._credential = None
            self._service_client = service_client
        else:
            if not settings.AZURE_STORAGE_ACCOUNT_URL:
                raise BadRequestException(
                    "AZURE_STORAGE_ACCOUNT_URL must be configured for Azure Blob storage"
                )
            if not settings.AZURE_STORAGE_CONTAINER:
                raise BadRequestException(
                    "AZURE_STORAGE_CONTAINER must be configured for Azure Blob storage"
                )
            self._credential = DefaultAzureCredential()
            self._service_client = BlobServiceClient(
                account_url=settings.AZURE_STORAGE_ACCOUNT_URL,
                credential=self._credential,
            )

        self._container = self._service_client.get_container_client(
            settings.AZURE_STORAGE_CONTAINER
        )

    async def upload(self, file_data: bytes, filename: str, content_type: str) -> str:
        ext = Path(filename).suffix
        date_folder = datetime.now(timezone.utc).strftime("%Y/%m")
        key = f"{date_folder}/{uuid.uuid4().hex}{ext}"
        blob = self._container.get_blob_client(key)

        await asyncio.to_thread(
            blob.upload_blob,
            file_data,
            overwrite=False,
            content_settings=ContentSettings(content_type=content_type),
        )
        return key

    async def get_url(self, stored_path: str) -> str:
        """Return the opaque key; downloads remain behind authorized API routes."""
        return stored_path

    async def delete(self, stored_path: str) -> None:
        blob = self._container.get_blob_client(stored_path)
        await asyncio.to_thread(blob.delete_blob)

    async def download(self, stored_path: str) -> bytes:
        blob = self._container.get_blob_client(stored_path)
        try:
            downloader = await asyncio.to_thread(blob.download_blob)
            return await asyncio.to_thread(downloader.readall)
        except ResourceNotFoundError as exc:
            raise FileNotFoundError(stored_path) from exc

    async def close(self) -> None:
        """Release SDK resources when the service is held for application life."""
        await asyncio.to_thread(self._service_client.close)
        if self._credential is not None:
            await asyncio.to_thread(self._credential.close)
