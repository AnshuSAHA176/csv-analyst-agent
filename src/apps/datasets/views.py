from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializer import DatasetUploadSerializer,GetDataSetSerializer
from .models import Dataset


class DataSetView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request):
        serializer = DatasetUploadSerializer(data=request.data,context={"request":request})
        serializer.is_valid(raise_exception=True)
        dataset = serializer.save()
        return Response(
            {
                "message": "File uploaded",
                "id": str(dataset.id),
                "name": dataset.name
            },
            status=201
        )
    def get(self,request):
        datasets = Dataset.objects.filter(user=request.user)
        serializer = GetDataSetSerializer(datasets,many=True)
        return Response(serializer.data)
