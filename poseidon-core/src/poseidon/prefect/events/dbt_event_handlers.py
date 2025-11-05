"""dbt-specific event handlers."""

from __future__ import annotations

from poseidon.prefect.events.andon_event_handlers import on_dbt_test_failed
from poseidon.prefect.tasks.kaizen_tasks import record_kaizen_event


def on_dbt_run_success(run_id: str, total_models: int) -> None:
    record_kaizen_event.fn(
        source="dbt",
        description=f"dbt run {run_id} succeeded",
        impact=f"Models built: {total_models}",
    )


def on_dbt_test_failure(model: str, test_name: str, failure_msg: str) -> None:
    on_dbt_test_failed("dbt_build_flow", model, test_name, failure_msg)


def on_dbt_model_runtime_warning(model: str, duration_s: float, threshold_s: float) -> None:
    if duration_s > threshold_s:
        record_kaizen_event.fn(
            source=model,
            description="dbt model runtime warning",
            impact=f"{duration_s:.2f}s > {threshold_s:.2f}s",
        )
