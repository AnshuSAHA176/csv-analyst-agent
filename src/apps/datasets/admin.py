from django.contrib import admin
from .models import Dataset,DatasetProfile,DatasetCleaningJob

admin.site.register(DatasetProfile)
admin.site.register(Dataset)
admin.site.register(DatasetCleaningJob)