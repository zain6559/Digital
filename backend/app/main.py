from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .agents import coordinator
from .config import settings
from .cognitive_core import cognitive_core
from .memory import spatial_memory
from .mobile_bridge import mobile_bridge
from .schemas import CommandRequest, DeviceCommand, Event, MemoryIn, VisionFrameIn
from .websocket import bus
from .vision import VisionFrame, vision_engine

def _csv(value: str) -> list[str]: return [v.strip() for v in value.split(',') if v.strip()]
@asynccontextmanager
async def lifespan(app: FastAPI):
    seed=spatial_memory.add(MemoryIn(title='Noor OS boot memory', content='Backend started; in-memory event bus and spatial memory are available.', tags=['system','memory'], source='system'))
    await bus.publish(Event(type='system.boot', payload={'memory': seed.model_dump(mode='json')}))
    yield

app=FastAPI(title='Noor OS API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=_csv(settings.noor_cors_origins), allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['content-type','authorization'])
@app.get('/health')
async def health():
    persistence = cognitive_core.persistence_status()
    return {
        'status': 'ok' if persistence['status'] == 'ok' else 'degraded',
        'service': 'noor-backend',
        'environment': settings.noor_env,
        'safe_defaults': {
            'browser_automation': settings.noor_enable_browser_automation,
            'mobile_bridge': settings.noor_enable_mobile_bridge,
            'cloud_fallback': settings.hybrid_fallback_enabled,
            'public_posting': settings.noor_enable_public_posting,
        },
        'persistence': persistence,
        'limits': {'websocket_history': bus.history_limit, 'cognitive_events': cognitive_core.limits['max_events']},
    }
@app.get('/diagnostics')
async def diagnostics():
    return {
        'service': 'noor-backend',
        'environment': settings.noor_env,
        'features': {
            'browser_automation_enabled': settings.noor_enable_browser_automation,
            'mobile_bridge_enabled': settings.noor_enable_mobile_bridge,
            'cloud_fallback_enabled': settings.hybrid_fallback_enabled,
            'public_posting_enabled': settings.noor_enable_public_posting,
        },
        'event_bus': bus.stats(),
        'cognitive': cognitive_core.metrics_snapshot(),
    }
@app.post('/api/command')
async def command(req:CommandRequest): return await coordinator.execute(req)
@app.get('/api/tasks')
async def tasks(): return await coordinator.list_tasks()
@app.post('/api/memory')
async def add_memory(m:MemoryIn):
    out=spatial_memory.add(m); await bus.publish(Event(type='memory.created', payload=out.model_dump(mode='json'))); return out
@app.get('/api/memory/search')
async def search_memory(q:str): return spatial_memory.search(q)
@app.get('/api/memory/realms')
async def realms(): return spatial_memory.realms()
@app.post('/api/vision/frame')
async def vision_frame(frame:VisionFrameIn): return await vision_engine.ingest(VisionFrame(**frame.model_dump()))
@app.get('/api/vision/inspect')
async def vision_inspect(source:str, objective:str): return await vision_engine.inspect(source, objective)

@app.get('/api/cognitive/state')
async def cognitive_state(): return {'beliefs': list(cognitive_core.beliefs.values()), 'evidence': list(cognitive_core.evidence.values()), 'world': list(cognitive_core.world.values()), 'self_model': cognitive_core.self_model(), 'ticks': cognitive_core.tick_count}
@app.post('/api/cognitive/tick')
async def cognitive_tick(): return cognitive_core.tick()

@app.get('/api/mobile/devices')
async def devices(): return await mobile_bridge.devices()
@app.post('/api/mobile/command')
async def mobile_command(c:DeviceCommand): return await mobile_bridge.command(c)
@app.websocket('/ws')
async def websocket(ws:WebSocket):
    await bus.connect(ws)
    try:
        while True:
            data=await ws.receive_json(); await bus.publish(Event(type='client.message', payload=data if isinstance(data,dict) else {'raw':data}))
    except WebSocketDisconnect: bus.disconnect(ws)
