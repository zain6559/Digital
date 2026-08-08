import asyncio, logging
from .browser_engine import browser_engine
from .cognitive_core import cognitive_core
from .memory import spatial_memory
from .policy import policy_gate
from .schemas import CommandRequest, Event, MemoryIn, Status, TaskRecord
from .websocket import bus
logger=logging.getLogger('noor.agents')
class Coordinator:
    def __init__(self): self.tasks={}; self.lock=asyncio.Lock(); self.semaphore=asyncio.Semaphore(12)
    def _route(self, req:CommandRequest)->str:
        text=req.prompt.lower()
        if text.startswith('remember') or req.context.get('intent')=='remember': return 'memory.store'
        if 'browser' in text or 'search web' in text or req.context.get('intent')=='browser.search': return 'browser.search'
        return 'episode.record'
    async def _record_memory(self, title, content, source, importance=4):
        mem=spatial_memory.add(MemoryIn(title=title, content=content, source=source, importance=importance)); await bus.publish(Event(type='memory.created', payload=mem.model_dump(mode='json'))); return mem
    async def execute(self, req: CommandRequest):
        async with self.semaphore:
            route=self._route(req); decision=cognitive_core.decide(req.prompt); risk,confirm,reason=policy_gate.assess(req.prompt, context=req.context)
            task=TaskRecord(prompt=req.prompt,risk=risk,status=Status.waiting_user if confirm else Status.running)
            async with self.lock: self.tasks[task.id]=task
            await bus.publish(Event(type='task.created', payload=task.model_dump(mode='json')|{'policy_reason':reason,'route':route,'decision':decision.__dict__}))
            if confirm:
                task.result='Action paused by policy gate before execution.'; await bus.publish(Event(type='task.blocked', payload=task.model_dump(mode='json')|{'route':route})); return task
            try:
                await bus.publish(Event(type='task.execution_started', payload={'id':task.id,'route':route,'risk':risk.value,'decision':decision.__dict__}))
                if route=='memory.store':
                    mem=await self._record_memory(req.prompt[:80], req.prompt, 'command', 5); cognitive_core.ingest_evidence(req.prompt, 'command', 'user', 0.7, 'supports', 0.55); task.result=f'Stored memory in {mem.realm}.'
                elif route=='browser.search':
                    task.result=str(await browser_engine.run_safe_search(req.prompt))
                else:
                    mem=await self._record_memory('Task episode', req.prompt, 'episode', 4); pred=cognitive_core.create_prediction(req.prompt, 'episode_recorded', 0.8, []);
                    if pred: cognitive_core.record_outcome(pred.id, 'episode_recorded');
                    task.result=f'Recorded task episode in {mem.realm}; no external action was taken.'
                task.status=Status.completed; await bus.publish(Event(type='task.completed', payload=task.model_dump(mode='json')|{'route':route}))
            except Exception as exc:
                logger.exception('task failed'); task.status=Status.failed; task.result=str(exc); await bus.publish(Event(type='task.failed', payload=task.model_dump(mode='json')|{'route':route}))
            return task
    async def list_tasks(self):
        async with self.lock: return list(self.tasks.values())
coordinator=Coordinator()
