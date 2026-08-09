import asyncio
import base64
import sys
from pathlib import Path
from app.agents import Coordinator
from app.llm_client import LocalLLMClient
from app.mobile_bridge import MobileBridge
from app.policy import policy_gate
from app.schemas import CommandRequest, DeviceCommand, Event, MemoryIn, Risk
from app.memory import SpatialMemoryAgent
from app.vision import VisionFrame, LiveVisionContextEngine
from app.self_healing import SelfHealingExecutor


def test_policy_blocks_high_risk_actions():
    risk, confirm, _ = policy_gate.assess('delete this account security settings')
    assert risk is Risk.high
    assert confirm is True


def test_spatial_memory_assigns_realms_and_coordinates():
    agent = SpatialMemoryAgent()
    memory = agent.add(MemoryIn(title='Android ADB screen', content='mobile phone notification screen', tags=['adb'], importance=9))
    assert memory.realm == 'Mobile Systems World'
    assert {'x', 'y', 'z'} == set(memory.position)
    assert 0.0 < memory.brightness <= 1.0


def test_memory_boundary_distribution_has_low_coordinate_collision_rate():
    agent = SpatialMemoryAgent()
    coords = set()
    for i in range(300):
        mem = agent.add(MemoryIn(title=f'code file {i}', content=f'repo api function boundary {i}', importance=(i % 10) + 1))
        coords.add((mem.position['x'], mem.position['y'], mem.position['z']))
    assert len(coords) > 285


def test_vision_handles_bad_base64_zero_dimensions_and_4k_scaling():
    async def run():
        engine = LiveVisionContextEngine(max_frames=2)
        bad = await engine.ingest(VisionFrame(source='mobile', width=-10, height=0, mime='image/png', data_base64='bad!!'))
        assert bad['width'] == 1
        assert bad['height'] == 1
        assert len(bad['regions']) == 9
        huge = await engine.ingest(VisionFrame(source='mobile', width=7680, height=4320, mime='image/png', data_base64=''))
        assert huge['width'] * huge['height'] <= engine.max_pixels
        inspected = await engine.inspect('mobile', 'tap top right button')
        assert inspected['target_region']['label'] == 'top-right'
    asyncio.run(run())


def test_self_healing_recovers_after_failure():
    async def run():
        attempts = {'count': 0}
        engine_payload = base64.b64encode(b'frame').decode()
        from app.vision import vision_engine
        await vision_engine.ingest(VisionFrame(source='desktop', width=300, height=300, mime='image/png', data_base64=engine_payload))
        async def action(_attempt, plan):
            attempts['count'] += 1
            if attempts['count'] == 1:
                raise RuntimeError('selector drift')
            return {'plan': plan}
        result = await SelfHealingExecutor(max_attempts=2).run('test', action, 'desktop', 'click middle center')
        assert result.ok is True
        assert result.attempts == 2
        assert result.result['plan']['target_region']['label'] == 'middle-center'
    asyncio.run(run())


def test_orchestrator_high_concurrency_policy_interventions():
    async def run():
        coordinator = Coordinator()
        prompts = [CommandRequest(prompt=f'remember code memory {i}') for i in range(40)]
        prompts += [CommandRequest(prompt=f'delete account setting {i}') for i in range(15)]
        results = await asyncio.gather(*(coordinator.execute(p) for p in prompts))
        assert len(results) == 55
        assert sum(r.status.value == 'waiting_user' for r in results) == 15
        assert len(await coordinator.list_tasks()) == 55
    asyncio.run(run())


def test_adb_timeout_forces_process_exit(tmp_path, monkeypatch):
    from app import mobile_bridge as module
    monkeypatch.setattr(module.settings, 'noor_enable_mobile_bridge', True)
    sleeper = tmp_path / 'adb'
    sleeper.write_text(f'#!{sys.executable}\nimport time\ntime.sleep(30)\n')
    sleeper.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path))
    async def run():
        bridge = MobileBridge()
        try:
            await bridge.run('devices', timeout=0.1)
        except RuntimeError as exc:
            assert 'timed out' in str(exc)
        else:
            raise AssertionError('timeout did not raise')
    asyncio.run(run())


def test_llm_stream_parser_repairs_malformed_lines():
    client = LocalLLMClient(base_url='http://localhost:1')
    assert client._parse_line('data: [DONE]').done is True
    assert client._parse_line('not-json').raw['malformed'] is True
    parsed = client._parse_line('{"choices":[{"delta":{"content":"hi"}}]}')
    assert parsed.text == 'hi'


def test_hybrid_routing_local_vs_cloud(monkeypatch):
    from app import llm_client as module
    monkeypatch.setattr(module.settings, 'llm_mode', 'hybrid')
    monkeypatch.setattr(module.settings, 'openai_api_key', 'test-openai-key')
    monkeypatch.setattr(module.settings, 'anthropic_api_key', '')
    monkeypatch.setattr(module.settings, 'gemini_api_key', '')
    client = module.HybridLLMClient(base_url='http://localhost:1')
    assert client.route('summarize UI logs', risk='low').provider.value == 'local'
    assert client.route('security audit policy analysis', risk='high').provider.value == 'openai'


def test_hybrid_routing_cloud_without_key_falls_back_to_local(monkeypatch):
    from app import llm_client as module
    monkeypatch.setattr(module.settings, 'llm_mode', 'cloud')
    monkeypatch.setattr(module.settings, 'openai_api_key', '')
    monkeypatch.setattr(module.settings, 'anthropic_api_key', '')
    monkeypatch.setattr(module.settings, 'gemini_api_key', '')
    client = module.HybridLLMClient(base_url='http://localhost:1')
    decision = client.route('deep research task', risk='high')
    assert decision.provider.value == 'local'
    assert 'no API key' in decision.reason


def test_provider_payload_normalization_for_tool_and_vision_shapes():
    client = LocalLLMClient(base_url='http://localhost:1')
    openai = client._normalize_payload({'choices': [{'delta': {'content': 'ok', 'tool_calls': [{'id': 'tool'}]}}]}, 'openai')
    assert openai.text == 'ok'
    assert openai.tool_calls[0]['id'] == 'tool'
    anthropic = client._normalize_payload({'type': 'content_block_delta', 'delta': {'text': 'hello'}}, 'anthropic')
    assert anthropic.text == 'hello'
    gemini = client._normalize_payload({'candidates': [{'content': {'parts': [{'text': 'vision'}, {'functionCall': {'name': 'inspect'}}]}, 'finishReason': 'STOP'}]}, 'gemini')
    assert gemini.text == 'vision'
    assert gemini.tool_calls[0]['name'] == 'inspect'
    assert gemini.done is True


def test_local_failure_can_fallback_without_leaking_api_key(monkeypatch):
    from app import llm_client as module
    monkeypatch.setattr(module.settings, 'llm_mode', 'hybrid')
    monkeypatch.setattr(module.settings, 'openai_api_key', 'redacted-test-key')
    monkeypatch.setattr(module.settings, 'hybrid_fallback_enabled', True)
    client = module.HybridLLMClient(base_url='http://localhost:1')
    assert client._is_local_failure_retryable(RuntimeError('CUDA OOM')) is True
    assert 'redacted-test-key' not in str(client.route('security audit', risk='high'))


def test_policy_intent_context_action_confidence():
    assessment = policy_gate.analyze('please send message about security settings', context={'external_effect': True})
    assert assessment.intent == 'operate'
    assert assessment.action_class == 'user_visible_or_destructive_action'
    assert assessment.confidence >= 0.6
    assert assessment.requires_confirmation is True
    low = policy_gate.analyze('summarize account architecture notes')
    assert low.risk in {Risk.low, Risk.medium}
    assert low.requires_confirmation is False


def test_memory_deduplicates_and_ranks_title_tags_content():
    agent = SpatialMemoryAgent()
    first = agent.add(MemoryIn(title='API timeout fix', content='backend retry code', tags=['python'], importance=3))
    duplicate = agent.add(MemoryIn(title='API timeout fix', content='backend retry code', tags=['python'], importance=9))
    agent.add(MemoryIn(title='other', content='api timeout mentioned only in content', tags=[], importance=1))
    assert first.id == duplicate.id
    results = agent.search('api timeout python')
    assert results[0].id == first.id
    assert results[0].importance == 9


def test_vision_declares_grid_fallback_and_low_confidence_without_direction():
    async def run():
        engine = LiveVisionContextEngine(max_frames=1)
        frame = await engine.ingest(VisionFrame(source='desk', width=100, height=100, mime='text/plain', data_base64='%%%'))
        assert frame['mode'] == 'grid_fallback'
        assert 'invalid_base64' in frame['warnings']
        inspected = await engine.inspect('desk', 'find the submit button')
        assert inspected['mode'] == 'grid_fallback'
        assert 'does not identify visual objects' in inspected['strategy']
        assert inspected['confidence'] <= 0.25
    asyncio.run(run())


def test_self_healing_rejects_low_confidence_plan():
    async def run():
        attempts = {'count': 0}
        async def action(_attempt, plan):
            attempts['count'] += 1
            assert plan is None
            raise RuntimeError('still broken')
        result = await SelfHealingExecutor(max_attempts=2, timeout_seconds=1).run('reject-plan', action, 'missing-source', 'find submit button')
        assert result.ok is False
        assert result.recovery_plan is None
        assert attempts['count'] == 2
    asyncio.run(run())


def test_mobile_args_validation_and_text_sanitizing(monkeypatch):
    from app import mobile_bridge as module
    monkeypatch.setattr(module.settings, 'noor_enable_mobile_bridge', True)
    bridge = MobileBridge()
    assert bridge._args_for(DeviceCommand(action='text', text='hello % world\n'))[-1] == 'hello%sworld'
    try:
        bridge._validate_args(('devices', ''))
    except ValueError as exc:
        assert 'invalid adb argument' in str(exc)
    else:
        raise AssertionError('invalid argument accepted')


def test_event_bus_origin_and_history():
    from app.websocket import EventBus
    bus2 = EventBus(history_limit=2)
    assert bus2._origin_allowed('http://localhost:3000') is True
    assert bus2._origin_allowed(None) is False
    assert bus2._origin_allowed('http://evil.example') is False
    async def run():
        await bus2.publish(Event(type='one', payload={}))
        await bus2.publish(Event(type='two', payload={}))
        await bus2.publish(Event(type='three', payload={}))
        assert [e.type for e in bus2.history] == ['two', 'three']
    asyncio.run(run())


def test_backend_smoke_health_and_command():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        health = client.get('/health')
        assert health.status_code == 200
        assert health.json()['safe_defaults']['browser_automation'] is False
        assert health.json()['safe_defaults']['mobile_bridge'] is False
        assert health.json()['persistence']['status'] in {'ok', 'locked'}
        res = client.post('/api/command', json={'prompt': 'remember api smoke test', 'context': {}})
        assert res.status_code == 200
        assert res.json()['status'] == 'completed'


def test_mobile_disabled_path_is_explicit(monkeypatch):
    from app import mobile_bridge as module
    monkeypatch.setattr(module.settings, 'noor_enable_mobile_bridge', False)
    bridge = MobileBridge()
    try:
        bridge._validate_args(('devices',))
    except RuntimeError as exc:
        assert 'disabled by configuration' in str(exc)
    else:
        raise AssertionError('disabled mobile bridge accepted args')


def test_browser_disabled_path_is_explicit(monkeypatch):
    from app import browser_engine as module
    monkeypatch.setattr(module.settings, 'noor_enable_browser_automation', False)
    async def run():
        try:
            await module.BrowserEngine().run_safe_search('docs')
        except RuntimeError as exc:
            assert 'disabled by configuration' in str(exc)
        else:
            raise AssertionError('disabled browser automation ran')
    asyncio.run(run())


def test_websocket_bounded_replay_and_command_event_smoke():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.websocket import bus
    async def seed():
        await bus.publish(Event(type='release.one', payload={}))
        await bus.publish(Event(type='release.two', payload={}))
    asyncio.run(seed())
    with TestClient(app) as client:
        with client.websocket_connect('/ws', headers={'origin': 'http://localhost:3000'}) as ws:
            seen = [ws.receive_json() for _ in range(50)]
            types = [e['type'] for e in seen]
            assert 'release.one' in types and 'release.two' in types
        res = client.post('/api/command', json={'prompt': 'remember release smoke command', 'context': {}})
        assert res.status_code == 200
        assert res.json()['status'] == 'completed'


def test_final_e2e_cognitive_operational_persistence_smoke(tmp_path):
    from app.cognitive_core import CognitiveCore
    c = CognitiveCore(tmp_path/'release_state.json', limits={'max_events':500,'max_browser_requests':3,'tick_budget_ms':5})
    ev = c.ingest_evidence('release candidate has_state tested', 'release_smoke', 'test', 0.9, 'supports', 0.8)
    assert ev.id in c.evidence and c.world
    plan = c.create_plan('search docs release smoke')
    out = c.execute_plan(plan.plan_id, {'step_1': {'success': False, 'actual_outcome': 'timeout', 'error_type': 'timeout'}})
    assert out['status'] in {'recovering','blocked','failed'}
    assert c.actions and c.failures and c.skills
    c.run_inquiry_results('release docs are documented', [{'title': 'Release docs', 'url': 'https://docs.example.test/release', 'content': 'official manual evidence'}])
    tick = c.tick()
    assert tick['events'] <= c.limits['max_events']
    c.save(); restarted = CognitiveCore(tmp_path/'release_state.json')
    assert restarted.evidence and restarted.beliefs and restarted.world and restarted.actions and restarted.failures


def test_release_claim_audit_and_secret_hygiene():
    root = Path(__file__).resolve().parents[2]
    files = [p for p in [root/'README.md', root/'FINAL_RELEASE_REPORT.md', root/'NOOR_ENTITY_EVOLUTION_REPORT.md', root/'frontend/app/page.tsx', root/'frontend/components/MobileMirror.tsx', root/'frontend/components/AgentGraph.tsx'] if p.exists()]
    text = '\n'.join(p.read_text().lower() for p in files)
    forbidden = ['self-aware = true', 'living entity capability', 'provides full multimodal understanding', 'unbounded general autonomy', 'consciousness = true']
    assert all(term not in text for term in forbidden)
    assert 'prototype' in text and 'disabled by default' in text
    tracked_text = '\n'.join(p.read_text(errors='ignore') for p in [root/'.env.example', root/'README.md', root/'FINAL_RELEASE_REPORT.md'])
    assert 'sk-secret' not in tracked_text and 'test-openai-key' not in tracked_text
