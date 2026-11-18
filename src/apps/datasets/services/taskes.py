from celery import shared_task
from apps.datasets.services.cleaning import clean_dataset

@shared_task
def clean_dataset_task(file_path, operations):
    result = clean_dataset(file_path, operations)

    cleaned_df = result["dataframe"]
    report = result["report"]

    # Save cleaned_df and report