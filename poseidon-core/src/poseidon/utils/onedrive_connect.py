"""Helpers for authenticating and querying OneDrive/SharePoint via Microsoft Graph."""

from __future__ import annotations

import logging

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator, List, Optional

import requests
from typing import Any

try:  # pragma: no cover - simple import guard
    from msal import ConfidentialClientApplication
except ModuleNotFoundError:  # provide helpful guidance if msal is missing
    ConfidentialClientApplication = Any  # type: ignore[assignment]
    _MSAL_IMPORT_ERROR = True
else:
    _MSAL_IMPORT_ERROR = False

from poseidon.utils.logger_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class OneDriveAuthError(RuntimeError):
    """Raised when Graph authentication fails."""


class OneDriveAPIError(RuntimeError):
    """Raised when Graph API requests fail."""


@dataclass(frozen=True)
class GraphConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    authority: str = "https://login.microsoftonline.com"
    scope: str = "https://graph.microsoft.com/.default"

    @classmethod
    def from_env(cls) -> "GraphConfig":
        try:
            tenant = os.environ["AZURE_TENANT_ID"]
            client = os.environ["AZURE_CLIENT_ID"]
            secret = os.environ["AZURE_CLIENT_SECRET"]
        except KeyError as missing:
            raise OneDriveAuthError(f"Missing Azure credential: {missing.args[0]}")
        return cls(tenant_id=tenant, client_id=client, client_secret=secret)


@lru_cache(maxsize=1)
def _build_app(config: GraphConfig) -> ConfidentialClientApplication:
    if _MSAL_IMPORT_ERROR:
        raise OneDriveAuthError(
            "Microsoft Authentication Library (msal) is not installed. "
            "Install msal==1.28.0 or set POSEIDON_DISABLE_ONEDRIVE=1 to disable OneDrive features."
        )
    return ConfidentialClientApplication(
        config.client_id,
        authority=f"{config.authority}/{config.tenant_id}",
        client_credential=config.client_secret,
    )


@lru_cache(maxsize=1)
def acquire_token() -> str:
    config = GraphConfig.from_env()
    app = _build_app(config)
    result = app.acquire_token_for_client(scopes=[config.scope])
    if "access_token" not in result:
        logger.error("Graph token acquisition failed: %s", result)
        raise OneDriveAuthError("Failed to acquire Graph access token")
    return result["access_token"]


def graph_request(method: str, url: str, *, timeout: int = 30, **kwargs) -> requests.Response:
    token = acquire_token()
    headers = kwargs.setdefault("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    response = requests.request(method, url, timeout=timeout, **kwargs)
    if not response.ok:
        logger.warning("Graph request failed [%s %s]: %s", method, url, response.text)
        raise OneDriveAPIError(f"Graph request failed: {response.status_code}")
    return response


@dataclass
class SharePointSite:
    hostname: str
    site_path: str

    @property
    def site_url(self) -> str:
        return f"https://graph.microsoft.com/v1.0/sites/{self.hostname}:{self.site_path}"

    def get_site_id(self) -> str:
        response = graph_request("GET", self.site_url)
        data = response.json()
        return data["id"]

    def list_document_libraries(self) -> List[dict]:
        site_id = self.get_site_id()
        response = graph_request(
            "GET",
            f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives",
        )
        return response.json().get("value", [])


def iter_drive_pdfs(drive_id: str) -> Iterator[dict]:
    response = graph_request(
        "GET",
        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/search(q='.pdf')",
    )
    yield from response.json().get("value", [])


def download_file(download_url: str, target_path: str) -> None:
    with requests.get(download_url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(target_path, "wb") as handle:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)


def get_onedrive_client() -> tuple[str, Optional[str]]:
    """Retained for backward compatibility with tooling that expects a token."""
    token = acquire_token()
    base_path = os.getenv("ONEDRIVE_BASE_PATH")
    return token, base_path


__all__ = [
    "OneDriveAuthError",
    "OneDriveAPIError",
    "GraphConfig",
    "SharePointSite",
    "acquire_token",
    "graph_request",
    "iter_drive_pdfs",
    "download_file",
    "get_onedrive_client",
]
