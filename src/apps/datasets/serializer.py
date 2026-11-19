from rest_framework import serializers
from .models import Dataset, DatasetProfile, DatasetCleaningJob
import os
from django.db import transaction
from .services.profiling import profile_dataset
from .services.taskes import clean_dataset_task


class DatasetUploadSerializer(serializers.ModelSerializer):

    class Meta:
        model = Dataset
        fields = ["name", "file"]

    def validate_file(self, file):
        if file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Maximum file size is 10 MB.")

        if os.path.splitext(file.name)[1].lower() != ".csv":
            raise serializers.ValidationError("Only CSV files are allowed.")

        return file

    def create(self, validated_data):

        request = self.context["request"]

        file = validated_data["file"]
        with transaction.atomic():
            dataset = Dataset.objects.create(
                **validated_data, user=request.user, file_size=file.size
            )
            transaction.on_commit(lambda: profile_dataset.delay(dataset_id=dataset.id))
        return dataset


class GetDataSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = [
            "id",
            "name",
            "file_size",
            "status",
            "created_at",
        ]


class DataSetProfilingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatasetProfile
        fields = "__all__"


class DataSetCleaningSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatasetCleaningJob
        fields = ["dataset", "operations"]

    def validate(self, attrs):
        if not isinstance(attrs.get("operations"), dict):
            raise serializers.ValidationError("operation must be a dict")
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            cleaning_job = DatasetCleaningJob.objects.create(**validated_data)
            transaction.on_commit(
                lambda: clean_dataset_task.delay(cleaning_job_id=cleaning_job.id)
            )
        return cleaning_job
