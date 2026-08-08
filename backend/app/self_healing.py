import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from .schemas import Event
from .vision import vision_engine
from .websocket import bus

logger = logging.getLogger('noor.recovery')

@dataclass
class RecoveryResult:
    ok: bool
    attempts: int
    result: Any = None
    error: str | None = None
    recovery_plan: dict[str, Any] | None = None

class SelfHealingExecutor:
    def __init__(self, max_attempts: int = 3, timeout_seconds: float = 20.0):
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds

    def _valid_plan(self, plan: dict[str, Any] | None) -> bool:
        if not plan or not isinstance(plan, dict):
            return False
        region = plan.get('target_region')
        return bool(region and region.get('center') and plan.get('confidence', 0) >= 0.3)

    async def run(self, name: str, action: Callable[[int, dict[str, Any] | None], Awaitable[Any]], source: str, objective: str) -> RecoveryResult:
        recovery_plan: dict[str, Any] | None = None
        last_error: str | None = None
        for attempt in range(1, self.max_attempts + 1):
            await bus.publish(Event(type='recovery.attempt', payload={'name': name, 'attempt': attempt, 'objective': objective}))
            try:
                result = await asyncio.wait_for(action(attempt, recovery_plan), timeout=self.timeout_seconds)
                await bus.publish(Event(type='recovery.success', payload={'name': name, 'attempts': attempt}))
                return RecoveryResult(ok=True, attempts=attempt, result=result, recovery_plan=recovery_plan)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = str(exc)
                logger.warning('self-healing attempt failed for %s attempt=%s error=%s', name, attempt, last_error)
                candidate = await vision_engine.inspect(source, objective)
                recovery_plan = candidate if self._valid_plan(candidate) else None
                await bus.publish(Event(type='recovery.visual_reinspect', payload={'name': name, 'error': last_error, 'plan': recovery_plan, 'plan_valid': recovery_plan is not None}))
                await asyncio.sleep(min(2.0, 0.2 * attempt))
        await bus.publish(Event(type='recovery.failed', payload={'name': name, 'error': last_error, 'attempts': self.max_attempts}))
        return RecoveryResult(ok=False, attempts=self.max_attempts, error=last_error or 'unknown failure', recovery_plan=recovery_plan)

self_healing_executor = SelfHealingExecutor()
