import asyncio
import time
from pathlib import Path
from .schemas import Event
from .self_healing import self_healing_executor
from .websocket import bus

class BrowserEngine:
    def __init__(self):
        self.last_action: dict[str, float] = {}
        self.profile_root = Path('playwright_profiles')

    async def run_safe_search(self, query: str):
        now = time.time()
        key = 'search'
        if now - self.last_action.get(key, 0) < 3:
            await asyncio.sleep(3)
        self.last_action[key] = time.time()

        async def attempt(_attempt: int, recovery_plan):
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                ctx = await p.chromium.launch_persistent_context(str(self.profile_root / 'default'), headless=True)
                page = await ctx.new_page()
                await page.goto('https://example.com', wait_until='domcontentloaded')
                if recovery_plan:
                    await page.mouse.move(10, 10)
                title = await page.title()
                await ctx.close()
                return {'title': title, 'query': query}

        result = await self_healing_executor.run('browser.safe_search', attempt, 'desktop', query)
        event_type = 'browser.result' if result.ok else 'browser.error'
        await bus.publish(Event(type=event_type, payload=result.__dict__))
        return result.__dict__

browser_engine = BrowserEngine()
