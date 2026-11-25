from django.urls import path
from .consumer import InvestigationConsumer

websocket_urlpatterns = [
    path(
        "ws/investigation/<uuid:investigation_id>/",
        InvestigationConsumer.as_asgi(),
        name="Investigation websocket",
    )
]
