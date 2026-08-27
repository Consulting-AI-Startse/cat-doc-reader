from abc import ABC, abstractmethod

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from shared.config import settings


class BlobStorage(ABC):
    @abstractmethod
    def upload(self, path: str, data: bytes) -> str:
        ...

    @abstractmethod
    def download(self, path: str) -> bytes:
        ...

    @abstractmethod
    def get_url(self, path: str) -> str:
        ...

    def ensure_container(self) -> None:
        pass


class AzuriteStorage(BlobStorage):
    def __init__(self, connection_string: str | None = None, container: str | None = None) -> None:
        self._client = BlobServiceClient.from_connection_string(
            connection_string or settings.azure_storage_connection_string
        )
        self._container = container or settings.blob_container_name

    def ensure_container(self) -> None:
        try:
            self._client.create_container(self._container)
        except ResourceExistsError:
            pass

    def upload(self, path: str, data: bytes) -> str:
        self._client.get_blob_client(self._container, path).upload_blob(data, overwrite=True)
        return path

    def download(self, path: str) -> bytes:
        return self._client.get_blob_client(self._container, path).download_blob().readall()

    def get_url(self, path: str) -> str:
        return self._client.get_blob_client(self._container, path).url


class AzureBlobStorage(BlobStorage):
    def __init__(self, account_url: str | None = None, container: str | None = None) -> None:
        from azure.identity import DefaultAzureCredential

        self._client = BlobServiceClient(
            account_url or settings.azure_storage_account_url,
            credential=DefaultAzureCredential(),
        )
        self._container = container or settings.blob_container_name

    def upload(self, path: str, data: bytes) -> str:
        self._client.get_blob_client(self._container, path).upload_blob(data, overwrite=True)
        return path

    def download(self, path: str) -> bytes:
        return self._client.get_blob_client(self._container, path).download_blob().readall()

    def get_url(self, path: str) -> str:
        return self._client.get_blob_client(self._container, path).url


def get_blob_storage() -> BlobStorage:
    if settings.azure_storage_account_url:
        return AzureBlobStorage()
    return AzuriteStorage()
