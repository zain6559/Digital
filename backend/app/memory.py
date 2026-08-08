import hashlib, math, time
from datetime import datetime
from .schemas import MemoryIn, MemoryOut

REALMS={
 'code':'Code Base World','account':'Personal Accounts World','mobile':'Mobile Systems World','history':'Historical Archive World','research':'Research Nebula','general':'Noor Core Archive'}
KEYWORDS={'code':['code','repo','api','function','bug','file'], 'account':['account','login','profile','social'], 'mobile':['android','phone','adb','screen','notification'], 'history':['past','archive','event'], 'research':['research','paper','web','source']}
class SpatialMemoryAgent:
    def __init__(self): self.memories: dict[str, MemoryOut] = {}
    def realm_for(self, text:str)->str:
        low=text.lower(); scores={k:sum(w in low for w in ws) for k,ws in KEYWORDS.items()}
        key=max(scores, key=scores.get); return REALMS[key if scores[key] else 'general']
    def coords(self, text:str):
        h=int(hashlib.sha256(text.encode()).hexdigest()[:12],16); a=(h%360)*math.pi/180; r=30+(h%70); z=((h//360)%80)-40
        return {'x': round(math.cos(a)*r,2), 'y': round(math.sin(a)*r,2), 'z': float(z)}
    def add(self, m:MemoryIn)->MemoryOut:
        ident=hashlib.sha1(f'{m.title}{m.content}{time.time()}'.encode()).hexdigest()[:16]
        realm=self.realm_for(m.title+' '+m.content+' '+' '.join(m.tags)); out=MemoryOut(id=ident, **m.model_dump(), realm=realm, position=self.coords(m.content), brightness=min(1.0,0.25+m.importance/10), created_at=datetime.utcnow())
        self.memories[ident]=out; return out
    def search(self, q:str):
        terms=set(q.lower().split())
        scored=[]
        for m in self.memories.values():
            blob=(m.title+' '+m.content+' '+' '.join(m.tags)).lower(); score=sum(t in blob for t in terms)
            if score: scored.append((score,m))
        return [m for _,m in sorted(scored,key=lambda x:x[0], reverse=True)]
    def realms(self):
        data={}
        for m in self.memories.values(): data.setdefault(m.realm,[]).append(m)
        return data
spatial_memory=SpatialMemoryAgent()
