from django.urls import path
from .views import InvestigationView


urlpatterns=[
    path("",InvestigationView.as_view(),name="investigation"),
]