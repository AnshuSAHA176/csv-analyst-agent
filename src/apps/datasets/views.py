from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializer import DatasetUploadSerializer, GetDataSetSerializer
from .models import Dataset
from django.shortcuts import get_object_or_404
from rest_framework import status
import cloudinary.uploader


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
