from rest_framework import serializers
from .models import Investigation


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


class InvestigationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investigation
        fields = ["id", "dataset", "question", "goal", "status"]
