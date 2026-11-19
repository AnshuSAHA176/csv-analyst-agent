from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializer import (
    DatasetUploadSerializer,
    GetDataSetSerializer,
    DataSetProfilingSerializer,
    DataSetCleaningSerializer,
)
from .models import Dataset, DatasetProfile
from django.shortcuts import get_object_or_404
from rest_framework import status
import cloudinary.uploader
from rest_framework.permissions import BasePermission


class IsDatasetOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj.dataset.user

class IsDataCleaingOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj.user

class DataSetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DatasetUploadSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        dataset = serializer.save()
        return Response(
            {"message": "File uploaded", "id": str(dataset.id), "name": dataset.name},
            status=201,
        )

    def get_queryset(self):
        return Dataset.objects.filter(user=self.request.user)

    def get(self, request):
        datasets = self.get_queryset()
        serializer = GetDataSetSerializer(datasets, many=True)
        return Response(serializer.data)


class DataSetDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, dataset_id):
        return get_object_or_404(Dataset, id=dataset_id, user=self.request.user)

    def get(self, request, dataset_id):
        serializer = GetDataSetSerializer(self.get_object(dataset_id=dataset_id))
        return Response(serializer.data)

    def delete(self, request, dataset_id):
        dataset = self.get_object(dataset_id=dataset_id)
        if dataset.file:
            cloudinary.uploader.destroy(
                dataset.file.public_id, resource_type="raw", invalidate=True
            )
        dataset.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class DataSetProfilingView(APIView):
    permission_classes = [IsAuthenticated, IsDatasetOwner]

    def get(self, request, dataset_id):
        dataset_profile = get_object_or_404(
            DatasetProfile.objects.select_related("dataset"),
            dataset_id=dataset_id,
        )

        self.check_object_permissions(request=request, obj=dataset_profile)
        serializer = DataSetProfilingSerializer(dataset_profile)

        return Response(serializer.data)


class DataSetCleaingView(APIView):
    permission_classes = [IsAuthenticated, IsDataCleaingOwner]

    def post(self, request):
        dataset_id = request.data.get("dataset")
        if not dataset_id:
            return Response(
                {"error": "please provide the dataset_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dataset = get_object_or_404(
            Dataset.objects.select_related("user"), id=dataset_id
        )
        self.check_object_permissions(request=request, obj=dataset)
        serializer = DataSetCleaningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        return Response(
            {
                "job_id": job.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )
