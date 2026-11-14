from django.contrib import admin
from .models import Dataset,DatasetProfile

admin.site.register(DatasetProfile)
admin.site.register(Dataset)