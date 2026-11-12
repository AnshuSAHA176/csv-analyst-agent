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
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        dataset.status = Dataset.StatusChoices.PROCESSING
        dataset.save(update_fields=["status"])
        csv_file_url = dataset.file.url.replace("http://", "https://")
        response = requests.get(csv_file_url, timeout=10)
        with tempfile.NamedTemporaryFile(prefix=".csv") as temp:
            temp.flush()
            temp.write(response.content)
            profileing_data = profile_csv(file_path=temp.name)
            DatasetProfile.objects.create(
                dataset=dataset,
                row_count=profileing_data.get("row_count"),
                column_count=profileing_data.get("column_count"),
                duplicated_rows=profileing_data.get("duplicate_rows"),
                missing_values=profileing_data.get("missing_values"),
                column_details=profileing_data.get("column_details"),
            )
        dataset.status = Dataset.StatusChoices.READY
        dataset.save(update_fields=["status"])
    except Exception as exc:

        if self.request.retries >= self.max_retries:
            dataset.status = Dataset.StatusChoices.FAILED
            dataset.save(update_fields=["status"])

        raise self.retry(exc=exc, countdown=2**self.request.retries)
