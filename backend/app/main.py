from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .agents import coordinator
from .memory import spatial_memory
from .mobile_bridge import mobile_bridge
from .schemas import CommandRequest, DeviceCommand, Event, MemoryIn, VisionFrameIn
from .websocket import bus
from .vision import VisionFrame, vision_engine

app=FastAPI(title='Noor OS API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

@app.on_event('startup')
async def startup():
    seed=spatial_memory.add(MemoryIn(title='Noor OS boot memory', content='The spatial memory multiverse initialized successfully.', tags=['system','memory'], source='system'))
    await bus.publish(Event(type='system.boot', payload={'memory': seed.model_dump(mode='json')}))

@app.get('/health')
async def health(): return {'status':'ok','service':'noor-backend'}
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
async def vision_frame(frame:VisionFrameIn):
    return await vision_engine.ingest(VisionFrame(**frame.model_dump()))
@app.get('/api/vision/inspect')
async def vision_inspect(source:str, objective:str):
    return await vision_engine.inspect(source, objective)
@app.get('/api/mobile/devices')
async def devices(): return await mobile_bridge.devices()
@app.post('/api/mobile/command')
async def mobile_command(c:DeviceCommand): return await mobile_bridge.command(c)
@app.websocket('/ws')
async def websocket(ws:WebSocket):
    await bus.connect(ws)
    try:
        while True:
            data=await ws.receive_json(); await bus.publish(Event(type='client.message', payload=data))
    except WebSocketDisconnect: bus.disconnect(ws)
