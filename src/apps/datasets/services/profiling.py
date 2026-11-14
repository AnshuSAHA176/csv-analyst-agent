from apps.datasets.models import Dataset, DatasetProfile
import tempfile
import requests
import pandas as pd
from celery import shared_task


def profile_csv(file_path) -> dict:
    try:
        df = pd.read_csv(file_path)

        if df.empty:
            raise ValueError("CSV file is empty")

        row, col = df.shape

        return {
            "row_count": int(row),
            "column_count": int(col),
            "duplicate_rows": int(df.duplicated().sum()),
            "missing_values": df.isnull().sum().to_dict(),
            "column_details": df.dtypes.astype(str).to_dict(),
        }

    except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        raise ValueError(f"Invalid CSV file: {e}") from e


@shared_task(bind=True, max_retries=3, ignore_result=True)
def profile_dataset(self, dataset_id: str):
    dataset = None

    try:
        dataset = Dataset.objects.get(id=dataset_id)

        dataset.status = Dataset.StatusChoices.PROCESSING
        dataset.save(update_fields=["status"])

        with tempfile.NamedTemporaryFile(suffix=".csv") as temp:
            response = requests.get(dataset.file.url, timeout=(5, 30), stream=True)
            response.raise_for_status()

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp.write(chunk)

            temp.flush()

            profiling_data = profile_csv(temp.name)

        DatasetProfile.objects.update_or_create(
            dataset=dataset,
            defaults={
                "row_count": profiling_data["row_count"],
                "column_count": profiling_data["column_count"],
                "duplicated_rows": profiling_data["duplicate_rows"],
                "missing_values": profiling_data["missing_values"],
                "column_details": profiling_data["column_details"],
            },
        )

        dataset.status = Dataset.StatusChoices.READY
        dataset.save(update_fields=["status"])

    except Exception as exc:

        if dataset is not None and self.request.retries >= self.max_retries:
            dataset.status = Dataset.StatusChoices.FAILED
            dataset.save(update_fields=["status"])

        raise self.retry(exc=exc, countdown=2**self.request.retries)
