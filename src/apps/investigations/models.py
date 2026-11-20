import uuid

from django.db import models
from django.conf import settings


class Investigation(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="investigations"
    )

    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="investigations"
    )

    question = models.TextField()
    goal = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # Investigation outputs & audit trail
    analysis_plan = models.JSONField(default=dict, blank=True)
    evidence_collected = models.JSONField(default=list, blank=True)
    verification_results = models.JSONField(default=dict, blank=True)
    final_report = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.question[:80]