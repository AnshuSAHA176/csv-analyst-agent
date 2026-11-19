import tempfile
import requests
import cloudinary.uploader

from celery import shared_task
from django.utils import timezone

from apps.datasets.models import DatasetCleaningJob
from apps.datasets.services.cleaning import clean_dataset


@shared_task(bind=True, max_retries=3)
def clean_dataset_task(self, cleaning_job_id):

    job = None

    try:
        # 1. Retrieve cleaning job
        job = DatasetCleaningJob.objects.select_related(
            "dataset"
        ).get(id=cleaning_job_id)

        job.status = DatasetCleaningJob.Status.PROCESSING
        job.save(update_fields=["status"])

        # 2. Download original CSV
        response = requests.get(
            job.dataset.file.url,
            timeout=(5, 30),
            stream=True
        )
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".csv") as input_file:

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    input_file.write(chunk)

            input_file.flush()

            # 3. Execute cleaning engine
            result = clean_dataset(
                input_file.name,
                job.operations
            )

            cleaned_df = result["dataframe"]
            report = result["report"]

            # 4. Save cleaned CSV temporarily
            with tempfile.NamedTemporaryFile(suffix=".csv") as output_file:

                cleaned_df.to_csv(output_file.name, index=False)
                output_file.flush()

                # 5. Upload cleaned CSV to Cloudinary
                upload_result = cloudinary.uploader.upload(
                    output_file.name,
                    resource_type="raw",
                    folder="cleaned_datasets"
                )

        # 6. Save Cloudinary reference and report
        job.cleaned_file = upload_result["public_id"]
        job.report = report
        job.status = DatasetCleaningJob.Status.COMPLETED
        job.completed_at = timezone.now()

        job.save(update_fields=[
            "cleaned_file",
            "report",
            "status",
            "completed_at"
        ])

        return str(job.id)

    except Exception as exc:

        if job is not None:
            job.status = DatasetCleaningJob.Status.FAILED
            job.save(update_fields=["status"])

        raise