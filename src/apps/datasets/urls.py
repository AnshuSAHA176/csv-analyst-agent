from django.urls import path
from .views import DataSetView, DataSetDetailView, DataSetProfilingView

urlpatterns = [
    path("", DataSetView.as_view(), name="datasets"),
    path("<uuid:dataset_id>/", DataSetDetailView.as_view()),
    path("<uuid:dataset_id>/profile/", DataSetProfilingView.as_view()),
]
