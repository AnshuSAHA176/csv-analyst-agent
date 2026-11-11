import uuid
from django.conf import settings
from django.db import models
from cloudinary.models import CloudinaryField


class Dataset(models.Model):

    class StatusChoices(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="datasets"
    )

    name = models.CharField(max_length=255)

    file = CloudinaryField(
        "file",
        resource_type="raw",
    )

    file_size = models.PositiveBigIntegerField(default=0)

    status = models.CharField(
        max_length=20, choices=StatusChoices.choices, default=StatusChoices.UPLOADED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.name
