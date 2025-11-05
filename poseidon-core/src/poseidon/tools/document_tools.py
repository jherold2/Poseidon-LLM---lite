"""Utilities for discovering, downloading, and retrieving SOP documents."""

from __future__ import annotations

import logging

import json
import os
from datetime import datetime
from functools import lru_cache
from typing import Dict, Iterable, List, Optional

import requests
from langchain_core.tools import Tool

from poseidon.utils.db_connect import run as db_run
from poseidon.utils.logger_setup import setup_logging
from poseidon.utils.onedrive_connect import (
    OneDriveAPIError,
    OneDriveAuthError,
    SharePointSite,
    download_file,
    graph_request,
    iter_drive_pdfs,
)

SOP_FOLDER_NAME = os.getenv("SOP_FOLDER_NAME", "CDA SOP Master")
SOP_SITE_HOSTNAME = os.getenv(
    "SOP_SITE_HOSTNAME",
    os.getenv("ONEDRIVE_SITE_HOSTNAME", "cdaseafood.sharepoint.com"),
)
SOP_SITE_PATH = os.getenv(
    "SOP_SITE_PATH",
    os.getenv("ONEDRIVE_SITE_PATH", "/sites/SOPCDA"),
)
SOP_LIBRARY_NAME = os.getenv("SOP_LIBRARY_NAME")
SOP_EMBED_MODEL = os.getenv("SOP_EMBED_MODEL", "text-embedding-3-large")
SOP_EMBED_TABLE = os.getenv("SOP_EMBED_TABLE", "analytics_semantic.sop_embeddings")

try:  # pragma: no cover - optional dependency for embeddings
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

setup_logging()
logger = logging.getLogger(__name__)


def _is_sop_folder(path: Optional[str]) -> bool:
    if not path:
        return False
    needle = SOP_FOLDER_NAME.lower()
    components = [segment for segment in path.lower().split(":")[-1].split("/") if segment]
    return needle in components


@lru_cache(maxsize=1)
def _get_site() -> SharePointSite:
    return SharePointSite(hostname=SOP_SITE_HOSTNAME, site_path=SOP_SITE_PATH)


def _resolve_download_url(drive_id: str, item_id: str) -> Optional[str]:
    try:
        response = graph_request(
            "GET",
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}",
            params={"$select": "@microsoft.graph.downloadUrl"},
        )
        payload = response.json()
        return payload.get("@microsoft.graph.downloadUrl")
    except OneDriveAPIError as exc:
        logger.error("Failed to resolve download URL for %s/%s: %s", drive_id, item_id, exc)
        return None


def _iter_sop_items() -> Iterable[Dict[str, object]]:
    try:
        site = _get_site()
        drives = site.list_document_libraries()
    except (OneDriveAuthError, OneDriveAPIError) as exc:
        logger.error("Unable to list SOP drives: %s", exc)
        raise

    for drive in drives:
        if SOP_LIBRARY_NAME and drive.get("name") != SOP_LIBRARY_NAME:
            continue
        drive_id = drive.get("id")
        if not drive_id:
            continue
        try:
            for item in iter_drive_pdfs(drive_id):
                file_info = item.get("file", {})
                if file_info.get("mimeType") != "application/pdf":
                    continue
                parent_path = item.get("parentReference", {}).get("path")
                if not _is_sop_folder(parent_path):
                    continue
                normalized = {
                    "drive_id": drive_id,
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "web_url": item.get("webUrl"),
                    "download_url": item.get("@microsoft.graph.downloadUrl"),
                    "last_modified": item.get("lastModifiedDateTime"),
                    "size": item.get("size"),
                    "path": parent_path,
                }
                if normalized["id"] and normalized["name"]:
                    yield normalized
        except OneDriveAPIError as exc:
            logger.warning("Skipping drive %s due to API error: %s", drive_id, exc)
            continue


def _collect_documents() -> List[Dict[str, object]]:
    documents = list(_iter_sop_items())
    documents.sort(key=lambda doc: str(doc.get("name", "")).lower())
    return documents


def list_sop_documents(_: dict) -> str:
    try:
        documents = _collect_documents()
    except (OneDriveAuthError, OneDriveAPIError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"documents": documents, "count": len(documents)})


def search_sop_documents(args: Dict[str, str]) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "query is required"})

    try:
        documents = _collect_documents()
    except (OneDriveAuthError, OneDriveAPIError) as exc:
        return json.dumps({"error": str(exc)})

    query_lower = query.lower()
    matches = [
        doc
        for doc in documents
        if query_lower in str(doc.get("name", "")).lower()
        or query_lower in str(doc.get("path", "")).lower()
    ][:10]
    return json.dumps({"documents": matches, "query": query})


def fetch_sop_document(args: Dict[str, str]) -> str:
    doc_id = args.get("doc_id") or args.get("id")
    drive_id = args.get("drive_id")
    file_name = args.get("file_name") or args.get("name")

    try:
        documents = _collect_documents()
    except (OneDriveAuthError, OneDriveAPIError) as exc:
        return json.dumps({"error": str(exc)})

    target: Optional[Dict[str, object]] = None
    if doc_id:
        for doc in documents:
            if doc.get("id") == doc_id and (not drive_id or doc.get("drive_id") == drive_id):
                target = doc
                break
    if not target and file_name:
        file_name_lower = file_name.lower()
        candidates = [doc for doc in documents if str(doc.get("name", "")).lower() == file_name_lower]
        if drive_id:
            for doc in candidates:
                if doc.get("drive_id") == drive_id:
                    target = doc
                    break
        if not target and len(candidates) == 1:
            target = candidates[0]
    if not target:
        return json.dumps({"error": "SOP document not found"})

    download_url = target.get("download_url")
    if not download_url:
        resolved = _resolve_download_url(str(target.get("drive_id")), str(target.get("id")))
        if not resolved:
            return json.dumps({"error": "Unable to resolve download URL"})
        download_url = resolved

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = str(target.get("name")).replace("/", "_")
    local_dir = os.path.join("data", "sop_cache")
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, f"{timestamp}_{safe_name}")

    try:
        download_file(str(download_url), local_path)
    except requests.RequestException as exc:
        logger.error("Failed to download SOP document %s: %s", target.get("name"), exc)
        return json.dumps({"error": str(exc)})

    payload = {
        "local_path": local_path,
        "file_name": target.get("name"),
        "doc_id": target.get("id"),
        "drive_id": target.get("drive_id"),
        "web_url": target.get("web_url"),
        "last_modified": target.get("last_modified"),
        "size": target.get("size"),
    }
    return json.dumps(payload)


@lru_cache(maxsize=1)
def _get_openai_client():  # pragma: no cover
    if OpenAI is None:
        raise ImportError("openai package not installed; cannot generate embeddings")
    return OpenAI()


def _format_vector(values: Iterable[float]) -> str:
    return "[" + ",".join(f"{val:.8f}" for val in values) + "]"


def _embed_query(text: str) -> str:
    client = _get_openai_client()
    response = client.embeddings.create(model=SOP_EMBED_MODEL, input=[text])
    return _format_vector(response.data[0].embedding)


def retrieve_similar_docs(args: Dict[str, str]) -> str:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 5) or 5)
    if not query:
        return json.dumps({"error": "query is required"})

    try:
        embedding_literal = _embed_query(query)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to embed query for SOP retrieval: %s", exc)
        return json.dumps({"error": str(exc)})

    sql = f"""
    with input_embedding as (select %s::vector as embedding)
    select
        se.doc_id,
        se.doc_name,
        se.chunk_index,
        se.content,
        se.metadata,
        1 - (se.embedding <=> input_embedding.embedding) as similarity
    from {SOP_EMBED_TABLE} as se, input_embedding
    order by se.embedding <=> input_embedding.embedding
    limit %s
    """

    try:
        rows = db_run(sql, (embedding_literal, limit))
    except Exception as exc:
        logger.error("SOP similarity query failed: %s", exc)
        return json.dumps({"error": str(exc)})

    matches: List[Dict[str, object]] = []
    for row in rows or []:
        raw_metadata = row[4]
        try:
            metadata = json.loads(raw_metadata) if raw_metadata else None
        except json.JSONDecodeError:
            metadata = raw_metadata
        matches.append(
            {
                "doc_id": row[0],
                "doc_name": row[1],
                "chunk_index": row[2],
                "content": row[3],
                "metadata": metadata,
                "similarity": row[5],
            }
        )

    return json.dumps({"query": query, "matches": matches})


list_documents_tool = Tool(
    name="list_sop_documents",
    func=list_sop_documents,
    description="List SOP documents available in OneDrive. No arguments required.",
)

search_documents_tool = Tool(
    name="search_sop_documents",
    func=search_sop_documents,
    description="Search for SOP documents matching a natural language query. Args: query (str)",
)

fetch_document_tool = Tool(
    name="fetch_sop_document",
    func=fetch_sop_document,
    description="Download an SOP document. Args: doc_id (str optional), drive_id (str optional), file_name (str optional).",
)

retrieve_similar_tool = Tool(
    name="retrieve_similar_sop_documents",
    func=retrieve_similar_docs,
    description=(
        "Semantic similarity search over embedded SOP chunks. Args: query (str), limit (int optional)."
    ),
)

__all__ = [
    "list_documents_tool",
    "search_documents_tool",
    "fetch_document_tool",
    "retrieve_similar_tool",
]
