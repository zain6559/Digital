import json, hashlib, time, os, re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from datetime import datetime, UTC
from urllib.parse import urlparse
from .schemas import MemoryIn
from .memory import SpatialMemoryAgent

STATE_VERSION=2

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
    selected_action: str; alternatives: list[str]; risk: str; confidence: float; beliefs_used: list[str]; predictions_used: list[str]; reason_codes: list[str]

class CognitiveCore:
    def __init__(self, path: str|Path='noor_state.json', memory: SpatialMemoryAgent|None=None, limits: dict[str,int]|None=None, features: dict[str,bool]|None=None):
        self.path=Path(path); self.memory=memory or SpatialMemoryAgent(); self.limits={'max_memories':2000,'max_events':2000,'max_inquiries':100,'max_browser_requests':20,'tick_budget_ms':20,'max_tick_checks':50}|(limits or {})
        defaults={'memory':True,'beliefs':True,'inquiry':True,'world_model':True,'prediction':True,'self_model':True,'autonomy':True}; defaults.update(features or {}); self.features=defaults
        self.evidence={}; self.beliefs={}; self.world={}; self.predictions={}; self.goals={}; self.unknowns={}; self.events=[]; self.source_stats={}; self.self_history=[]; self.tick_count=0; self.browser_requests=0; self.version=STATE_VERSION
        self.load()
    def _append_event(self, typ, payload): self.events.append({'type':typ,'payload':payload,'ts':now()}); self.events=self.events[-self.limits['max_events']:]
    def _domain(self, text):
        ts=set(tokens(text));
        for d,keys in {'mobile':{'device','tap','wake','phone','android'},'browser':{'url','search','page','docs'},'world':{'cause','state','relation'},'vision':{'face','image','camera'}}.items():
            if ts & keys: return d
        return 'general'
    def _migrate(self,data): data.setdefault('version',1); return data
    def load(self):
        if not self.path.exists(): return
        try: data=self._migrate(json.loads(self.path.read_text()))
        except Exception: self._append_event('state.load_failed',{}); return
        self.version=data.get('version',1)
        def filt(cls,v):
            names=cls.__dataclass_fields__.keys(); return cls(**{k:v for k,v in v.items() if k in names})
        self.evidence={k:filt(EvidenceRecord,v) for k,v in data.get('evidence',{}).items()}; self.beliefs={k:filt(BeliefRecord,v) for k,v in data.get('beliefs',{}).items()}; self.world={k:filt(WorldRelation,v) for k,v in data.get('world',{}).items()}; self.predictions={k:filt(PredictionRecord,v) for k,v in data.get('predictions',{}).items()}; self.goals={k:filt(GoalRecord,v) for k,v in data.get('goals',{}).items()}; self.unknowns=data.get('unknowns',{}); self.events=data.get('events',[])[:self.limits['max_events']]; self.source_stats=data.get('source_stats',{}); self.self_history=data.get('self_history',[]); self.tick_count=data.get('tick_count',0); self.browser_requests=data.get('browser_requests',0)
    def save(self):
        data={name:{k:asdict(v) for k,v in getattr(self,name).items()} for name in ['evidence','beliefs','world','predictions','goals']}
        data|={'version':STATE_VERSION,'unknowns':self.unknowns,'events':self.events[-self.limits['max_events']:],'source_stats':self.source_stats,'self_history':self.self_history[-500:],'tick_count':self.tick_count,'browser_requests':self.browser_requests}
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix(self.path.suffix+'.tmp'); lock=self.path.with_suffix(self.path.suffix+'.lock')
        fd=os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        try:
            Path(tmp).write_text(json.dumps(data,ensure_ascii=False,indent=2)); os.replace(tmp,self.path)
        finally:
            os.close(fd); Path(lock).unlink(missing_ok=True); Path(tmp).unlink(missing_ok=True)
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
        return DecisionTrace(selected,available_actions,'low' if selected!='search' else 'medium',1-inq['uncertainty'],beliefs,[],[f"meta:{inq['meta_state']}",f"iv:{inq['information_value']:.2f}",f"gain:{inq['expected_gain']:.2f}"])
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
    def _score_result(self,r):
        title=(r.get('title') or '').strip(); url=(r.get('url') or '').strip(); content=(r.get('content') or r.get('snippet') or '').strip();
        if not title or not url: return 0, 'missing_title_or_url'
        host=urlparse(url).netloc.lower(); cred=self.source_credibility(url,'browser'); hints=len(set(tokens(title+' '+content)) & {'docs','documented','official','evidence','study','manual','spec'})*0.08
        return clamp(0.15+cred*0.45+min(len(content),300)/3000+hints), host
    def run_inquiry_results(self, proposition, results):
        self.browser_requests+=1
        if not results: self._append_event('inquiry.search_failed',{'proposition':proposition,'reason':'empty_results'}); self.save(); raise ValueError('search cannot succeed without evidence')
        ev=[]; seen=set()
        for r in results:
            score,reason=self._score_result(r); host=reason
            if score<0.38 or host in seen: continue
            seen.add(host); rel='supports'; ev.append(self.ingest_evidence(proposition,r.get('url') or 'browser','browser',None,rel,score,{'title':r.get('title'),'score':score}))
            st=self.source_stats.setdefault('source:'+host,{'observations':0,'reliability':self.source_credibility(r.get('url') or host,'browser')}); st['observations']+=1; st['reliability']=clamp((st['reliability']*(st['observations']-1)+score)/st['observations'])
        if not ev: self._append_event('inquiry.search_failed',{'proposition':proposition,'reason':'no_usable_evidence'}); self.save(); raise ValueError('search results contained no usable evidence')
        self._append_event('inquiry.search_evidence_attached',{'proposition':proposition,'count':len(ev)}); self.save(); return ev
    def knows(self, proposition): return self.meta_state(proposition) == 'known'

cognitive_core=CognitiveCore(Path('noor_state.json'))
