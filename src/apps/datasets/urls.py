from django.urls import path
from .views import DataSetView

urlpatterns=[
    path("",DataSetView.as_view(),name="datasets")
]