import asyncio,time,urllib.parse
from pathlib import Path
from .config import settings
from .schemas import Event
from .self_healing import self_healing_executor
from .websocket import bus

class BrowserEngine:
    def __init__(self): self.last_action={}; self.profile_root=Path('playwright_profiles'); self.search_url='https://duckduckgo.com/html/'
    def _clean_query(self, query:str)->str:
        cleaned=' '.join((query or '').split())[:300]
        if not cleaned: raise ValueError('browser search query is empty')
        return cleaned
    async def run_safe_search(self, query: str):
        if not settings.noor_enable_browser_automation: raise RuntimeError('browser automation is disabled by configuration')
        query=self._clean_query(query); now=time.time(); key='search'
        wait=max(0,2.0-(now-self.last_action.get(key,0)))
        if wait: await asyncio.sleep(wait)
        self.last_action[key]=time.time()
        async def attempt(_attempt:int,recovery_plan):
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                ctx=await p.chromium.launch_persistent_context(str(self.profile_root/'default'), headless=True)
                try:
                    page=await ctx.new_page(); url=f'{self.search_url}?q={urllib.parse.quote_plus(query)}'
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    links=await page.locator('a.result__a').evaluate_all("els => els.slice(0,5).map(a => ({title:a.innerText.trim(), url:a.href}))")
                    title=await page.title()
                    return {'query':query,'url':url,'page_title':title,'results':links,'result_count':len(links),'recovery_used':bool(recovery_plan)}
                finally:
                    await ctx.close()
        result=await self_healing_executor.run('browser.safe_search',attempt,'desktop',query)
        await bus.publish(Event(type='browser.result' if result.ok else 'browser.error', payload=result.__dict__))
        return result.__dict__
browser_engine=BrowserEngine()
