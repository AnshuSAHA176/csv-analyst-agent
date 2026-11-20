from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework import generics
from .serializer import (
    InvestigationCreateSerializer,
    InvestigationListSerializer,
    InvestigationDeailsSerializer,
)
from .models import Investigation


class IsInvestigationOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj.user

    def has_permission(self, request, view):
        return request.user.is_authenticated


class InvestigationView(generics.ListCreateAPIView):
    permission_classes = [IsInvestigationOwner]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return InvestigationCreateSerializer
        return InvestigationListSerializer

    def get_queryset(self):
        queryset = Investigation.objects.filter(user=self.request.user)
        dataset_id = self.request.query_params.get("dataset")
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class InvestigationDetailsView(generics.RetrieveAPIView):
    permission_classes=[IsInvestigationOwner]
    queryset=Investigation.objects.all()
    lookup_field="id"
    lookup_url_kwarg="investigation_id"
    serializer_class =InvestigationDeailsSerializer
    