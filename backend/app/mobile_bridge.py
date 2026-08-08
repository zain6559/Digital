import asyncio
import logging
import os
import shutil
import signal
import shlex
from .config import settings
from .schemas import DeviceCommand, Event
from .self_healing import self_healing_executor
from .websocket import bus

logger = logging.getLogger('noor.mobile')

class MobileBridge:
    def adb(self):
        path = shutil.which('adb')
        if not path:
            raise RuntimeError('adb executable not found')
        return path

    async def _terminate(self, proc: asyncio.subprocess.Process):
        if proc.returncode is not None:
            return
        try:
            if os.name != 'nt':
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except Exception:
            try:
                if os.name != 'nt':
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            finally:
                await proc.wait()

    def _validate_args(self, args):
        if not settings.noor_enable_mobile_bridge:
            raise RuntimeError('mobile bridge is disabled by configuration')
        if not args or any(not isinstance(a, str) or not a or '\x00' in a for a in args):
            raise ValueError('invalid adb argument')
        return [str(a) for a in args]

    async def run(self, *args, timeout: float = 15.0):
        args = self._validate_args(args)
        kwargs = {'stdout': asyncio.subprocess.PIPE, 'stderr': asyncio.subprocess.PIPE}
        if os.name != 'nt':
            kwargs['preexec_fn'] = os.setsid
        proc = await asyncio.create_subprocess_exec(self.adb(), *args, **kwargs)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            await self._terminate(proc)
            raise RuntimeError(f'adb command timed out after {timeout:.1f}s: {shlex.join(args)}')
        except Exception:
            await self._terminate(proc)
            raise
        if proc.returncode != 0:
            raise RuntimeError(err.decode(errors='replace').strip() or out.decode(errors='replace').strip() or 'adb command failed')
        return proc.returncode, out.decode(errors='replace'), err.decode(errors='replace')

    async def devices(self):
        try:
            code, out, err = await self.run('devices', '-l')
            await bus.publish(Event(type='mobile.devices', payload={'output': out, 'error': err, 'code': code}))
            return {'code': code, 'output': out, 'error': err}
        except Exception as e:
            logger.warning('adb device scan failed: %s', e)
            await bus.publish(Event(type='mobile.error', payload={'error': str(e)}))
            return {'code': 1, 'output': '', 'error': str(e)}

    def _args_for(self, c: DeviceCommand, recovery_plan=None):
        serial = ['-s', c.serial] if c.serial else []
        if c.action == 'tap':
            x, y = c.x, c.y
            if recovery_plan and recovery_plan.get('target_region'):
                x, y = recovery_plan['target_region']['center']
            if x is not None and y is not None:
                x = max(0, min(int(x), 7680))
                y = max(0, min(int(y), 4320))
                return serial + ['shell', 'input', 'tap', str(x), str(y)]
        if c.action == 'text' and c.text:
            safe = '%s'.join(''.join(ch for ch in c.text if ch.isprintable()).replace('%', '').split())[:256]
            return serial + ['shell', 'input', 'text', safe]
        if c.action == 'wake':
            return serial + ['shell', 'input', 'keyevent', 'KEYCODE_WAKEUP']
        raise ValueError(f'unsupported or incomplete mobile command: {c.action}')

    async def command(self, c: DeviceCommand):
        async def attempt(_attempt: int, recovery_plan):
            args = self._args_for(c, recovery_plan)
            code, out, err = await self.run(*args)
            return {'code': code, 'output': out, 'error': err, 'args': args}
        result = await self_healing_executor.run('mobile.command', attempt, 'mobile', c.objective or c.action)
        await bus.publish(Event(type='mobile.command', payload={'action': c.action, 'ok': result.ok, 'attempts': result.attempts}))
        return result.__dict__

mobile_bridge = MobileBridge()
