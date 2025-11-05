"""Entry point for `python -m poseidon.prefect.deployments`."""

from __future__ import annotations

import argparse
from pathlib import Path

from poseidon.prefect.deployments.reporting import apply_all_deployments
from poseidon.prefect.deployments.streams import apply_stream_deployments


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Prefect deployments for Poseidon.")
    parser.add_argument(
        "--mode",
        choices=["reporting", "streams", "all"],
        default="all",
        help="Deployment sets to apply.",
    )
    parser.add_argument("--work-pool", default="default", help="Prefect work pool to target.")
    parser.add_argument("--base-path", default=None, help="Repository root override.")
    parser.add_argument(
        "--storage-block-name",
        default="poseidon-local-storage",
        help="LocalFileSystem block name.",
    )
    parser.add_argument(
        "--streams-storage-block-name",
        default="poseidon-streams-storage",
        help="Storage block name for stream deployments.",
    )
    parser.add_argument("--queue-prefix", default=None, help="Optional prefix for stream work queues.")
    return parser.parse_args()


def _resolve_path(value: str | None) -> Path | None:
    return Path(value).resolve() if value else None


if __name__ == "__main__":  # pragma: no cover
    args = _parse_args()
    repo_path = _resolve_path(args.base_path)

    if args.mode in {"reporting", "all"}:
        apply_all_deployments(
            work_pool_name=args.work_pool,
            repo_path=repo_path,
            storage_block_name=args.storage_block_name,
        )

    if args.mode in {"streams", "all"}:
        apply_stream_deployments(
            work_pool_name=args.work_pool,
            repo_path=repo_path,
            storage_block_name=args.streams_storage_block_name,
            work_queue_prefix=args.queue_prefix,
        )
