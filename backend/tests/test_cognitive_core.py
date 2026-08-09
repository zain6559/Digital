from pathlib import Path
import os
import time
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


def test_semantic_belief_normalization_clusters_aliases_and_contradictions(tmp_path):
    c=core(tmp_path)
    c.ingest_evidence('device is ready','manual','user',0.9,'supports',0.8)
    c.ingest_evidence('the device has state ok','telemetry','telemetry',0.9,'supports',0.8)
    assert len(c.beliefs) == 1
    b=next(iter(c.beliefs.values()))
    assert len(b.aliases) == 2
    c.ingest_evidence('device is broken','repair_log','telemetry',0.9,'supports',0.8)
    assert len(c.beliefs) == 1
    assert b.contradiction_count == 1
    assert c.meta_state('device is not ready') in {'contradictory','suspended','uncertain','rejected'}


def test_world_model_typed_relations_and_ambiguous_state(tmp_path):
    c=core(tmp_path)
    c.ingest_evidence('rain causes wet_ground after storm','weather.gov','browser',None,'supports',0.8)
    rel=next(r for r in c.world.values() if r.relation == 'causes')
    assert rel.relation_type == 'causal'
    assert rel.temporal_hint == 'ordered'
    assert rel.evidence
    c.ingest_evidence('maybe unclear','note','user',0.5,'supports',0.4)
    ambiguous=[r for r in c.world.values() if r.state == 'ambiguous']
    assert ambiguous and ambiguous[0].relation == 'states'


def test_inquiry_uses_importance_contradiction_and_cost(tmp_path):
    c=core(tmp_path)
    assert c.evaluate_inquiry('unknown low value',0.1)['action'] in {'defer','ask_human'}
    assert c.evaluate_inquiry('unknown high value',0.9)['action'] == 'search'
    c.ingest_evidence('device is ready','manual','user',0.9,'supports',0.8)
    c.ingest_evidence('device is broken','sensor','telemetry',0.9,'supports',0.8)
    assert c.evaluate_inquiry('device is ready',0.4)['action'] == 'search'
    assert c.evaluate_inquiry('unknown expensive',0.6,search_cost=0.9)['action'] != 'search'


def test_browser_evidence_scoring_dedupes_and_bad_sources_are_weak(tmp_path):
    good=core(tmp_path)
    good.run_inquiry_results('x is documented',[{'title':'Official X docs','url':'https://docs.example.test/x','content':'official manual evidence'}])
    good_conf=next(iter(good.beliefs.values())).confidence
    bad=core(tmp_path/'bad')
    bad.run_inquiry_results('x is documented',[{'title':'Rumor docs about X','url':'https://spam.example/x','content':'thin unofficial manual evidence '*20}])
    bad_conf=next(iter(bad.beliefs.values())).confidence
    assert good_conf > bad_conf
    dedupe=core(tmp_path/'dedupe')
    ev=dedupe.run_inquiry_results('y is documented',[
        {'title':'Official Y docs','url':'https://docs.example.test/y','content':'official manual evidence'},
        {'title':'Official Y docs copy','url':'https://docs.example.test/y2','content':'official manual evidence'},
    ])
    assert len(ev) == 1
    assert dedupe.meta_state('y is documented') != 'known'


def test_search_failure_is_observable_and_low_value_rejected(tmp_path):
    c=core(tmp_path)
    with pytest.raises(ValueError):
        c.run_inquiry_results('z fact',[{'title':'', 'url':'https://example.test/z'}])
    assert c.events[-1]['type'] == 'inquiry.search_failed'
    assert not c.beliefs


def test_self_model_differs_by_domain_and_flags_weakness(tmp_path):
    c=core(tmp_path)
    pm=c.create_prediction('mobile tap','wake',0.8,[])
    c.record_outcome(pm.id,'no_wake')
    pb=c.create_prediction('browser search','results',0.8,[])
    c.record_outcome(pb.id,'results')
    sm=c.self_model()
    assert sm['mobile']['mean_error'] > sm['browser']['mean_error']
    assert sm['mobile']['should_ask_for_help'] is True
    assert sm['browser']['strong'] is True


def test_persistence_version_atomic_and_partial_write_does_not_corrupt(tmp_path, monkeypatch):
    c=core(tmp_path)
    c.ingest_evidence('device ready','manual','user',0.8,'supports',0.8)
    path=c.path
    original=path.read_text()
    real_replace=os.replace
    def boom(src, dst):
        raise RuntimeError('simulated partial write')
    monkeypatch.setattr(os, 'replace', boom)
    with pytest.raises(RuntimeError):
        c.save()
    monkeypatch.setattr(os, 'replace', real_replace)
    assert path.read_text() == original
    c2=core(tmp_path)
    assert c2.version >= 1 and c2.beliefs


def test_persistence_active_lock_is_explicit_and_stale_lock_recovers(tmp_path):
    c=core(tmp_path)
    c.ingest_evidence('state lock check','manual','test',0.8,'supports',0.8)
    lock=c.path.with_suffix(c.path.suffix+'.lock')
    lock.write_text('active')
    with pytest.raises(RuntimeError, match='already in progress'):
        c.save()
    assert lock.exists()
    old=time.time()-120
    os.utime(lock, (old, old))
    c.save()
    assert not lock.exists()


def test_scheduler_idle_and_reason_codes_and_bounds(tmp_path):
    c=core(tmp_path)
    assert c.tick()['action'] == 'idle'
    c.ingest_evidence('system uncertain state','seed','test',0.5,'supports',0.1)
    out=c.tick()
    assert out['checked'] <= c.limits['max_tick_checks']
    assert out['reason_codes']


def test_anti_fake_claim_invariants(tmp_path):
    c=core(tmp_path)
    assert c.self_model() == {}
    with pytest.raises(ValueError):
        c.ingest_evidence('', 'src')
    with pytest.raises(ValueError):
        c.run_inquiry_results('claim', [])
    assert all(r.evidence for r in c.world.values())


def test_action_memory_records_outcomes_and_updates_skill_and_tool(tmp_path):
    c=core(tmp_path)
    a=c.record_action('find docs','search','browser_search','success','success',True,duration=0.2,confidence_before=0.5)
    assert a.id in c.actions
    assert c.skills['browser_search_search'].success_count == 1
    assert c.tools['browser_search'].trust_score > 0.5
    assert c.operational_memory[-1]['success'] is True
    with pytest.raises(ValueError):
        c.record_action('fake success','search','browser_search','success')


def test_planner_creates_inspectable_plan_and_decomposes_goal(tmp_path):
    c=core(tmp_path)
    g=c.create_goal('search docs then verify device state',0.8,'test',['docs found','device verified'])
    plan=c.create_plan(g.objective,g.id)
    assert plan.plan_id in c.plans
    assert len(c.subgoals) >= 2
    assert len(plan.steps) >= 2
    assert plan.fallback_plan[0]['action'] == 'ask_human'
    assert plan.status == 'ready'


def test_plan_execution_updates_after_each_step_and_completes_goal(tmp_path):
    c=core(tmp_path)
    g=c.create_goal('search docs then verify device state',0.8,'test')
    plan=c.create_plan(g.objective,g.id)
    out=c.execute_plan(plan.plan_id, {
        'step_1': {'success': True, 'actual_outcome': 'success', 'duration': 0.1},
        'step_2': {'success': True, 'actual_outcome': 'success', 'duration': 0.1},
    })
    assert out['status'] == 'completed'
    assert len(out['executed_actions']) == len(plan.steps)
    assert c.goals[g.id].status == 'completed'
    assert all(a.success for a in c.actions.values())


def test_recovery_changes_plan_after_failure_and_retry_is_not_success(tmp_path):
    c=core(tmp_path)
    c.tools['browser_search']=c._tool('browser_search')
    c.tools['browser_search'].trust_score=0.8
    plan=c.create_plan('search docs')
    out=c.execute_plan(plan.plan_id, {'step_1': {'success': False, 'actual_outcome': 'timeout', 'error_type': 'timeout'}})
    action=next(iter(c.actions.values()))
    assert action.success is False
    assert out['status'] == 'recovering'
    assert out['recovery_decision'] == 'retry'
    assert c.failures
    assert c.skills['browser_search_search'].failure_count == 1


def test_low_reliability_tool_causes_human_help_recovery(tmp_path):
    c=core(tmp_path)
    c.tools['browser_search']=c._tool('browser_search')
    c.tools['browser_search'].trust_score=0.1
    plan=c.create_plan('search docs')
    out=c.execute_plan(plan.plan_id, {'step_1': {'success': False, 'actual_outcome': 'bad', 'error_type': 'permission_denied'}})
    assert out['status'] == 'blocked'
    assert out['recovery_decision'] == 'ask_human'
    assert c.operational_self_model()['should_ask_for_help'] is True


def test_tool_reliability_changes_future_tool_choice(tmp_path):
    c=core(tmp_path)
    for _ in range(3):
        c.record_action('search docs','search','browser_search','success','bad',False,error_type='bad_result',confidence_before=0.8)
    for _ in range(3):
        c.record_action('retrieve memory','retrieve','memory_retrieval','success','success',True,confidence_before=0.5)
    plan=c.create_plan('search documented fact')
    assert plan.steps[0]['tool_used'] == 'memory_retrieval'


def test_decision_trace_binds_to_execution_requirements(tmp_path):
    c=core(tmp_path)
    d=c.decide('unknown critical fact',['search','ask_human'])
    assert d.execution_required is True
    assert d.predicted_outcome == 'usable_evidence'
    assert d.expected_reward > 0
    assert 'ask_human' in d.alternatives


def test_operational_state_persists_after_restart(tmp_path):
    c=core(tmp_path)
    plan=c.create_plan('search docs')
    c.execute_plan(plan.plan_id, {'step_1': {'success': True, 'actual_outcome': 'success'}})
    c.save()
    c2=core(tmp_path)
    assert c2.plans and c2.actions and c2.skills and c2.tools and c2.operational_memory
    assert c2.operational_self_model()['tools']


def test_operational_causality_feature_ablation(tmp_path):
    no_planner=core(tmp_path/'no_planner', planner=False)
    assert no_planner.create_plan('search docs') is None
    no_action=core(tmp_path/'no_action', action_memory=False)
    assert no_action.record_action('x','search','browser_search','success','success',True) is None
    assert not no_action.skills
    no_skill=core(tmp_path/'no_skill', skill_tracking=False)
    no_skill.record_action('x','search','browser_search','success','bad',False)
    assert not no_skill.skills and no_skill.tools
    no_tool=core(tmp_path/'no_tool', tool_reliability=False)
    no_tool.record_action('x','search','browser_search','success','success',True)
    assert not no_tool.tools and no_tool.skills
    no_recovery=core(tmp_path/'no_recovery', recovery=False)
    plan=no_recovery.create_plan('search docs')
    out=no_recovery.execute_plan(plan.plan_id, {'step_1': {'success': False, 'actual_outcome': 'bad'}})
    assert out['recovery_decision'] == 'abort'
    no_op_self=core(tmp_path/'no_op_self', operational_self_model=False)
    no_op_self.record_action('x','search','browser_search','success','bad',False)
    assert no_op_self.operational_self_model() == {}


def test_long_run_skill_simulation_improves_tool_choice_and_help(tmp_path):
    c=core(tmp_path)
    for i in range(40):
        c.record_action(f'browser task {i}','search','browser_search','success','bad',False,error_type='bad_result',confidence_before=0.8)
    for i in range(40):
        c.record_action(f'memory task {i}','retrieve','memory_retrieval','success','success',True,confidence_before=0.5)
    sm=c.operational_self_model()
    assert c.skills['memory_retrieval_retrieve'].reliability > c.skills['browser_search_search'].reliability
    assert c.tools['memory_retrieval'].trust_score > c.tools['browser_search'].trust_score
    assert 'browser_search_search' in sm['weak_skills']
    assert c.create_plan('search documented fact').steps[0]['tool_used'] == 'memory_retrieval'


def complete_plan(c, objective, outcome=True):
    plan=c.create_plan(objective)
    outcomes={st['step_id']:{'success':outcome,'actual_outcome':'success' if outcome else 'failure','error_type':None if outcome else 'bad_result'} for st in plan.steps}
    c.execute_plan(plan.plan_id, outcomes)
    return plan


def test_procedure_not_induced_from_single_success_but_induced_from_repetition(tmp_path):
    c=core(tmp_path)
    complete_plan(c, 'search docs for alpha')
    assert c.induce_procedures(min_successes=2) == []
    complete_plan(c, 'search docs for beta')
    procs=c.induce_procedures(min_successes=2)
    assert procs
    proc=procs[0]
    assert proc.success_count >= 2
    assert proc.confidence > 0
    assert proc.derived_from


def test_task_template_mined_from_validated_procedure(tmp_path):
    c=core(tmp_path)
    complete_plan(c, 'search docs for alpha')
    complete_plan(c, 'search docs for beta')
    c.induce_procedures(min_successes=2)
    templates=c.mine_task_templates(min_count=2)
    assert templates
    assert templates[0].goal_type == 'search_and_evaluate'
    assert templates[0].confidence > 0


def test_transfer_requires_test_and_cross_domain_validation(tmp_path):
    c=core(tmp_path)
    for i in range(3):
        c.record_action(f'browser search {i}','search','browser_search','success','success',True)
    tr=c.create_transfer_test('browser_search_search','memory_retrieval_retrieve','information retrieval overlap')
    assert tr.test_result is None
    assert tr.transfer_strength > 0
    failed=c.validate_transfer(tr.id, False, 'outcome_1')
    assert failed.test_result == 'failed'
    assert failed.confidence_after < failed.confidence_before
    passed=c.validate_transfer(tr.id, True, 'outcome_2')
    assert passed.test_result == 'success'
    assert passed.outcome_ids


def test_benchmark_requires_outcomes_and_tracks_improvement(tmp_path):
    c=core(tmp_path)
    with pytest.raises(ValueError):
        c.evaluate_benchmark('browser','search')
    ids=[]
    for i in range(4):
        ids.append(c.record_action(f'browser search {i}','search','browser_search','success','bad',False,confidence_before=0.8).id)
    b1=c.evaluate_benchmark('browser','search',ids)
    for i in range(6):
        ids.append(c.record_action(f'browser search ok {i}','search','browser_search','success','success',True,confidence_before=0.5).id)
    b2=c.evaluate_benchmark('browser','search',ids)
    assert b2.sample_size == 10
    assert b2.success_rate > b1.success_rate
    assert b2.trend == 'improving'


def test_drift_detection_degrades_skill_and_procedure(tmp_path):
    c=core(tmp_path)
    for i in range(10):
        c.record_action(f'browser task {i}','search','browser_search','success','success',True,duration=0.1)
    complete_plan(c, 'search docs alpha')
    complete_plan(c, 'search docs beta')
    proc=c.induce_procedures(min_successes=2)[0]
    for i in range(5):
        c.record_action(f'browser task degraded {i}','search','browser_search','success','bad',False,error_type='bad_result',duration=1.0,confidence_before=0.9)
    drift=c.detect_drift('browser',recent=5,baseline=10)
    assert drift['drift'] is True
    assert c.skills['browser_search_search'].ask_for_help_flag is True
    assert c.procedures[proc.id].lifecycle == 'degraded'


def test_competence_calibration_changes_planning_to_safer_or_help(tmp_path):
    c=core(tmp_path)
    c.drift_signals['browser']={'drift':True}
    c.tools['browser_search']=c._tool('browser_search')
    c.tools['browser_search'].trust_score=0.1
    plan=c.create_plan('search documented fact')
    assert plan.steps[0]['tool_used'] in {'ask_human','memory_retrieval'}
    assert any(a.startswith('competence:') for a in plan.assumptions)


def test_debug_failure_uses_failure_history_and_updates_procedure_modes(tmp_path):
    c=core(tmp_path)
    complete_plan(c, 'search docs alpha')
    complete_plan(c, 'search docs beta')
    proc=c.induce_procedures(min_successes=2)[0]
    plan=c.create_plan('search docs gamma')
    c.execute_plan(plan.plan_id, {'step_1': {'success': False, 'actual_outcome': 'timeout', 'error_type': 'timeout'}})
    fid=next(iter(c.failures))
    dbg=c.debug_failure(fid, proc.id)
    assert dbg.failure_id == fid
    assert dbg.selected_fix in {'retry_with_smaller_probe','ask_human','change_tool'}
    assert c.procedures[proc.id].known_failure_modes['timeout'] >= 1


def test_procedure_confidence_does_not_rise_without_evidence(tmp_path):
    c=core(tmp_path)
    proc=c.induce_procedures(min_successes=2)
    assert proc == []
    manual_conf=sum(p.confidence for p in c.procedures.values())
    assert manual_conf == 0


def test_new_layer_causal_ablation(tmp_path):
    no_proc=core(tmp_path/'no_proc', procedure_induction=False)
    complete_plan(no_proc, 'search docs a'); complete_plan(no_proc, 'search docs b')
    assert no_proc.induce_procedures() == []
    no_transfer=core(tmp_path/'no_transfer', transfer_layer=False)
    assert no_transfer.create_transfer_test('a','b') is None
    no_bench=core(tmp_path/'no_bench', benchmark_tracking=False)
    no_bench.record_action('browser task','search','browser_search','success','success',True)
    assert no_bench.evaluate_benchmark('browser') is None
    no_drift=core(tmp_path/'no_drift', drift_detection=False)
    assert no_drift.detect_drift('browser') is None
    no_debug=core(tmp_path/'no_debug', debug_tracing=False)
    plan=no_debug.create_plan('search docs')
    no_debug.execute_plan(plan.plan_id, {'step_1': {'success': False, 'actual_outcome': 'bad'}})
    fid=next(iter(no_debug.failures))
    assert no_debug.debug_failure(fid) is None
    no_calib=core(tmp_path/'no_calib', competence_calibration=False)
    no_calib.drift_signals['browser']={'drift':True}
    assert no_calib.create_plan('search docs').steps[0]['step_id'] == 'step_1'


def test_long_run_transfer_simulation_and_persistence(tmp_path):
    c=core(tmp_path)
    for i in range(30):
        complete_plan(c, f'search docs repeated {i}')
    procs=c.induce_procedures(min_successes=2)
    c.mine_task_templates(min_count=2)
    for i in range(20):
        c.record_action(f'browser search {i}','search','browser_search','success','success',True,duration=0.1)
        c.record_action(f'memory retrieval {i}','retrieve','memory_retrieval','success','success',True,duration=0.05)
    tr=c.create_transfer_test('browser_search_search','memory_retrieval_retrieve','retrieval pattern')
    c.validate_transfer(tr.id, True, 'outcome_transfer')
    b1=c.evaluate_benchmark('browser','search')
    for i in range(15):
        c.record_action(f'browser degraded {i}','search','browser_search','success','bad',False,error_type='bad_result',duration=1.0,confidence_before=0.9)
    drift=c.detect_drift('browser',recent=5,baseline=10)
    summary=c.competence_summary()
    c.save(); c2=core(tmp_path)
    assert procs and c2.procedures and c2.transfers and c2.benchmarks and c2.task_templates
    assert b1.success_rate > 0
    assert drift['drift'] is True
    assert summary['transferable_patterns']
    assert c2.competence_summary()['domain_drift_summary']
