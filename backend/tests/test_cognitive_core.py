from pathlib import Path
import pytest
from app.cognitive_core import CognitiveCore


def core(tmp_path, **features):
    return CognitiveCore(tmp_path/'state.json', features=features or None, limits={'max_browser_requests':3,'max_events':30000,'tick_budget_ms':5})


def test_belief_requires_evidence_and_revises_with_audit(tmp_path):
    c=core(tmp_path)
    with pytest.raises(ValueError): c.ingest_evidence('x is true','')
    e1=c.ingest_evidence('device has_state broken','sensor','telemetry',0.9,'supports',0.8)
    b=c.beliefs[next(iter(c.beliefs))]
    before=b.confidence
    e2=c.ingest_evidence('device has_state broken','repair_log','telemetry',0.9,'contradicts',0.9)
    b=c.beliefs[b.id]
    assert e1.id in b.evidence and e2.id in b.counter_evidence
    assert b.confidence < before
    assert b.audit_trail[-1]['reason']=='contradicts'
    assert b.contradiction_count == 1


def test_meta_knowledge_unknown_uncertain_known_contradictory(tmp_path):
    c=core(tmp_path)
    assert c.meta_state('missing fact')=='unknown'
    c.ingest_evidence('sky color blue','camera','sensor',0.95,'supports',0.95)
    assert c.meta_state('sky color blue') in {'likely','known'}
    c.ingest_evidence('sky color blue','bad_feed','sensor',0.95,'contradicts',0.95)
    assert c.meta_state('sky color blue') in {'contradictory','suspended','uncertain','rejected'}


def test_world_model_updates_from_evidence(tmp_path):
    c=core(tmp_path)
    c.ingest_evidence('user owns deviceA','inventory','user',0.8,'supports',0.8)
    rel=next(iter(c.world.values()))
    assert rel.subject=='user'
    assert rel.relation=='owns'
    assert rel.object=='deviceA'
    assert rel.confidence > 0.5


def test_inquiry_decision_is_not_always_search_and_uses_uncertainty(tmp_path):
    c=core(tmp_path)
    assert c.evaluate_inquiry('unknown important fact',0.9)['action']=='search'
    c.ingest_evidence('known fact','manual','user',1.0,'supports',1.0)
    assert c.evaluate_inquiry('known fact',0.2)['action'] in {'act_despite_uncertainty','defer'}
    limited=core(tmp_path, inquiry=True); limited.browser_requests=3
    assert limited.evaluate_inquiry('another unknown fact',1.0)['action']=='defer'


def test_browser_search_cannot_succeed_without_evidence(tmp_path):
    c=core(tmp_path)
    with pytest.raises(ValueError): c.run_inquiry_results('x', [])
    c.run_inquiry_results('x is documented',[{'title':'X docs','url':'https://example.test/x'}])
    assert c.knows('x is documented') is False
    assert c.meta_state('x is documented') in {'likely','uncertain'}


def test_prediction_outcome_learning_updates_belief_and_self_model(tmp_path):
    c=core(tmp_path)
    c.ingest_evidence('tap causes wake','test','system',0.9,'supports',0.8)
    bid=next(iter(c.beliefs))
    p=c.create_prediction('mobile tap','wake',0.8,[bid])
    c.record_outcome(p.id,'no_wake')
    assert c.predictions[p.id].error == pytest.approx(0.8)
    assert c.self_model()['mobile']['prediction_count']==1
    assert c.beliefs[bid].counter_evidence


def test_persistence_survives_restart(tmp_path):
    c=core(tmp_path)
    c.create_goal('verify device state',0.7,'test',['state known'])
    c.ingest_evidence('device has_state ready','fixture','test',0.8,'supports',0.8)
    c.create_prediction('device check','ready',0.7, list(c.beliefs))
    c.tick(); c.save()
    c2=core(tmp_path)
    assert c2.beliefs and c2.evidence and c2.world and c2.predictions and c2.goals
    assert c2.tick_count == 1


def test_decision_changes_under_component_ablation(tmp_path):
    full=core(tmp_path)
    no_belief=core(tmp_path, beliefs=False)
    assert full.decide('unknown critical fact',['search','ask_human']).selected_action == 'search'
    assert no_belief.decide('unknown critical fact',['search','ask_human']).selected_action == 'ask_human'
    no_inquiry=core(tmp_path, inquiry=False)
    assert no_inquiry.decide('unknown critical fact',['search','ask_human','reason_internally']).selected_action == 'reason_internally'
    no_auto=core(tmp_path, autonomy=False)
    assert no_auto.tick()['action']=='disabled'


def test_llm_cannot_write_authoritative_state_without_validation(tmp_path):
    c=core(tmp_path)
    with pytest.raises(ValueError): c.ingest_evidence('llm claim', '', 'llm', 0.3, 'supports', 0.5)
    assert not c.beliefs


def test_long_term_10000_ticks_stable_and_bounded(tmp_path):
    c=core(tmp_path)
    c.ingest_evidence('system has_state uncertain','seed','test',0.5,'supports',0.1)
    for _ in range(10_000):
        out=c.tick()
    assert out['tick']==10_000
    assert len(c.events) <= c.limits['max_events']
    assert len(c.beliefs) == 1
    assert c.tick_count == 10_000


def test_causal_memory_world_prediction_self_model_ablation(tmp_path):
    no_memory=core(tmp_path, memory=False)
    no_memory.ingest_evidence('a relates b','src','test',0.8,'supports',0.8)
    assert not no_memory.memory.memories
    no_world=CognitiveCore(tmp_path/'world_off.json', features={'world_model':False})
    no_world.ingest_evidence('a relates b','src','test',0.8,'supports',0.8)
    assert not no_world.world
    no_prediction=CognitiveCore(tmp_path/'prediction_off.json', features={'prediction':False})
    assert no_prediction.create_prediction('x','y',0.5,[]) is None
    no_self=CognitiveCore(tmp_path/'self_off.json', features={'self_model':False})
    p=no_self.create_prediction('domain action','ok',0.9,[])
    no_self.record_outcome(p.id,'bad')
    assert no_self.self_model()=={}


def test_frontend_and_readme_do_not_claim_consciousness():
    root = Path(__file__).resolve().parents[2]
    text = '\n'.join((root/p).read_text().lower() for p in ['README.md','frontend/app/page.tsx','frontend/components/MobileMirror.tsx','frontend/components/MemoryWorlds.tsx','frontend/components/AgentGraph.tsx'])
    forbidden = ['consciousness = true','self-aware = true','i feel','aware entity']
    assert all(term not in text for term in forbidden)
    assert 'prototype' in (root/'README.md').read_text().lower()
