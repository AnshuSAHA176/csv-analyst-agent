import logging
import tempfile
from pathlib import Path

import requests
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.datasets.models import DatasetCleaningJob
from apps.investigations.models import Investigation
from .graph import build_investigation_graph

logger = logging.getLogger(__name__)


def ws_event(investigation_id: str, event_type: str, data: dict | None = None):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"investigation_{investigation_id}",
        {
            "type": "investigation.update",
            "payload": {
                "event": event_type,
                "investigation_id": str(investigation_id),
                **(data or {}),
            },
        },
    )


def _get_step_meta(state: dict, index: int) -> dict:
    """Safely look up step_id and description from the active analysis plan."""
    steps = (state.get("analysis_plan") or {}).get("steps", [])
    if 0 <= index < len(steps):
        return {
            "step_id": steps[index].get("step_id"),
            "description": steps[index].get("description", ""),
            "tool": steps[index].get("tool", ""),
        }
    return {"step_id": None, "description": "", "tool": ""}


@shared_task(bind=True, ignore_result=True)
def investigation_flow(self, investigation_id: str):
    investigation = Investigation.objects.select_related("dataset__profile").get(
        id=investigation_id
    )

    investigation.status = Investigation.Status.RUNNING
    investigation.save(update_fields=["status"])
    ws_event(investigation.id, "started", {"status": investigation.status})

    try:
        dataset = investigation.dataset
        profile = dataset.profile

        latest_cleaned = (
            dataset.cleaning_jobs.filter(status=DatasetCleaningJob.Status.COMPLETED)
            .exclude(cleaned_file__isnull=True)
            .exclude(cleaned_file="")
            .order_by("-completed_at")
            .first()
        )
        cloudinary_resource = (
            latest_cleaned.cleaned_file if latest_cleaned else dataset.file
        )

        with tempfile.TemporaryDirectory(prefix="investigation-") as tmp_dir:
            local_csv_path = Path(tmp_dir) / "dataset.csv"

            with requests.get(cloudinary_resource.url, stream=True, timeout=30) as resp:
                resp.raise_for_status()
                with open(local_csv_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

            initial_state = {
                "investigation_id": str(investigation.id),
                "dataset_id": str(dataset.id),
                "dataset_file_path": str(local_csv_path),
                "dataset_profile": profile.to_dict(),
                "question": investigation.question,
                "goal": investigation.goal,
                "replan_count": 0,
                "errors": [],
            }

            final_state = dict(initial_state)
            graph = build_investigation_graph()

            for mode, chunk in graph.stream(
                initial_state, stream_mode=["updates", "values"]
            ):
                if mode == "values":
                    final_state = chunk

                elif mode == "updates":
                    for _, delta in chunk.items():
                        # 1. Initial Plan or Recovery Re-Plan Created
                        if "analysis_plan" in delta:
                            is_replan = delta.get("replan_count", 0) > 0
                            ws_event(
                                investigation_id=investigation.id,
                                event_type=(
                                    "replan_created" if is_replan else "plan_created"
                                ),
                                data={
                                    "replan_count": delta.get("replan_count", 0),
                                    "analysis_plan": delta.get("analysis_plan"),
                                },
                            )

                        # 2. Python Analysis Code Generated
                        elif "current_code" in delta:
                            idx = final_state.get("current_analysis_step", 0)
                            meta = _get_step_meta(final_state, idx)
                            ws_event(
                                investigation_id=investigation.id,
                                event_type="code_generated",
                                data={
                                    **meta,
                                    "code": delta.get("current_code"),
                                },
                            )

                        # 3. Code Execution Failed on Try 1 -> Triggering Retry
                        elif delta.get("last_error"):
                            idx = final_state.get("current_analysis_step", 0)
                            meta = _get_step_meta(final_state, idx)
                            ws_event(
                                investigation_id=investigation.id,
                                event_type="code_failed_retrying",
                                data={
                                    "step_id": meta["step_id"],
                                    "retry_count": delta.get("retry_count", 1),
                                    "error": delta["last_error"][-500:],
                                },
                            )

                        # 4. Code Executed Successfully
                        elif delta.get("evidence_collected"):
                            latest = delta["evidence_collected"][-1]
                            ws_event(
                                investigation_id=investigation.id,
                                event_type="code_executed",
                                data={
                                    "step_id": latest["step_id"],
                                    "summary": latest["summary"],
                                    "sample_size": latest.get("sample_size", 0),
                                    "metrics": latest.get("metrics", {}),
                                },
                            )

                        # 5. Code Failed Twice -> Step Skipped
                        elif "errors" in delta and "tool_execution_results" in delta:
                            failed_idx = delta.get("current_analysis_step", 1) - 1
                            meta = _get_step_meta(final_state, failed_idx)
                            latest_err = (
                                delta["errors"][-1][-500:] if delta["errors"] else ""
                            )
                            ws_event(
                                investigation_id=investigation.id,
                                event_type="step_failed",
                                data={
                                    "step_id": meta["step_id"],
                                    "error": latest_err,
                                },
                            )

                        # 6. Evidence Verification Completed
                        elif "verification_results" in delta:
                            ws_event(
                                investigation_id=investigation.id,
                                event_type="verification_completed",
                                data={
                                    "verification_results": delta.get(
                                        "verification_results"
                                    )
                                },
                            )

        investigation.analysis_plan = final_state.get("analysis_plan", {})
        investigation.evidence_collected = final_state.get("evidence_collected", [])
        investigation.verification_results = final_state.get("verification_results", {})
        investigation.final_report = final_state.get("final_report", {})
        investigation.errors = final_state.get("errors", [])
        investigation.status = Investigation.Status.COMPLETED
        investigation.completed_at = timezone.now()
        investigation.save(
            update_fields=[
                "analysis_plan",
                "evidence_collected",
                "verification_results",
                "final_report",
                "errors",
                "status",
                "completed_at",
            ]
        )
        ws_event(
            investigation_id=investigation.id,
            event_type="completed",
            data={
                "status": investigation.status,
                "final_report": investigation.final_report,
            },
        )

    except Exception as exc:
        logger.exception("Investigation %s failed", investigation_id)
        investigation.status = Investigation.Status.FAILED
        investigation.errors = [str(exc)]
        investigation.completed_at = timezone.now()
        investigation.save(update_fields=["status", "errors", "completed_at"])
        ws_event(
            investigation_id=investigation.id,
            event_type="failed",
            data={"status": investigation.status, "error": str(exc)},
        )
        raise
