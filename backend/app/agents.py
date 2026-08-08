import asyncio
import logging
from .browser_engine import browser_engine
from .memory import spatial_memory
from .policy import policy_gate
from .schemas import CommandRequest, Event, MemoryIn, Status, TaskRecord
from .websocket import bus

logger = logging.getLogger('noor.agents')

class Coordinator:
    def __init__(self):
        self.tasks: dict[str, TaskRecord] = {}
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(12)

    async def execute(self, req: CommandRequest):
        async with self.semaphore:
            risk, confirm, reason = policy_gate.assess(req.prompt)
            task = TaskRecord(prompt=req.prompt, risk=risk, status=Status.waiting_user if confirm else Status.running)
            async with self.lock:
                self.tasks[task.id] = task
            await bus.publish(Event(type='task.created', payload=task.model_dump(mode='json') | {'policy_reason': reason}))
            if confirm:
                task.result = 'Action paused by policy gate.'
                return task
            try:
                text = req.prompt.lower()
                if 'remember' in text:
                    mem = spatial_memory.add(MemoryIn(title=req.prompt[:80], content=req.prompt, source='command'))
                    await bus.publish(Event(type='memory.created', payload=mem.model_dump(mode='json')))
                    task.result = f'Stored memory in {mem.realm}.'
                elif 'browser' in text:
                    res = await browser_engine.run_safe_search(req.prompt)
                    task.result = str(res)
                else:
                    mem = spatial_memory.add(MemoryIn(title='Task episode', content=req.prompt, source='episode', importance=4))
                    await bus.publish(Event(type='memory.created', payload=mem.model_dump(mode='json')))
                    task.result = 'Noor coordinator analyzed the request and recorded an episodic memory.'
                task.status = Status.completed
                await bus.publish(Event(type='task.completed', payload=task.model_dump(mode='json')))
            except Exception as exc:
                logger.exception('task failed')
                task.status = Status.failed
                task.result = str(exc)
                await bus.publish(Event(type='task.failed', payload=task.model_dump(mode='json')))
            return task

    async def list_tasks(self):
        async with self.lock:
            return list(self.tasks.values())

coordinator = Coordinator()
