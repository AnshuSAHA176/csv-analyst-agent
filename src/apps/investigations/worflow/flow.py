from celery import shared_task
from apps.investigations.models import Investigation
from .graph import build_investigation_graph


@shared_task(bind=True,ignore_result=True)
def investigation_flow(self,dataset_id:str):
    pass