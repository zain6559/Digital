import json, hashlib, time, os, re, shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from datetime import datetime, UTC
from urllib.parse import urlparse
from .schemas import MemoryIn
from .memory import SpatialMemoryAgent

STATE_VERSION=4
LOCK_STALE_SECONDS=30

def now(): return datetime.now(UTC).isoformat()
def cid(prefix: str, text: str) -> str: return prefix + hashlib.sha1(text.encode()).hexdigest()[:12]
def clamp(v: float) -> float: return max(0.0, min(1.0, v))
def tokens(s: str): return re.findall(r"[a-z0-9]+", s.lower())

STOP={'the','a','an','is','are','was','were','be','being','been','that','this','it','to','of','and','or'}
ALIASES={'owns':'own','owned':'own','has':'have','contains':'have','includes':'have','causes':'cause','caused':'cause','leads':'cause','triggers':'cause','results':'cause','broken':'not_ready','failed':'not_ready','failure':'not_ready','ready':'ready','ok':'ready','documented':'documented','docs':'documented'}
NEG={'not','no','never','without','cannot','cant','failed','broken'}
REL_WORDS={'own','have','cause','use','support','contradict','document','state','located','connect','ready','not_ready','relate'}

def normalize_text(text: str) -> dict[str, Any]:
    raw=tokens(text)
    polarity=-1 if any(t in NEG for t in raw) else 1
    norm=[ALIASES.get(t,t) for t in raw if t not in STOP and t not in NEG]
    ordered_terms=list(dict.fromkeys(norm))
    # collapse simple state phrases
    if 'not_ready' in norm and 'ready' in norm: norm=[t for t in norm if t!='ready']; ordered_terms=[t for t in ordered_terms if t!='ready']
    key_terms=sorted(dict.fromkeys(norm))
    rel=next((t for t in norm if t in REL_WORDS), 'state' if len(norm) <= 2 else 'relate')
    return {'canonical':' '.join(key_terms), 'terms':key_terms, 'ordered_terms':ordered_terms, 'relation_hint':rel, 'polarity':polarity}

@dataclass
class EvidenceRecord:
    id: str; claim: str; source: str; source_type: str; source_reliability: float; relation: str; strength: float; collected_at: str; metadata: dict[str, Any]=field(default_factory=dict)

@dataclass
class BeliefRecord:
    id: str; proposition: str; confidence: float; evidence: list[str]=field(default_factory=list); counter_evidence: list[str]=field(default_factory=list); source: str='system'; created_at: str=field(default_factory=now); updated_at: str=field(default_factory=now); last_tested_at: str|None=None; prediction_history: list[str]=field(default_factory=list); contradiction_count: int=0; revision_count: int=0; status: str='active'; audit_trail: list[dict[str, Any]]=field(default_factory=list); canonical: str=''; aliases: list[str]=field(default_factory=list); polarity: int=1; domain: str='general'

@dataclass
class WorldRelation:
    id: str; subject: str; relation: str; object: str; confidence: float; evidence: list[str]=field(default_factory=list); updated_at: str=field(default_factory=now); relation_type: str='ambiguous'; state: str='weak'; temporal_hint: str|None=None; causes: list[str]=field(default_factory=list)

@dataclass
class PredictionRecord:
    id: str; proposition: str; expected: str; probability: float; belief_ids: list[str]; created_at: str=field(default_factory=now); due_at: str|None=None; outcome: str|None=None; error: float|None=None; resolved_at: str|None=None; domain: str='general'; action_type: str='general'

@dataclass
class GoalRecord:
    id: str; objective: str; priority: float; origin: str; progress: float=0.0; confidence: float=0.5; dependencies: list[str]=field(default_factory=list); success_criteria: list[str]=field(default_factory=list); deadline: str|None=None; status: str='active'

@dataclass
class DecisionTrace:
    selected_action: str; alternatives: list[str]; risk: str; confidence: float; beliefs_used: list[str]; predictions_used: list[str]; reason_codes: list[str]; predicted_outcome: str=''; expected_cost: float=0.0; expected_reward: float=0.0; execution_required: bool=False; plan_id: str|None=None; rejected_alternatives: list[str]=field(default_factory=list)

@dataclass
class ActionRecord:
    id: str; goal_id: str|None; objective: str; action_type: str; tool_used: str; input_summary: str; expected_outcome: str; actual_outcome: str|None=None; success: bool|None=None; confidence_before: float=0.0; confidence_after: float=0.0; duration: float=0.0; retries: int=0; error_type: str|None=None; evidence_ids: list[str]=field(default_factory=list); belief_ids: list[str]=field(default_factory=list); created_at: str=field(default_factory=now)

@dataclass
class SkillRecord:
    skill_name: str; prediction_count: int=0; action_count: int=0; success_count: int=0; failure_count: int=0; mean_error: float=0.0; mean_latency: float=0.0; reliability: float=0.0; overconfidence_flag: bool=False; ask_for_help_flag: bool=True; last_updated: str=field(default_factory=now); lifecycle: str='emerging'

@dataclass
class ToolProfile:
    tool_name: str; attempts: int=0; successes: int=0; failures: int=0; mean_latency: float=0.0; mean_value_added: float=0.0; failure_modes: dict[str,int]=field(default_factory=dict); trust_score: float=0.5; last_seen: str=field(default_factory=now)

@dataclass
class PlanRecord:
    plan_id: str; objective: str; assumptions: list[str]; steps: list[dict[str, Any]]; estimated_risk: str; estimated_cost: float; expected_value: float; fallback_plan: list[dict[str, Any]]; selected_actions: list[str]; belief_ids_used: list[str]; created_at: str=field(default_factory=now); status: str='draft'; goal_id: str|None=None; current_step: int=0; outcome: str|None=None

@dataclass
class FailureRecord:
    id: str; action_id: str; plan_id: str|None; failure_type: str; cause_hypothesis: str; recovery_decision: str; effect_on_skill: float; created_at: str=field(default_factory=now)

@dataclass
class SubGoalRecord:
    id: str; parent_goal_id: str; objective: str; priority: float; progress: float=0.0; dependencies: list[str]=field(default_factory=list); success_criteria: list[str]=field(default_factory=list); blocking_reason: str|None=None; status: str='pending'

@dataclass
class ProcedureRecord:
    id: str; name: str; objective_type: str; preconditions: list[str]; steps: list[dict[str, Any]]; fallback_steps: list[dict[str, Any]]; tool_sequence: list[str]; expected_outcomes: list[str]; known_failure_modes: dict[str,int]; domain: str; confidence: float=0.0; success_count: int=0; failure_count: int=0; transfer_count: int=0; last_updated: str=field(default_factory=now); evidence_ids: list[str]=field(default_factory=list); belief_ids: list[str]=field(default_factory=list); derived_from: list[str]=field(default_factory=list); lifecycle: str='emerging'

@dataclass
class TransferRecord:
    id: str; source_skill: str; target_skill: str; transfer_reason: str; transfer_strength: float; test_result: str|None=None; confidence_before: float=0.0; confidence_after: float=0.0; evidence_ids: list[str]=field(default_factory=list); outcome_ids: list[str]=field(default_factory=list); created_at: str=field(default_factory=now)

@dataclass
class BenchmarkRecord:
    id: str; domain: str; task_type: str; sample_size: int; success_rate: float; mean_error: float; mean_latency: float; retry_rate: float; recovery_rate: float; help_request_rate: float; last_evaluated: str; trend: str='insufficient_history'

@dataclass
class DebugRecord:
    id: str; failure_id: str; hypothesized_cause: str; evidence_for: list[str]; evidence_against: list[str]; selected_fix: str; result: str; confidence: float; reused_procedure_id: str|None=None; created_at: str=field(default_factory=now)

@dataclass
class TaskTemplateRecord:
    id: str; name: str; goal_type: str; skeleton_steps: list[dict[str, Any]]; domains: list[str]; success_count: int=0; failure_count: int=0; confidence: float=0.0; last_updated: str=field(default_factory=now); lifecycle: str='emerging'

class CognitiveCore:
    def __init__(self, path: str|Path='noor_state.json', memory: SpatialMemoryAgent|None=None, limits: dict[str,int]|None=None, features: dict[str,bool]|None=None):
        self.path=Path(path); self.memory=memory or SpatialMemoryAgent(); self.limits={'max_memories':2000,'max_events':2000,'max_inquiries':100,'max_browser_requests':20,'tick_budget_ms':20,'max_tick_checks':50}|(limits or {})
        defaults={'memory':True,'beliefs':True,'inquiry':True,'world_model':True,'prediction':True,'self_model':True,'autonomy':True,'action_memory':True,'skill_tracking':True,'planner':True,'recovery':True,'tool_reliability':True,'operational_self_model':True,'operational_memory':True,'procedure_induction':True,'transfer_layer':True,'benchmark_tracking':True,'drift_detection':True,'debug_tracing':True,'competence_calibration':True}; defaults.update(features or {}); self.features=defaults
        self.evidence={}; self.beliefs={}; self.world={}; self.predictions={}; self.goals={}; self.plans={}; self.actions={}; self.skills={}; self.tools={}; self.failures={}; self.subgoals={}; self.procedures={}; self.transfers={}; self.benchmarks={}; self.debug_records={}; self.task_templates={}; self.drift_signals={}; self.operational_memory=[]; self.unknowns={}; self.events=[]; self.source_stats={}; self.self_history=[]; self.tick_count=0; self.browser_requests=0; self.version=STATE_VERSION
        self.load()
    def _append_event(self, typ, payload): self.events.append({'type':typ,'payload':payload,'ts':now()}); self.events=self.events[-self.limits['max_events']:]
    def _domain(self, text):
        ts=set(tokens(text));
        for d,keys in {'mobile':{'device','tap','wake','phone','android'},'browser':{'url','search','page','docs'},'world':{'cause','state','relation'},'vision':{'face','image','camera'}}.items():
            if ts & keys: return d
        return 'general'
    def _migrate(self,data): data.setdefault('version',1); return data
    def _state_checksum(self, data: dict[str, Any]) -> str:
        payload={k:v for k,v in data.items() if k!='__checksum'}
        return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    def _read_state_file(self, path: Path) -> dict[str, Any]:
        data=json.loads(path.read_text())
        checksum=data.get('__checksum')
        if checksum and checksum != self._state_checksum(data):
            raise ValueError(f'cognitive state checksum mismatch: {path}')
        return data
    def load(self):
        if not self.path.exists(): return
        try: data=self._migrate(self._read_state_file(self.path))
        except Exception as exc:
            backup=self.path.with_suffix(self.path.suffix+'.bak')
            if backup.exists():
                try:
                    data=self._migrate(self._read_state_file(backup)); self._append_event('state.load_recovered_from_backup',{'error':type(exc).__name__,'backup':str(backup)})
                except Exception as backup_exc:
                    self._append_event('state.load_failed',{'error':type(exc).__name__,'backup_error':type(backup_exc).__name__}); return
            else:
                self._append_event('state.load_failed',{'error':type(exc).__name__}); return
        self.version=data.get('version',1)
        def filt(cls,v):
            names=cls.__dataclass_fields__.keys(); return cls(**{k:v for k,v in v.items() if k in names})
        self.evidence={k:filt(EvidenceRecord,v) for k,v in data.get('evidence',{}).items()}; self.beliefs={k:filt(BeliefRecord,v) for k,v in data.get('beliefs',{}).items()}; self.world={k:filt(WorldRelation,v) for k,v in data.get('world',{}).items()}; self.predictions={k:filt(PredictionRecord,v) for k,v in data.get('predictions',{}).items()}; self.goals={k:filt(GoalRecord,v) for k,v in data.get('goals',{}).items()}; self.plans={k:filt(PlanRecord,v) for k,v in data.get('plans',{}).items()}; self.actions={k:filt(ActionRecord,v) for k,v in data.get('actions',{}).items()}; self.skills={k:filt(SkillRecord,v) for k,v in data.get('skills',{}).items()}; self.tools={k:filt(ToolProfile,v) for k,v in data.get('tools',{}).items()}; self.failures={k:filt(FailureRecord,v) for k,v in data.get('failures',{}).items()}; self.subgoals={k:filt(SubGoalRecord,v) for k,v in data.get('subgoals',{}).items()}; self.procedures={k:filt(ProcedureRecord,v) for k,v in data.get('procedures',{}).items()}; self.transfers={k:filt(TransferRecord,v) for k,v in data.get('transfers',{}).items()}; self.benchmarks={k:filt(BenchmarkRecord,v) for k,v in data.get('benchmarks',{}).items()}; self.debug_records={k:filt(DebugRecord,v) for k,v in data.get('debug_records',{}).items()}; self.task_templates={k:filt(TaskTemplateRecord,v) for k,v in data.get('task_templates',{}).items()}; self.drift_signals=data.get('drift_signals',{}); self.operational_memory=data.get('operational_memory',[]); self.unknowns=data.get('unknowns',{}); self.events=(data.get('events',[])+self.events)[-self.limits['max_events']:]; self.source_stats=data.get('source_stats',{}); self.self_history=data.get('self_history',[]); self.tick_count=data.get('tick_count',0); self.browser_requests=data.get('browser_requests',0)
    def save(self):
        data={name:{k:asdict(v) for k,v in getattr(self,name).items()} for name in ['evidence','beliefs','world','predictions','goals','plans','actions','skills','tools','failures','subgoals','procedures','transfers','benchmarks','debug_records','task_templates']}
        data|={'version':STATE_VERSION,'unknowns':self.unknowns,'events':self.events[-self.limits['max_events']:],'source_stats':self.source_stats,'self_history':self.self_history[-500:],'tick_count':self.tick_count,'browser_requests':self.browser_requests,'operational_memory':self.operational_memory[-500:],'drift_signals':self.drift_signals}
        data['__checksum']=self._state_checksum(data)
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix(self.path.suffix+'.tmp'); lock=self.path.with_suffix(self.path.suffix+'.lock'); backup=self.path.with_suffix(self.path.suffix+'.bak')
        fd=None
        for _ in range(2):
            try:
                fd=os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    age=time.time()-lock.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age <= LOCK_STALE_SECONDS:
                    self._append_event('state.save_blocked', {'reason':'active_lock','lock':str(lock)})
                    raise RuntimeError(f'cognitive state save is already in progress: {lock}')
                lock.unlink(missing_ok=True)
        if fd is None: raise RuntimeError(f'could not acquire cognitive state lock: {lock}')
        try:
            with open(tmp,'w',encoding='utf-8') as handle:
                json.dump(data,handle,ensure_ascii=False,indent=2); handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
            if self.path.exists() and self.path.is_file(): shutil.copy2(self.path,backup)
            os.replace(tmp,self.path)
        finally:
            if fd is not None: os.close(fd)
            Path(lock).unlink(missing_ok=True); Path(tmp).unlink(missing_ok=True)
    def _belief_id(self, proposition): return cid('b_', normalize_text(proposition)['canonical'])
    def _find_equiv(self,n):
        s=set(n['terms'])
        for b in self.beliefs.values():
            bs=set(b.canonical.split()); core_s={x for x in s if x not in {'have','state','relate'}}; core_b={x for x in bs if x not in {'have','state','relate'}}
            sim=len(core_s&core_b)/max(1,len(core_s|core_b))
            if sim>=0.6 or (core_s and core_s <= core_b) or (core_b and core_b <= core_s): return b
        return None
    def meta_state(self, proposition: str) -> str:
        b=self.beliefs.get(self._belief_id(proposition)) or self._find_equiv(normalize_text(proposition))
        if not b: return 'unknown'
        if b.status in {'rejected','suspended'}: return b.status
        if b.contradiction_count and b.evidence and b.counter_evidence: return 'contradictory'
        if b.confidence>=0.75: return 'known'
        if b.confidence>=0.55: return 'likely'
        return 'uncertain'
    def source_credibility(self, source, source_type='user'):
        host=urlparse(source).netloc.lower() if '://' in source else source.lower(); base=0.9 if source_type in {'system','telemetry'} else 0.75 if source_type=='user' else 0.55
        if any(b in host for b in ['spam','tabloid','bad','clickbait']): base=0.2
        if any(g in host for g in ['.gov','.edu','docs','official','example.test']): base=max(base,0.75)
        st=self.source_stats.get('source:'+host)
        if st and st.get('observations'): base=(base+st.get('reliability',base))/2
        return clamp(base)
    def ingest_evidence(self, claim: str, source: str, source_type='user', source_reliability=None, relation='supports', strength=0.6, metadata=None):
        if not source or not claim: raise ValueError('evidence requires source and claim')
        if relation not in {'supports','contradicts'}: raise ValueError('evidence relation must support or contradict')
        sr=self.source_credibility(source,source_type) if source_reliability is None else min(clamp(source_reliability), self.source_credibility(source,source_type)+0.15)
        e=EvidenceRecord(cid('e_', claim+source+relation+now()), claim, source, source_type, sr, relation, clamp(strength), now(), metadata or {})
        self.evidence[e.id]=e; self._append_event('evidence.created',asdict(e))
        if self.features['beliefs']: self.apply_evidence(e)
        if self.features['memory']: self.memory.add(MemoryIn(title=f'Evidence: {claim[:60]}',content=claim,tags=['evidence',relation],source=source,importance=max(1,int(e.strength*10))))
        self.save(); return e
    def apply_evidence(self, e):
        n=normalize_text(e.claim); b=self.beliefs.get(cid('b_',n['canonical'])) or self._find_equiv(n)
        if not b:
            b=BeliefRecord(cid('b_',n['canonical']),e.claim,0.5,source=e.source,canonical=n['canonical'],aliases=[e.claim],polarity=n['polarity'],domain=self._domain(e.claim)); self.beliefs[b.id]=b
        elif e.claim not in b.aliases: b.aliases.append(e.claim)
        effective_relation=e.relation
        if n['polarity'] != b.polarity and e.relation=='supports': effective_relation='contradicts'
        before=b.confidence; weight=e.strength*e.source_reliability
        if effective_relation=='supports': b.evidence.append(e.id); b.confidence=clamp(b.confidence+(1-b.confidence)*weight*0.55)
        else: b.counter_evidence.append(e.id); b.confidence=clamp(b.confidence-b.confidence*weight*0.85); b.contradiction_count+=1
        b.revision_count+=1; b.updated_at=now(); b.last_tested_at=now();
        if b.confidence<0.2: b.status='rejected'
        elif b.counter_evidence and b.evidence and abs(len(b.evidence)-len(b.counter_evidence))<=2: b.status='suspended' if b.confidence<0.55 else 'active'
        b.audit_trail.append({'before':before,'after':b.confidence,'evidence':e.id,'reason':effective_relation,'ts':now(),'weight':weight})
        self.update_world_from_belief(b,e); return b
    def merge_beliefs(self,a,b):
        ba=self.beliefs[self._belief_id(a)]; bb=self.beliefs.pop(self._belief_id(b)); before=ba.confidence; ba.evidence+=bb.evidence; ba.counter_evidence+=bb.counter_evidence; ba.aliases+=bb.aliases; ba.confidence=clamp((ba.confidence+bb.confidence)/2); ba.revision_count+=1; ba.updated_at=now(); ba.audit_trail.append({'before':before,'after':ba.confidence,'reason':'merge','merged':bb.id,'ts':now()}); self.save(); return ba
    def update_world_from_belief(self,b,e):
        if not self.features['world_model']: return None
        n=normalize_text(b.proposition); terms=[t for t in n.get('ordered_terms', n['terms']) if t not in REL_WORDS]
        rel=n['relation_hint']; state='weak'; rtype='ambiguous'; temporal=None; causes=[]
        low=b.proposition.lower()
        if any(x in low for x in [' after ',' before ',' when ',' then ']): temporal='ordered'; state='supported'
        if rel in {'own','have','cause','use','connect','ready','not_ready'} and len(terms)>=2:
            raw_words=re.findall(r'\S+', b.proposition)
            subj=raw_words[0] if raw_words else terms[0]; obj=' '.join(raw_words[2:]) if len(raw_words)>=3 else ' '.join(terms[1:])
            state='supported' if b.confidence>=0.55 else 'weak'; rtype='causal' if rel=='cause' else 'attribute'
        elif len(terms)>=3: subj,obj=terms[0],' '.join(terms[1:]); rel='relate'
        else: subj,obj='claim',b.proposition; rel='states'; state='ambiguous'
        if rel=='cause': causes=[subj]
        display_rel={'own':'owns','have':'has','cause':'causes'}.get(rel,rel); rid=cid('w_',subj+display_rel+obj); wr=self.world.get(rid) or WorldRelation(rid,subj,display_rel,obj,b.confidence,relation_type=rtype,state=state,temporal_hint=temporal,causes=causes)
        wr.confidence=min(b.confidence,e.strength*e.source_reliability); wr.evidence=list(dict.fromkeys(wr.evidence+[e.id])); wr.updated_at=now(); wr.state=state; self.world[rid]=wr; return wr
    def create_goal(self, objective, priority=0.5, origin='user', success_criteria=None):
        g=GoalRecord(cid('g_',objective+origin),objective,clamp(priority),origin,success_criteria=success_criteria or []); self.goals[g.id]=g; self.save(); return g
    def create_prediction(self, proposition, expected, probability, belief_ids=None):
        if not self.features['prediction']: return None
        ts=tokens(proposition); p=PredictionRecord(cid('p_',proposition+expected+now()),proposition,expected,clamp(probability),belief_ids or [],domain=self._domain(proposition),action_type=ts[1] if len(ts)>1 else 'general')
        self.predictions[p.id]=p
        for bid in p.belief_ids:
            if bid in self.beliefs: self.beliefs[bid].prediction_history.append(p.id)
        self.save(); return p
    def record_outcome(self, prediction_id, outcome):
        p=self.predictions[prediction_id]; p.outcome=outcome; happened=outcome==p.expected; p.error=abs((1.0 if happened else 0.0)-p.probability); p.resolved_at=now()
        for bid in p.belief_ids:
            if bid in self.beliefs: self.ingest_evidence(self.beliefs[bid].proposition,'outcome','system',0.9,'supports' if happened else 'contradicts',min(1,p.error+0.2),{'prediction':prediction_id})
        if self.features['self_model']: self.learn_from_prediction(p)
        self.save(); return p
    def learn_from_prediction(self,p):
        for key in [p.domain, 'action:'+p.action_type]:
            stats=self.source_stats.setdefault(key,{'predictions':0,'errors':0,'success':0}); stats['predictions']+=1; stats['errors']+=p.error or 0; stats['success']+=1 if (p.error or 1)<0.5 else 0
            self.self_history.append({'domain':key,'accuracy':stats['success']/stats['predictions'],'mean_error':stats['errors']/stats['predictions'],'ts':now()})
    def self_model(self):
        if not self.features['self_model'] or not self.self_history: return {}
        out={}
        for k,v in self.source_stats.items():
            if 'predictions' in v and v['predictions']:
                acc=v['success']/v['predictions']; err=v['errors']/v['predictions']; out[k]={'prediction_count':v['predictions'],'accuracy':acc,'mean_error':err,'strong':acc>=0.7,'weak':err>=0.5,'overconfident':err>=0.5,'should_ask_for_help':err>=0.5,'bias':'insufficient_history' if v['predictions']<3 else 'none_detected'}
        return out
    def evaluate_inquiry(self, proposition, importance=0.5, search_cost=0.25):
        state=self.meta_state(proposition); uncertainty={'unknown':1,'uncertain':0.7,'contradictory':0.95,'likely':0.35,'known':0.1,'suspended':0.85,'rejected':0.6}.get(state,0.5)
        b=self.beliefs.get(self._belief_id(proposition)) or self._find_equiv(normalize_text(proposition)); contradiction=(b.contradiction_count if b else 0)*0.15; cred=0.55
        expected_gain=clamp(uncertainty*importance + contradiction); value=expected_gain*cred-search_cost
        if not self.features['inquiry']: action='reason_internally'
        elif self.browser_requests>=self.limits['max_browser_requests']: action='defer'
        elif state in {'contradictory','suspended'} and importance>=0.3: action='search'
        elif value>=0.2 or (state=='unknown' and importance>=0.75): action='search'
        elif uncertainty>=0.7 and importance>=0.5: action='ask_human'
        elif expected_gain<0.25: action='defer' if importance<0.3 else 'act_despite_uncertainty'
        else: action='defer'
        return {'unknown':state=='unknown','meta_state':state,'uncertainty':uncertainty,'information_value':value,'expected_gain':expected_gain,'cost':search_cost,'action':action,'query':proposition if action=='search' else None}
    def decide(self, objective, available_actions=None):
        available_actions=available_actions or ['defer','ask_human','search','record_memory','idle']
        inq=self.evaluate_inquiry(objective,0.8); beliefs=[b.id for b in self.beliefs.values() if set(tokens(objective)) & set(b.canonical.split())]
        selected=inq['action'] if inq['action'] in available_actions else 'defer'
        if not self.features['beliefs'] and 'ask_human' in available_actions: selected='ask_human'
        return DecisionTrace(selected,available_actions,'low' if selected!='search' else 'medium',1-inq['uncertainty'],beliefs,[],[f"meta:{inq['meta_state']}",f"iv:{inq['information_value']:.2f}",f"gain:{inq['expected_gain']:.2f}"], predicted_outcome='usable_evidence' if selected=='search' else 'needs_resolution', expected_cost=inq['cost'], expected_reward=inq['expected_gain'], execution_required=selected in {'search','record_memory'})
    def tick(self):
        if not self.features['autonomy']: return {'action':'disabled'}
        start=time.perf_counter(); self.tick_count+=1; action='idle'; checked=0; reason=['no_priority_instability']
        candidates=sorted(self.beliefs.values(), key=lambda b:(b.contradiction_count, 1-b.confidence, len(b.evidence)+len(b.counter_evidence)), reverse=True)
        for b in candidates[:self.limits['max_tick_checks']]:
            checked+=1; st=self.meta_state(b.proposition)
            if st in {'uncertain','contradictory','suspended'}:
                d=self.decide(b.proposition,['defer','ask_human','search','idle']); action=d.selected_action; reason=d.reason_codes; break
            if (time.perf_counter()-start)*1000>self.limits['tick_budget_ms']: reason=['budget_exhausted']; break
        self._append_event('life.tick',{'tick':self.tick_count,'action':action,'checked':checked,'reason_codes':reason});
        if self.tick_count%100==0: self.save()
        return {'tick':self.tick_count,'action':action,'checked':checked,'state':action,'reason_codes':reason,'events':len(self.events)}
    def _score_result(self,r, proposition=''):
        title=(r.get('title') or '').strip(); url=(r.get('url') or '').strip(); content=(r.get('content') or r.get('snippet') or '').strip();
        if not title or not url: return 0, 'missing_title_or_url'
        host=urlparse(url).netloc.lower(); cred=self.source_credibility(url,'browser'); text_terms=set(tokens(title+' '+content)); query_terms=set(tokens(proposition))
        coverage=len(text_terms & query_terms)/max(1,len(query_terms))
        hints=len(text_terms & {'docs','documented','official','evidence','study','manual','spec','reference','standard','release','changelog'})*0.06
        thin_penalty=0.12 if len(content)<40 else 0.0
        low_cred_penalty=0.20 if cred<0.4 else 0.0
        duplicate_penalty=0.10 if r.get('duplicate') else 0.0
        return clamp(0.10+cred*0.42+min(len(content),500)/4000+coverage*0.22+hints-thin_penalty-low_cred_penalty-duplicate_penalty), host
    def run_inquiry_results(self, proposition, results):
        self.browser_requests+=1
        if not results: self._append_event('inquiry.search_failed',{'proposition':proposition,'reason':'empty_results'}); self.save(); raise ValueError('search cannot succeed without evidence')
        ev=[]; seen=set()
        for r in results:
            score,reason=self._score_result(r, proposition); host=reason
            if score<0.38 or host in seen: continue
            seen.add(host); rel='supports'; ev.append(self.ingest_evidence(proposition,r.get('url') or 'browser','browser',None,rel,score,{'title':r.get('title'),'score':score}))
            st=self.source_stats.setdefault('source:'+host,{'observations':0,'reliability':self.source_credibility(r.get('url') or host,'browser')}); st['observations']+=1; st['reliability']=clamp((st['reliability']*(st['observations']-1)+score)/st['observations'])
        if not ev: self._append_event('inquiry.search_failed',{'proposition':proposition,'reason':'no_usable_evidence'}); self.save(); raise ValueError('search results contained no usable evidence')
        self._append_event('inquiry.search_evidence_attached',{'proposition':proposition,'count':len(ev)}); self.save(); return ev

    def _skill_name(self, action_type, tool_used): return f"{tool_used}_{action_type}" if tool_used != action_type else action_type
    def _tool(self, tool_name):
        return self.tools.setdefault(tool_name, ToolProfile(tool_name))
    def _skill(self, skill_name):
        return self.skills.setdefault(skill_name, SkillRecord(skill_name))
    def _update_mean(self, old, count, value): return ((old*(count-1))+value)/count if count else value
    def update_operational_stats(self, action: ActionRecord, value_added=0.0):
        if self.features.get('tool_reliability', True):
            t=self._tool(action.tool_used); t.attempts+=1; t.last_seen=now(); t.mean_latency=self._update_mean(t.mean_latency,t.attempts,action.duration); t.mean_value_added=self._update_mean(t.mean_value_added,t.attempts,value_added)
            if action.success: t.successes+=1
            else:
                t.failures+=1; t.failure_modes[action.error_type or 'unknown']=t.failure_modes.get(action.error_type or 'unknown',0)+1
            t.trust_score=clamp((t.successes+0.5)/(t.attempts+1) + t.mean_value_added*0.1)
        if self.features.get('skill_tracking', True):
            s=self._skill(self._skill_name(action.action_type, action.tool_used)); s.action_count+=1; s.last_updated=now(); s.mean_latency=self._update_mean(s.mean_latency,s.action_count,action.duration)
            if action.success: s.success_count+=1
            else: s.failure_count+=1
            err=abs((1.0 if action.success else 0.0)-action.confidence_before); s.mean_error=self._update_mean(s.mean_error,s.action_count,err); s.reliability=clamp(s.success_count/s.action_count if s.action_count else 0); s.overconfidence_flag=s.mean_error>=0.45 and action.confidence_before>=0.6; s.ask_for_help_flag=s.reliability<0.5 or s.overconfidence_flag; s.lifecycle='stable' if s.action_count>=10 and s.reliability>=0.8 else 'validated' if s.action_count>=3 and s.reliability>=0.65 else 'degraded' if s.action_count>=3 and s.reliability<0.35 else 'provisional' if s.action_count>=2 else 'emerging'
    def record_action(self, objective, action_type, tool_used, expected_outcome, actual_outcome=None, success=None, goal_id=None, input_summary='', confidence_before=0.5, duration=0.0, retries=0, error_type=None, evidence_ids=None, belief_ids=None):
        if not self.features.get('action_memory', True): return None
        if success is None and actual_outcome is None: raise ValueError('action outcome is required')
        if success is None: success = actual_outcome == expected_outcome
        confidence_after=clamp(confidence_before + (0.2 if success else -0.25))
        a=ActionRecord(cid('a_', objective+action_type+tool_used+now()), goal_id, objective, action_type, tool_used, input_summary, expected_outcome, actual_outcome, bool(success), confidence_before, confidence_after, duration, retries, error_type, evidence_ids or [], belief_ids or [])
        self.actions[a.id]=a; self.update_operational_stats(a, confidence_after-confidence_before)
        if self.features.get('operational_memory', True):
            self.operational_memory.append({'action_id':a.id,'objective':objective,'tool':tool_used,'action_type':action_type,'success':a.success,'error_type':error_type,'ts':a.created_at}); self.operational_memory=self.operational_memory[-500:]
        self._append_event('action.recorded', asdict(a)); self.save(); return a
    def decompose_goal(self, goal_id):
        g=self.goals[goal_id]; parts=[p.strip() for p in re.split(r'\bthen\b|;|,', g.objective) if p.strip()]
        if len(parts)<=1 and len(tokens(g.objective))>5: parts=[g.objective, 'verify outcome']
        out=[]
        for i,part in enumerate(parts):
            sg=SubGoalRecord(cid('sg_',goal_id+part+str(i)), goal_id, part, clamp(g.priority-(i*0.05)), dependencies=[out[-1].id] if out else [], success_criteria=[part+' done'])
            self.subgoals[sg.id]=sg; out.append(sg)
        self.save(); return out
    def _select_tool_for_step(self, objective):
        low=objective.lower(); candidates=['memory_retrieval']
        if any(x in low for x in ['search','browser','documented','docs','verify']): candidates=['browser_search','memory_retrieval']
        if any(x in low for x in ['tap','adb','device','text','wake']): candidates=['adb_tap','ask_human']
        if not self.features.get('tool_reliability', True): return candidates[0]
        return max(candidates, key=lambda t:self.tools.get(t, ToolProfile(t)).trust_score)
    def create_plan(self, objective, goal_id=None, available_tools=None):
        if not self.features.get('planner', True): return None
        state=self.meta_state(objective); beliefs=[b.id for b in self.beliefs.values() if set(tokens(objective)) & set(b.canonical.split())]
        assumptions=[] if state=='unknown' else [f'meta_state:{state}']
        risk='medium' if state in {'unknown','contradictory','suspended'} else 'low'
        status='rejected' if state=='unknown' and 'dangerous' in objective.lower() else 'ready'
        chunks=[objective]
        if goal_id and goal_id in self.goals:
            chunks=[sg.objective for sg in self.decompose_goal(goal_id)] or chunks
        steps=[]; selected=[]
        for i,ch in enumerate(chunks):
            tool=self._select_tool_for_step(ch); action_type='ask_human' if tool=='ask_human' else 'search' if tool=='browser_search' else 'tap' if tool.startswith('adb') else 'retrieve'
            step={'step_id':f'step_{i+1}','objective':ch,'action_type':action_type,'tool_used':tool,'expected_outcome':'success','status':'pending','retries':0}; steps.append(step); selected.append(tool)
        fallback=[{'action':'ask_human','reason':'low_skill_or_failed_step'}]
        expected_value=max(0.1, 1.0-(0.2*len(steps))-(0.3 if risk=='medium' else 0))
        calib=self.calibrate_action_confidence(objective, selected[0] if selected else 'memory_retrieval') if self.features.get('competence_calibration', True) else {'confidence':0.5,'mode':'normal'}
        if calib['mode'] in {'safer','ask_human'} and steps: steps.insert(0, {'step_id':'step_0','objective':'small competence probe for '+objective,'action_type':'ask_human' if calib['mode']=='ask_human' else 'retrieve','tool_used':'ask_human' if calib['mode']=='ask_human' else 'memory_retrieval','expected_outcome':'success','status':'pending','retries':0})
        plan=PlanRecord(cid('pl_', objective+now()), objective, assumptions+[f"competence:{calib['confidence']:.2f}"], steps, risk, 0.2*len(steps), expected_value*calib['confidence'], fallback, [st['tool_used'] for st in steps], beliefs, goal_id=goal_id, status=status)
        self.plans[plan.plan_id]=plan; self._append_event('plan.created', asdict(plan)); self.save(); return plan
    def recover_from_failure(self, action, plan=None, failure_type=None):
        if not self.features.get('recovery', True): return 'abort'
        tool=self.tools.get(action.tool_used, ToolProfile(action.tool_used)); skill=self.skills.get(self._skill_name(action.action_type,action.tool_used), SkillRecord(self._skill_name(action.action_type,action.tool_used)))
        if action.retries<1 and tool.trust_score>=0.2 and (failure_type or action.error_type) not in {'permission_denied','unsafe'}: decision='retry'
        elif skill.ask_for_help_flag or tool.trust_score<0.45: decision='ask_human'
        else: decision='alternative_action'
        f=FailureRecord(cid('f_', action.id+now()), action.id, plan.plan_id if plan else None, failure_type or action.error_type or 'unknown', f'{action.tool_used} failed with reliability {tool.trust_score:.2f}', decision, -0.1)
        self.failures[f.id]=f; self._append_event('recovery.decided', asdict(f)); self.save(); return decision
    def execute_plan(self, plan_id, outcomes=None):
        plan=self.plans[plan_id]; outcomes=outcomes or {}; plan.status='running'; executed=[]
        for step in plan.steps[plan.current_step:]:
            before=self.tools.get(step['tool_used'], ToolProfile(step['tool_used'])).trust_score
            spec=outcomes.get(step['step_id'], outcomes.get(step['tool_used'], outcomes.get(step['action_type'], {})))
            if isinstance(spec, bool): spec={'success':spec,'actual_outcome':'success' if spec else 'failure'}
            if not spec: spec={'success':False,'actual_outcome':None,'error_type':'missing_outcome'}
            a=self.record_action(step['objective'], step['action_type'], step['tool_used'], step['expected_outcome'], spec.get('actual_outcome'), spec.get('success'), plan.goal_id, step['objective'][:80], before, spec.get('duration',0.0), step.get('retries',0), spec.get('error_type'), belief_ids=plan.belief_ids_used)
            executed.append(a.id if a else None); step['status']='succeeded' if a and a.success else 'failed'
            if not a or not a.success:
                decision=self.recover_from_failure(a, plan, spec.get('error_type')) if a else 'abort'; step['recovery_decision']=decision
                if decision=='retry': step['retries']=step.get('retries',0)+1; plan.status='recovering'
                elif decision=='alternative_action': step['tool_used']='memory_retrieval'; step['action_type']='retrieve'; plan.status='recovering'
                elif decision=='ask_human': plan.status='blocked'; plan.outcome='needs_human_help'
                else: plan.status='failed'; plan.outcome='aborted'
                self.save(); return {'plan_id':plan_id,'status':plan.status,'executed_actions':executed,'recovery_decision':decision}
            plan.current_step+=1
        plan.status='completed'; plan.outcome='success'
        if plan.goal_id and plan.goal_id in self.goals: self.goals[plan.goal_id].progress=1.0; self.goals[plan.goal_id].status='completed'
        self._append_event('plan.completed', {'plan_id':plan_id,'actions':executed}); self.save(); return {'plan_id':plan_id,'status':plan.status,'executed_actions':executed}
    def operational_self_model(self):
        if not self.features.get('operational_self_model', True): return {}
        if not self.actions: return {}
        weak=[s.skill_name for s in self.skills.values() if s.ask_for_help_flag]; strong=[s.skill_name for s in self.skills.values() if s.action_count>=2 and s.reliability>=0.7]
        tools={t.tool_name:{'trust_score':t.trust_score,'attempts':t.attempts,'failure_modes':t.failure_modes} for t in self.tools.values()}
        return {'strong_skills':strong,'weak_skills':weak,'tools':tools,'failure_patterns':{f.failure_type:sum(1 for x in self.failures.values() if x.failure_type==f.failure_type) for f in self.failures.values()},'should_ask_for_help':bool(weak)}

    def _objective_type(self, text):
        low=text.lower()
        if any(x in low for x in ['search','docs','browser','verify']): return 'search_and_evaluate'
        if any(x in low for x in ['tap','adb','device','inspect']): return 'inspect_and_recover'
        if any(x in low for x in ['revise','contradict','belief']): return 'compare_and_revise'
        if 'then' in low or ';' in low: return 'decompose_and_execute'
        return 'general_task'
    def induce_procedures(self, min_successes=2):
        if not self.features.get('procedure_induction', True): return []
        groups={}
        for p in self.plans.values():
            if p.status!='completed': continue
            key=(self._objective_type(p.objective), tuple(st['tool_used'] for st in p.steps), tuple(st['action_type'] for st in p.steps))
            groups.setdefault(key,[]).append(p)
        made=[]
        for (otype,tools,acts),plans in groups.items():
            if len(plans)<min_successes: continue
            pid=cid('proc_', otype+'|'.join(tools)+'|'.join(acts)); failures={}
            for f in self.failures.values(): failures[f.failure_type]=failures.get(f.failure_type,0)+1
            proc=self.procedures.get(pid) or ProcedureRecord(pid, otype.replace('_',' ')+' procedure', otype, [f'repeated_successes>={min_successes}'], [{'action_type':a,'tool_used':t} for a,t in zip(acts,tools)], [{'action':'ask_human'}], list(tools), ['success']*len(tools), failures, self._domain(' '.join(p.objective for p in plans)))
            proc.success_count=len(plans); proc.failure_count=sum(1 for p in self.plans.values() if self._objective_type(p.objective)==otype and p.status=='failed'); proc.confidence=clamp(proc.success_count/(proc.success_count+proc.failure_count+1)); proc.derived_from=list({p.plan_id for p in plans}); proc.belief_ids=list({b for p in plans for b in p.belief_ids_used}); proc.lifecycle='stable' if proc.success_count>=5 and proc.failure_count==0 else 'validated' if proc.success_count>=2 else 'emerging'; proc.last_updated=now(); self.procedures[pid]=proc; made.append(proc)
        self.save(); return made
    def mine_task_templates(self, min_count=2):
        groups={}
        for proc in self.procedures.values(): groups.setdefault(proc.objective_type,[]).append(proc)
        out=[]
        for otype,procs in groups.items():
            if len(procs)<1 or sum(p.success_count for p in procs)<min_count: continue
            tid=cid('tmpl_',otype); tmpl=self.task_templates.get(tid) or TaskTemplateRecord(tid, otype.replace('_','-'), otype, procs[0].steps, sorted({p.domain for p in procs}))
            tmpl.success_count=sum(p.success_count for p in procs); tmpl.failure_count=sum(p.failure_count for p in procs); tmpl.confidence=clamp(tmpl.success_count/(tmpl.success_count+tmpl.failure_count+1)); tmpl.lifecycle='validated' if tmpl.confidence>=0.6 else 'emerging'; tmpl.last_updated=now(); self.task_templates[tid]=tmpl; out.append(tmpl)
        self.save(); return out
    def create_transfer_test(self, source_skill, target_skill, reason='mapped competence'):
        if not self.features.get('transfer_layer', True): return None
        src=self.skills.get(source_skill); before=src.reliability if src else 0.0; strength=0.0 if not src or src.action_count<2 else before*0.4
        tr=TransferRecord(cid('tr_',source_skill+target_skill+now()), source_skill, target_skill, reason, strength, None, before, before, [], [])
        self.transfers[tr.id]=tr; self.save(); return tr
    def validate_transfer(self, transfer_id, success, outcome_id=None):
        tr=self.transfers[transfer_id]; tr.test_result='success' if success else 'failed'; delta=0.2 if success else -0.2; tr.confidence_after=clamp(tr.confidence_before+delta); tr.transfer_strength=clamp(tr.transfer_strength+delta); 
        if outcome_id: tr.outcome_ids.append(outcome_id)
        for proc in self.procedures.values():
            if tr.source_skill in proc.tool_sequence or any(tool in tr.source_skill for tool in proc.tool_sequence) or tr.source_skill in proc.name:
                proc.transfer_count+=1 if success else 0; proc.confidence=clamp(proc.confidence+(0.05 if success else -0.1)); proc.lifecycle='stable' if proc.transfer_count and proc.confidence>=0.7 else proc.lifecycle
        self.save(); return tr
    def evaluate_benchmark(self, domain, task_type=None, action_ids=None):
        if not self.features.get('benchmark_tracking', True): return None
        acts=[self.actions[i] for i in action_ids] if action_ids else [a for a in self.actions.values() if self._domain(a.objective)==domain or a.tool_used.startswith(domain) or a.action_type==domain]
        if not acts: raise ValueError('benchmark requires action outcomes')
        task_type=task_type or 'general'; successes=sum(1 for a in acts if a.success); failures=len(acts)-successes; mean_err=sum(abs((1 if a.success else 0)-a.confidence_before) for a in acts)/len(acts); mean_lat=sum(a.duration for a in acts)/len(acts); retry=sum(a.retries for a in acts)/len(acts); recoveries=sum(1 for f in self.failures.values() if f.action_id in {a.id for a in acts})/len(acts); help_rate=sum(1 for f in self.failures.values() if f.action_id in {a.id for a in acts} and f.recovery_decision=='ask_human')/len(acts)
        bid=cid('bench_',domain+task_type); old=self.benchmarks.get(bid); rate=successes/len(acts); trend='insufficient_history' if not old else 'improving' if rate>old.success_rate else 'declining' if rate<old.success_rate else 'stable'
        b=BenchmarkRecord(bid,domain,task_type,len(acts),rate,mean_err,mean_lat,retry,recoveries,help_rate,now(),trend); self.benchmarks[bid]=b; self.save(); return b
    def detect_drift(self, domain, recent=5, baseline=10):
        if not self.features.get('drift_detection', True): return None
        acts=[a for a in self.actions.values() if self._domain(a.objective)==domain or a.tool_used.startswith(domain)]
        if len(acts)<recent+baseline: return None
        old=acts[:baseline]; new=acts[-recent:]; old_rate=sum(a.success for a in old)/len(old); new_rate=sum(a.success for a in new)/len(new); latency=(sum(a.duration for a in new)/len(new))-(sum(a.duration for a in old)/len(old)); drift=(old_rate-new_rate)>=0.25 or latency>0.5
        sig={'domain':domain,'baseline_success_rate':old_rate,'recent_success_rate':new_rate,'latency_delta':latency,'drift':drift,'ts':now()}; self.drift_signals[domain]=sig
        if drift:
            for s in self.skills.values():
                if domain in s.skill_name: s.lifecycle='degraded'; s.ask_for_help_flag=True
            for proc in self.procedures.values():
                if proc.domain==domain: proc.confidence=clamp(proc.confidence-0.2); proc.lifecycle='degraded'
        self.save(); return sig
    def debug_failure(self, failure_id, reused_procedure_id=None):
        if not self.features.get('debug_tracing', True): return None
        f=self.failures[failure_id]; similar=[x.id for x in self.failures.values() if x.failure_type==f.failure_type and x.id!=failure_id]; cause=f'pattern:{f.failure_type}' if similar else f.cause_hypothesis; fix='ask_human' if f.recovery_decision=='ask_human' else 'retry_with_smaller_probe' if f.recovery_decision=='retry' else 'change_tool'
        dbg=DebugRecord(cid('dbg_',failure_id+now()), failure_id, cause, similar+[failure_id], [], fix, 'recorded', clamp(0.5+0.1*len(similar)), reused_procedure_id)
        self.debug_records[dbg.id]=dbg
        if reused_procedure_id and reused_procedure_id in self.procedures: self.procedures[reused_procedure_id].known_failure_modes[f.failure_type]=self.procedures[reused_procedure_id].known_failure_modes.get(f.failure_type,0)+1
        self.save(); return dbg
    def calibrate_action_confidence(self, objective, tool_used):
        if not self.features.get('competence_calibration', True): return {'confidence':0.5,'mode':'normal'}
        domain=self._domain(objective); tool=self.tools.get(tool_used, ToolProfile(tool_used)); bench=next((b for b in self.benchmarks.values() if b.domain==domain), None); procs=[p for p in self.procedures.values() if p.objective_type==self._objective_type(objective)]
        proc_conf=max([p.confidence for p in procs], default=0.5); bench_rate=bench.success_rate if bench else 0.5; drift=self.drift_signals.get(domain,{}).get('drift',False); conf=clamp((tool.trust_score+bench_rate+proc_conf)/3 - (0.25 if drift else 0))
        mode='ask_human' if conf<0.25 else 'safer' if conf<0.4 or drift else 'normal'
        return {'confidence':conf,'mode':mode,'domain':domain,'procedure_confidence':proc_conf,'tool_trust':tool.trust_score,'drift':drift}
    def competence_summary(self):
        return {'successful_procedures':[p.id for p in self.procedures.values() if p.success_count>p.failure_count], 'failed_procedures':[p.id for p in self.procedures.values() if p.failure_count>=p.success_count and p.failure_count], 'transferable_patterns':[p.id for p in self.procedures.values() if p.transfer_count>0], 'common_recovery_patterns':{f.recovery_decision:sum(1 for x in self.failures.values() if x.recovery_decision==f.recovery_decision) for f in self.failures.values()}, 'domain_drift_summary':self.drift_signals}
    def knows(self, proposition): return self.meta_state(proposition) == 'known'

cognitive_core=CognitiveCore(Path('noor_state.json'))
