from django.urls import path
from .views import DataSetView,DataSetDetailView

urlpatterns=[
    path("",DataSetView.as_view(),name="datasets"),
    path(
    "<uuid:dataset_id>/",
    DataSetDetailView.as_view()
)
]