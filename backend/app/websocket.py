import asyncio
import logging
from fastapi import WebSocket
from .config import settings
from .schemas import Event

logger = logging.getLogger('noor.websocket')

class EventBus:
    def __init__(self, history_limit: int = 500):
        self.clients: set[WebSocket] = set()
        self.history: list[Event] = []
        self.history_limit = history_limit
        self.lock = asyncio.Lock()

    def _origin_allowed(self, origin: str | None) -> bool:
        allowed = [o.strip() for o in settings.noor_ws_allowed_origins.split(',') if o.strip()]
        return not origin or origin in allowed

    async def connect(self, ws: WebSocket):
        if not self._origin_allowed(ws.headers.get('origin')):
            await ws.close(code=1008)
            raise RuntimeError('websocket origin not allowed')
        await ws.accept()
        async with self.lock:
            self.clients.add(ws)
            history = list(self.history[-50:])
        for event in history:
            try:
                await ws.send_json(event.model_dump(mode='json'))
            except Exception as exc:
                logger.warning('failed to replay websocket history: %s', exc)
                self.disconnect(ws)
                return

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    async def publish(self, event: Event):
        async with self.lock:
            self.history.append(event)
            self.history = self.history[-self.history_limit:]
            clients = list(self.clients)
        dead: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(event.model_dump(mode='json'))
            except Exception as exc:
                logger.warning('dropping disconnected websocket client: %s', exc)
                dead.append(client)
        if dead:
            async with self.lock:
                for client in dead:
                    self.clients.discard(client)

bus = EventBus()
