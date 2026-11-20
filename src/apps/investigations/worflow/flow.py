import logging
import tempfile
from pathlib import Path

import requests
from celery import shared_task
from django.utils import timezone

from apps.datasets.models import DatasetCleaningJob
from apps.investigations.models import Investigation
from .graph import build_investigation_graph

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def investigation_flow(self, investigation_id: str):
    investigation = Investigation.objects.select_related("dataset__profile").get(
        id=investigation_id
    )

    investigation.status = Investigation.Status.RUNNING
    investigation.save(update_fields=["status"])

    try:
        dataset = investigation.dataset
        profile = dataset.profile

        # Prefer the latest completed cleaned CSV if available, otherwise raw upload
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

            # Download once from Cloudinary for all Docker sandbox steps
            with requests.get(cloudinary_resource.url, stream=True, timeout=30) as resp:
                resp.raise_for_status()
                with open(local_csv_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

            final_state = build_investigation_graph().invoke(
                {
                    "investigation_id": str(investigation.id),
                    "dataset_id": str(dataset.id),
                    "dataset_file_path": str(local_csv_path),
                    "dataset_profile": profile.to_dict(),
                    "question": investigation.question,
                    "goal": investigation.goal,
                    "errors": [],
                }
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

    except Exception as exc:
        logger.exception("Investigation %s failed", investigation_id)
        investigation.status = Investigation.Status.FAILED
        investigation.errors = [str(exc)]
        investigation.completed_at = timezone.now()
        investigation.save(update_fields=["status", "errors", "completed_at"])
        raise