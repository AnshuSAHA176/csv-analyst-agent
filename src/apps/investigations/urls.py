from django.urls import path
from .views import InvestigationView,InvestigationDetailsView


urlpatterns=[
    path("",InvestigationView.as_view(),name="investigation"),
    path("<uuid:investigation_id>/",InvestigationDetailsView.as_view(),name="investigation-details"),
]