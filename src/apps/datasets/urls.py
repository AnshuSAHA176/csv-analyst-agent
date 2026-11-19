from django.urls import path
from .views import DataSetView, DataSetDetailView, DataSetProfilingView,DataSetCleaingView

urlpatterns = [
    path("", DataSetView.as_view(), name="datasets"),
    path("<uuid:dataset_id>/", DataSetDetailView.as_view()),
    path("<uuid:dataset_id>/profile/", DataSetProfilingView.as_view()),
    path("cleaning-jobs/", DataSetCleaingView.as_view()),
]
