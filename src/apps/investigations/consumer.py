from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from .models import Investigation


class InvestigationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.investigation_id = str(
            self.scope["url_route"]["kwargs"]["investigation_id"]
        )
        self.groups_name = f"investigation_{self.investigation_id}"
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close(code=4001)
            return
        snapshot = await self.get_investigation_snapshot(
            investigation_id=self.investigation_id, user_id=user.id
        )
        if not snapshot:
            return await self.close(code=4001)
        await self.channel_layer.group_add(
            group=self.groups_name, channel=self.channel_name
        )
        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    "event": "connected",
                    "investigation_id": self.investigation_id,
                    **snapshot,
                }
            )
        )

    async def disconnect(self, code):
        if hasattr(self, "groups_name"):
            await self.channel_layer.group_discard(
                group=self.groups_name, channel=self.channel_name
            )

    async def investigation_update(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def get_investigation_snapshot(self, investigation_id: str, user_id: str) -> dict:
        inv = Investigation.objects.filter(id=investigation_id, user_id=user_id).first()
        if not inv:
            return None
        return {
            "status": inv.status,
            "analysis_plan": inv.analysis_plan,
            "verification_results": inv.verification_results,
            "final_report": inv.final_report,
        }
