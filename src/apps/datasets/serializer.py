from rest_framework import serializers
from .models import Dataset
import os


class DatasetUploadSerializer(serializers.ModelSerializer):

    class Meta:
        model = Dataset
        fields = ["name", "file"]

    def validate_file(self, file):
        if file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "Maximum file size is 10 MB."
            )

        if os.path.splitext(file.name)[1].lower() != ".csv":
            raise serializers.ValidationError(
                "Only CSV files are allowed."
            )

        return file

    def create(self, validated_data):
        request = self.context["request"]

        file = validated_data["file"]

        return Dataset.objects.create(
            **validated_data,
            user=request.user,
            file_size=file.size
        )
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