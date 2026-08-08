import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator
import httpx
from .config import settings
from .schemas import Event
from .websocket import bus

logger = logging.getLogger('noor.llm')

class Provider(str, Enum):
    local = 'local'
    openai = 'openai'
    anthropic = 'anthropic'
    gemini = 'gemini'

@dataclass
class LLMChunk:
    text: str
    raw: dict[str, Any]
    provider: str = 'local'
    done: bool = False
    tool_calls: list[dict[str, Any]] | None = None

@dataclass
class RoutingDecision:
    provider: Provider
    reason: str
    allow_fallback: bool
    model: str

class LLMProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code

class HybridLLMClient:
    def __init__(self, base_url: str | None = None, timeout: float = 45.0):
        self.base_url = (base_url or settings.local_llm_base_url).rstrip('/')
        self.timeout = timeout

    def _has_cloud_key(self, provider: Provider | None = None) -> bool:
        keys = {
            Provider.openai: settings.openai_api_key,
            Provider.anthropic: settings.anthropic_api_key,
            Provider.gemini: settings.gemini_api_key,
        }
        if provider:
            return bool(keys.get(provider))
        return any(bool(v) for v in keys.values())

    def _preferred_cloud_provider(self) -> Provider:
        if settings.openai_api_key:
            return Provider.openai
        if settings.anthropic_api_key:
            return Provider.anthropic
        if settings.gemini_api_key:
            return Provider.gemini
        return Provider.local

    def route(self, task: str, risk: str = 'low', modality: str = 'text') -> RoutingDecision:
        mode = settings.llm_mode.lower()
        task_l = task.lower()
        complex_markers = {'deep research', 'multi-step', 'architecture', 'security audit', 'policy analysis', 'legal', 'financial'}
        needs_cloud = risk in {'high', 'critical'} or modality == 'vision' or any(marker in task_l for marker in complex_markers)
        fallback = settings.hybrid_fallback_enabled
        if mode == 'local':
            return RoutingDecision(Provider.local, 'LLM_MODE=local', False, settings.local_model_name)
        if mode == 'cloud':
            provider = self._preferred_cloud_provider()
            return RoutingDecision(provider if provider != Provider.local else Provider.local, 'LLM_MODE=cloud' if provider != Provider.local else 'cloud requested but no API key available', fallback, settings.cloud_model_name)
        if needs_cloud and self._has_cloud_key():
            return RoutingDecision(self._preferred_cloud_provider(), 'hybrid escalation for complex/high-risk task', fallback, settings.cloud_model_name)
        return RoutingDecision(Provider.local, 'hybrid local-first route', fallback, settings.local_model_name)

    def _parse_line(self, line: str, provider: str = 'local') -> LLMChunk | None:
        line = line.strip()
        if not line:
            return None
        if line.startswith('data:'):
            line = line[5:].strip()
        if line == '[DONE]':
            return LLMChunk(text='', raw={}, provider=provider, done=True)
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return LLMChunk(text=line, raw={'malformed': True}, provider=provider, done=False)
        return self._normalize_payload(payload, provider)

    def _normalize_payload(self, payload: dict[str, Any], provider: str) -> LLMChunk:
        text = ''
        done = False
        tool_calls: list[dict[str, Any]] = []
        if provider in {'local', 'openai'}:
            choice = (payload.get('choices') or [{}])[0]
            delta = choice.get('delta') or choice.get('message') or {}
            text = delta.get('content') or payload.get('response') or payload.get('content') or ''
            tool_calls = delta.get('tool_calls') or choice.get('message', {}).get('tool_calls') or []
            done = bool(payload.get('done') or choice.get('finish_reason'))
        elif provider == 'anthropic':
            if payload.get('type') == 'content_block_delta':
                text = payload.get('delta', {}).get('text', '')
            elif payload.get('content'):
                text = ''.join(block.get('text', '') for block in payload.get('content', []) if block.get('type') == 'text')
            tool_calls = [block for block in payload.get('content', []) if block.get('type') == 'tool_use']
            done = payload.get('type') in {'message_stop', 'content_block_stop'} or bool(payload.get('stop_reason'))
        elif provider == 'gemini':
            candidates = payload.get('candidates') or []
            parts = (((candidates[0] if candidates else {}).get('content') or {}).get('parts') or [])
            text = ''.join(part.get('text', '') for part in parts)
            tool_calls = [part.get('functionCall') for part in parts if part.get('functionCall')]
            done = bool((candidates[0] if candidates else {}).get('finishReason'))
        return LLMChunk(text=text, raw={'provider': provider}, provider=provider, done=done, tool_calls=tool_calls or None)

    def _headers(self, provider: Provider) -> dict[str, str]:
        if provider == Provider.openai:
            return {'Authorization': f'Bearer {settings.openai_api_key}', 'Content-Type': 'application/json'}
        if provider == Provider.anthropic:
            return {'x-api-key': settings.anthropic_api_key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'}
        if provider == Provider.gemini:
            return {'Content-Type': 'application/json'}
        return {'Content-Type': 'application/json'}

    def _url(self, provider: Provider) -> str:
        if provider == Provider.local:
            return f'{self.base_url}/v1/chat/completions'
        if provider == Provider.openai:
            return 'https://api.openai.com/v1/chat/completions'
        if provider == Provider.anthropic:
            return 'https://api.anthropic.com/v1/messages'
        return f'https://generativelanguage.googleapis.com/v1beta/models/{settings.cloud_model_name}:streamGenerateContent?key={settings.gemini_api_key}'

    def _payload(self, provider: Provider, messages: list[dict[str, str]], model: str) -> dict[str, Any]:
        if provider in {Provider.local, Provider.openai}:
            return {'model': model, 'messages': messages, 'stream': True}
        if provider == Provider.anthropic:
            system = '\n'.join(m['content'] for m in messages if m.get('role') == 'system')
            user_messages = [m for m in messages if m.get('role') != 'system']
            return {'model': model, 'system': system, 'messages': user_messages, 'max_tokens': 2048, 'stream': True}
        return {'contents': [{'role': 'user' if m.get('role') != 'assistant' else 'model', 'parts': [{'text': m.get('content', '')}]} for m in messages]}

    async def _stream_provider(self, provider: Provider, messages: list[dict[str, str]], model: str) -> AsyncIterator[LLMChunk]:
        timeout = httpx.Timeout(self.timeout, connect=10.0, read=self.timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream('POST', self._url(provider), headers=self._headers(provider), json=self._payload(provider, messages, model)) as response:
                if response.status_code in {401, 403, 429}:
                    raise LLMProviderError(f'{provider.value} API rejected request with status {response.status_code}', retryable=response.status_code == 429, status_code=response.status_code)
                response.raise_for_status()
                async for line in response.aiter_lines():
                    chunk = self._parse_line(line, provider.value)
                    if chunk:
                        yield chunk
                        if chunk.done:
                            return

    def _is_local_failure_retryable(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return any(marker in text for marker in ['cuda', 'oom', 'out of memory', 'timeout', 'malformed', 'connection', 'readerror'])

    async def stream_chat(self, messages: list[dict[str, str]], model: str | None = None, task: str = '', risk: str = 'low', modality: str = 'text') -> AsyncIterator[LLMChunk]:
        decision = self.route(task or ' '.join(m.get('content', '') for m in messages), risk=risk, modality=modality)
        active_model = model or decision.model
        await bus.publish(Event(type='llm.route', payload={'provider': decision.provider.value, 'reason': decision.reason, 'fallback': decision.allow_fallback, 'model': active_model}))
        try:
            async for chunk in self._stream_provider(decision.provider, messages, active_model):
                yield chunk
        except (httpx.TimeoutException, httpx.HTTPError, LLMProviderError, json.JSONDecodeError) as exc:
            logger.warning('LLM provider failed provider=%s error=%s', decision.provider.value, exc)
            can_fallback = decision.allow_fallback and decision.provider == Provider.local and self._has_cloud_key() and self._is_local_failure_retryable(exc)
            if can_fallback:
                provider = self._preferred_cloud_provider()
                await bus.publish(Event(type='llm.fallback', payload={'from': 'local', 'to': provider.value, 'reason': type(exc).__name__}))
                try:
                    async for chunk in self._stream_provider(provider, messages, settings.cloud_model_name):
                        yield chunk
                    return
                except Exception as fallback_exc:
                    logger.warning('LLM fallback failed provider=%s error=%s', provider.value, fallback_exc)
                    await bus.publish(Event(type='llm.stream_error', payload={'provider': provider.value, 'error': type(fallback_exc).__name__}))
            else:
                await bus.publish(Event(type='llm.stream_error', payload={'provider': decision.provider.value, 'error': type(exc).__name__, 'status_code': getattr(exc, 'status_code', None)}))
            yield LLMChunk(text='', raw={'error': type(exc).__name__}, provider=decision.provider.value, done=True)

LocalLLMClient = HybridLLMClient
local_llm_client = HybridLLMClient()
