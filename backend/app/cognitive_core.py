import json, hashlib, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from datetime import datetime, UTC
from .schemas import MemoryIn
from .memory import SpatialMemoryAgent

def now(): return datetime.now(UTC).isoformat()
def cid(prefix: str, text: str) -> str: return prefix + hashlib.sha1(text.encode()).hexdigest()[:12]
def clamp(v: float) -> float: return max(0.0, min(1.0, v))

@dataclass
class EvidenceRecord:
    id: str; claim: str; source: str; source_type: str; source_reliability: float; relation: str; strength: float; collected_at: str; metadata: dict[str, Any]=field(default_factory=dict)

@dataclass
class BeliefRecord:
    id: str; proposition: str; confidence: float; evidence: list[str]=field(default_factory=list); counter_evidence: list[str]=field(default_factory=list); source: str='system'; created_at: str=field(default_factory=now); updated_at: str=field(default_factory=now); last_tested_at: str|None=None; prediction_history: list[str]=field(default_factory=list); contradiction_count: int=0; revision_count: int=0; status: str='active'; audit_trail: list[dict[str, Any]]=field(default_factory=list)

@dataclass
class WorldRelation:
    id: str; subject: str; relation: str; object: str; confidence: float; evidence: list[str]=field(default_factory=list); updated_at: str=field(default_factory=now)

@dataclass
class PredictionRecord:
    id: str; proposition: str; expected: str; probability: float; belief_ids: list[str]; created_at: str=field(default_factory=now); due_at: str|None=None; outcome: str|None=None; error: float|None=None; resolved_at: str|None=None

@dataclass
class GoalRecord:
    id: str; objective: str; priority: float; origin: str; progress: float=0.0; confidence: float=0.5; dependencies: list[str]=field(default_factory=list); success_criteria: list[str]=field(default_factory=list); deadline: str|None=None; status: str='active'

@dataclass
class DecisionTrace:
    selected_action: str; alternatives: list[str]; risk: str; confidence: float; beliefs_used: list[str]; predictions_used: list[str]; reason_codes: list[str]

class CognitiveCore:
    def __init__(self, path: str|Path='noor_state.json', memory: SpatialMemoryAgent|None=None, limits: dict[str,int]|None=None, features: dict[str,bool]|None=None):
        self.path=Path(path); self.memory=memory or SpatialMemoryAgent(); self.limits={'max_memories':2000,'max_events':2000,'max_inquiries':100,'max_browser_requests':20,'tick_budget_ms':20}|(limits or {})
        defaults={'memory':True,'beliefs':True,'inquiry':True,'world_model':True,'prediction':True,'self_model':True,'autonomy':True}; defaults.update(features or {}); self.features=defaults
        self.evidence={}; self.beliefs={}; self.world={}; self.predictions={}; self.goals={}; self.unknowns={}; self.events=[]; self.source_stats={}; self.self_history=[]; self.tick_count=0; self.browser_requests=0
        self.load()
    def _append_event(self, typ, payload):
        self.events.append({'type':typ,'payload':payload,'ts':now()}); self.events=self.events[-self.limits['max_events']:]
    def load(self):
        if not self.path.exists(): return
        try: data=json.loads(self.path.read_text())
        except Exception: self._append_event('state.load_failed',{}); return
        self.evidence={k:EvidenceRecord(**v) for k,v in data.get('evidence',{}).items()}; self.beliefs={k:BeliefRecord(**v) for k,v in data.get('beliefs',{}).items()}; self.world={k:WorldRelation(**v) for k,v in data.get('world',{}).items()}; self.predictions={k:PredictionRecord(**v) for k,v in data.get('predictions',{}).items()}; self.goals={k:GoalRecord(**v) for k,v in data.get('goals',{}).items()}; self.unknowns=data.get('unknowns',{}); self.events=data.get('events',[])[:self.limits['max_events']]; self.source_stats=data.get('source_stats',{}); self.self_history=data.get('self_history',[]); self.tick_count=data.get('tick_count',0); self.browser_requests=data.get('browser_requests',0)
    def save(self):
        data={name:{k:asdict(v) for k,v in getattr(self,name).items()} for name in ['evidence','beliefs','world','predictions','goals']}
        data|={'unknowns':self.unknowns,'events':self.events[-self.limits['max_events']:],'source_stats':self.source_stats,'self_history':self.self_history[-500:],'tick_count':self.tick_count,'browser_requests':self.browser_requests}
        self.path.parent.mkdir(parents=True,exist_ok=True); self.path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    def meta_state(self, proposition: str) -> str:
        b=self.beliefs.get(cid('b_', proposition.lower()))
        if not b: return 'unknown'
        if b.status in {'rejected','suspended'}: return b.status
        if b.contradiction_count and b.evidence and b.counter_evidence: return 'contradictory'
        if b.confidence>=0.75: return 'known'
        if b.confidence>=0.55: return 'likely'
        return 'uncertain'
    def ingest_evidence(self, claim: str, source: str, source_type='user', source_reliability=0.7, relation='supports', strength=0.6, metadata=None):
        if not source or not claim: raise ValueError('evidence requires source and claim')
        if relation not in {'supports','contradicts'}: raise ValueError('evidence relation must support or contradict')
        e=EvidenceRecord(cid('e_', claim+source+relation+now()), claim, source, source_type, clamp(source_reliability), relation, clamp(strength), now(), metadata or {})
        self.evidence[e.id]=e; self._append_event('evidence.created',asdict(e))
        if self.features['beliefs']: self.apply_evidence(e)
        if self.features['memory']: self.memory.add(MemoryIn(title=f'Evidence: {claim[:60]}',content=claim,tags=['evidence',relation],source=source,importance=max(1,int(strength*10))))
        self.save(); return e
    def apply_evidence(self, e: EvidenceRecord):
        bid=cid('b_', e.claim.lower()); b=self.beliefs.get(bid)
        if not b:
            b=BeliefRecord(bid,e.claim,0.5,source=e.source); self.beliefs[bid]=b
        before=b.confidence; weight=e.strength*e.source_reliability
        if e.relation=='supports': b.evidence.append(e.id); b.confidence=clamp(b.confidence+(1-b.confidence)*weight*0.55)
        else: b.counter_evidence.append(e.id); b.confidence=clamp(b.confidence-b.confidence*weight*0.85); b.contradiction_count+=1
        b.revision_count+=1; b.updated_at=now(); b.last_tested_at=now();
        if b.confidence<0.2: b.status='rejected'
        elif b.counter_evidence and b.evidence and abs(len(b.evidence)-len(b.counter_evidence))<=2: b.status='suspended' if b.confidence<0.45 else 'active'
        b.audit_trail.append({'before':before,'after':b.confidence,'evidence':e.id,'reason':e.relation,'ts':now()})
        self.update_world_from_belief(b,e)
        return b
    def merge_beliefs(self, a: str, b: str):
        ba=self.beliefs[cid('b_',a.lower())]; bb=self.beliefs.pop(cid('b_',b.lower()))
        before=ba.confidence; total=len(ba.evidence)+len(bb.evidence)+len(ba.counter_evidence)+len(bb.counter_evidence) or 1
        ba.evidence+=bb.evidence; ba.counter_evidence+=bb.counter_evidence; ba.confidence=clamp((ba.confidence+bb.confidence)/2); ba.revision_count+=1; ba.updated_at=now(); ba.audit_trail.append({'before':before,'after':ba.confidence,'reason':'merge','merged':bb.id,'ts':now()}); self.save(); return ba
    def update_world_from_belief(self,b:BeliefRecord,e:EvidenceRecord):
        if not self.features['world_model']: return None
        words=b.proposition.split()
        if len(words)>=3: subj,rel,obj=words[0],words[1],' '.join(words[2:])
        else: subj,rel,obj='claim','states',b.proposition
        rid=cid('w_',subj+rel+obj); wr=self.world.get(rid) or WorldRelation(rid,subj,rel,obj,b.confidence)
        wr.confidence=b.confidence; wr.evidence.append(e.id); wr.updated_at=now(); self.world[rid]=wr; return wr
    def create_goal(self, objective, priority=0.5, origin='user', success_criteria=None):
        g=GoalRecord(cid('g_',objective+origin),objective,clamp(priority),origin,success_criteria=success_criteria or []); self.goals[g.id]=g; self.save(); return g
    def create_prediction(self, proposition, expected, probability, belief_ids=None):
        if not self.features['prediction']: return None
        p=PredictionRecord(cid('p_',proposition+expected+now()),proposition,expected,clamp(probability),belief_ids or [])
        self.predictions[p.id]=p
        for bid in p.belief_ids:
            if bid in self.beliefs: self.beliefs[bid].prediction_history.append(p.id)
        self.save(); return p
    def record_outcome(self, prediction_id, outcome):
        p=self.predictions[prediction_id]; p.outcome=outcome; happened=outcome==p.expected; p.error=abs((1.0 if happened else 0.0)-p.probability); p.resolved_at=now()
        for bid in p.belief_ids:
            if bid in self.beliefs:
                rel='supports' if happened else 'contradicts'; self.ingest_evidence(self.beliefs[bid].proposition,'outcome','system',0.9,rel,min(1,p.error+0.2),{'prediction':prediction_id})
        
        if self.features['self_model']:
            self.learn_from_prediction(p)
        self.save(); return p
    def learn_from_prediction(self,p:PredictionRecord):
        bucket=p.proposition.split()[0] if p.proposition.split() else 'general'; stats=self.source_stats.setdefault(bucket,{'predictions':0,'errors':0,'success':0})
        stats['predictions']+=1; stats['errors']+=p.error or 0; stats['success']+=1 if (p.error or 1)<0.5 else 0
        self.self_history.append({'domain':bucket,'accuracy':stats['success']/stats['predictions'],'mean_error':stats['errors']/stats['predictions'],'ts':now()})
    def self_model(self):
        return {k:{'prediction_count':v['predictions'],'accuracy':v['success']/v['predictions'] if v['predictions'] else 0,'mean_error':v['errors']/v['predictions'] if v['predictions'] else 0} for k,v in self.source_stats.items()}
    def evaluate_inquiry(self, proposition, importance=0.5):
        state=self.meta_state(proposition); uncertainty={'unknown':1,'uncertain':0.7,'contradictory':0.9,'likely':0.35,'known':0.1}.get(state,0.5); value=uncertainty*importance
        if not self.features['inquiry']: action='reason_internally'
        elif self.browser_requests>=self.limits['max_browser_requests']: action='defer'
        elif value>=0.45: action='search'
        elif uncertainty>=0.7: action='ask_human'
        else: action='act_despite_uncertainty'
        return {'unknown':state=='unknown','meta_state':state,'uncertainty':uncertainty,'information_value':value,'action':action,'query':proposition if action=='search' else None}
    def decide(self, objective: str, available_actions=None):
        available_actions=available_actions or ['defer','ask_human','search','record_memory']
        inq=self.evaluate_inquiry(objective,0.8); beliefs=[b.id for b in self.beliefs.values() if objective.lower() in b.proposition.lower()]
        selected=inq['action'] if inq['action'] in available_actions else 'defer'
        if not self.features['beliefs'] and 'ask_human' in available_actions: selected='ask_human'
        return DecisionTrace(selected,available_actions,'low' if selected!='search' else 'medium',1-inq['uncertainty'],beliefs,[],[f"meta:{inq['meta_state']}",f"iv:{inq['information_value']:.2f}"])
    def tick(self):
        if not self.features['autonomy']: return {'action':'disabled'}
        start=time.perf_counter(); self.tick_count+=1; action='idle'; checked=0
        for b in list(self.beliefs.values())[:50]:
            checked+=1
            if self.meta_state(b.proposition) in {'unknown','uncertain','contradictory'}:
                d=self.decide(b.proposition,['defer','ask_human','search']); action=d.selected_action; break
            if (time.perf_counter()-start)*1000>self.limits['tick_budget_ms']: break
        self._append_event('life.tick',{'tick':self.tick_count,'action':action,'checked':checked});
        if self.tick_count%100==0: self.save()
        return {'tick':self.tick_count,'action':action,'checked':checked,'events':len(self.events)}
    def run_inquiry_results(self, proposition, results):
        if not results: raise ValueError('search cannot succeed without evidence')
        self.browser_requests+=1; ev=[]
        for r in results:
            text=(r.get('title') or '')+' '+(r.get('url') or '')
            if text.strip(): ev.append(self.ingest_evidence(proposition,r.get('url') or 'browser','browser',0.55,'supports',0.45,{'title':r.get('title')}))
        if not ev: raise ValueError('search results contained no usable evidence')
        return ev
    def knows(self, proposition): return self.meta_state(proposition) == 'known'

cognitive_core=CognitiveCore(Path('noor_state.json'))
