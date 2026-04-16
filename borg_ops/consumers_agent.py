"""
borg_ops/consumers_agent.py — WebSocket consumer za Fenix Sobu.

URL: ws/fenix/agent/<task_id>/
Protokol:
  Server -> Client: {type: thinking|tool_start|tool_end|diff|approval|done|error|rejected|approved}
  Client -> Server: {type: approve|reject|start|ping}
"""

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger("agent_ws")


class FenixAgentConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.task_id = self.scope["url_route"]["kwargs"]["task_id"]
        self.room    = f"agent_task_{self.task_id}"
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        if not (user.is_superuser or user.is_staff):
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

        state = await self._get_state()
        await self.send_json({"type": "init", **state})
        logger.info("WS connect: user=%s task=%s", user.username, self.task_id)

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive_json(self, content):
        msg_type = content.get("type", "")

        if msg_type == "start":
            await self._handle_start()
        elif msg_type == "approve":
            await self._handle_approval(True)
        elif msg_type == "reject":
            await self._handle_approval(False)
        elif msg_type == "ping":
            state = await self._get_state()
            await self.send_json({"type": "pong", **state})

    async def agent_message(self, event):
        """Celery worker salje ovu poruku -> prosljedujemo browseru."""
        await self.send_json(event["data"])

    # ── Handleri ──────────────────────────────────────────────────────────────

    async def _handle_start(self):
        from .tasks_agent import execute_agent_task
        updated = await database_sync_to_async(self._set_queued)()
        if updated:
            execute_agent_task.delay(str(self.task_id))
            await self.send_json({"type": "queued", "message": "Task je u redu, pokrecujem..."})
        else:
            state = await self._get_state()
            await self.send_json({"type": "error", "error": f"Ne mogu pokrenuti task u statusu: {state.get('status')}"})

    async def _handle_approval(self, approved: bool):
        from .tasks_agent import continue_after_approval
        continue_after_approval.delay(str(self.task_id), approved)
        await self.send_json({
            "type": "approval_received",
            "approved": approved,
            "message": "Odobreno — izvrsavam." if approved else "Odbijeno.",
        })

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _set_queued(self) -> bool:
        from .models import AgentTask
        return bool(AgentTask.objects.filter(pk=self.task_id, status="draft").update(status="queued"))

    @database_sync_to_async
    def _get_state(self) -> dict:
        from .models import AgentTask, AgentTaskLog
        try:
            t = AgentTask.objects.get(pk=self.task_id)
            logs = list(
                AgentTaskLog.objects.filter(task=t)
                .values("tool_type", "tool_input", "tool_output",
                        "is_approval_gate", "duration_ms", "created_at")
                .order_by("created_at")[:50]
            )
            # Serialize datetime
            for log in logs:
                if log.get("created_at"):
                    log["created_at"] = log["created_at"].isoformat()
            return {
                "task_id": str(t.pk),
                "agent": t.agent,
                "title": t.title,
                "status": t.status,
                "scope": t.scope,
                "requires_approval": t.requires_approval,
                "approval_prompt": t.approval_prompt,
                "summary": t.agent_summary,
                "cost_usd": str(t.cost_usd),
                "cost_display": t.cost_display,
                "logs": logs,
            }
        except Exception as e:
            return {"error": str(e)}
