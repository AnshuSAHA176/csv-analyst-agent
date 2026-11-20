from rest_framework import serializers
from .models import Investigation
from django.db import transaction
from .worflow.flow import investigation_flow


class InvestigationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investigation
        fields = ["id", "dataset", "question", "goal", "status"]
        extra_kwargs = {
            "id": {"read_only": True},
            "status": {"read_only": True},
        }

    def validate_dataset(self, dataset):
        user = self.context["request"].user

        if dataset.user != user:
            raise serializers.ValidationError("You do not own this dataset.")

        return dataset

    def create(self, validated_data):
        with transaction.atomic():
            investigation = Investigation.objects.create(**validated_data)
            transaction.on_commit(
                lambda: investigation_flow.delay(investigation_id=investigation.id)
            )
        return investigation


class InvestigationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investigation
        fields = ["id", "dataset", "question", "goal", "status"]


class InvestigationDeailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investigation
        fields = [
            "id",
            "dataset",
            "question",
            "goal",
            "status",
            "analysis_plan",
            "evidence_collected",
            "verification_results",
            "final_report",
            "errors",
            "created_at",
            "completed_at",
        ]
    
    