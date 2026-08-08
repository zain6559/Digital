import hashlib, math, re
from datetime import datetime, UTC
from .schemas import MemoryIn, MemoryOut

REALMS={'code':'Code Base World','account':'Personal Accounts World','mobile':'Mobile Systems World','history':'Historical Archive World','research':'Research Nebula','general':'Noor Core Archive'}
KEYWORDS={'code':['code','repo','api','function','bug','file','test'], 'account':['account','login','profile','social','password'], 'mobile':['android','phone','adb','screen','notification','tap'], 'history':['past','archive','event','timeline'], 'research':['research','paper','web','source','browser','search']}
TOKEN_RE=re.compile(r'[\w\-]+')
class SpatialMemoryAgent:
    def __init__(self):
        self.memories: dict[str, MemoryOut] = {}
        self._fingerprints: dict[str, str] = {}
    def _tokens(self, text:str)->list[str]: return TOKEN_RE.findall((text or '').lower())
    def realm_for(self, text:str)->str:
        toks=set(self._tokens(text)); scores={k:sum(2 if w in toks else 1 for w in ws if w in toks or w in text.lower()) for k,ws in KEYWORDS.items()}
        key=max(scores, key=scores.get); return REALMS[key if scores[key] else 'general']
    def coords(self, text:str):
        h=int(hashlib.sha256(text.encode()).hexdigest()[:12],16); a=(h%360)*math.pi/180; r=30+(h%70); z=((h//360)%80)-40
        return {'x': round(math.cos(a)*r,2), 'y': round(math.sin(a)*r,2), 'z': float(z)}
    def _fingerprint(self,m:MemoryIn)->str:
        norm=' '.join(self._tokens(m.title+' '+m.content+' '+' '.join(sorted(m.tags))))
        return hashlib.sha1(norm.encode()).hexdigest()[:20]
    def add(self, m:MemoryIn)->MemoryOut:
        fp=self._fingerprint(m)
        if fp in self._fingerprints:
            existing=self.memories[self._fingerprints[fp]]
            if m.importance > existing.importance: existing.importance=m.importance; existing.brightness=min(1.0,0.25+m.importance/10)
            return existing
        text=m.title+' '+m.content+' '+' '.join(m.tags); ident=fp; realm=self.realm_for(text)
        out=MemoryOut(id=ident, **m.model_dump(), realm=realm, position=self.coords(text), brightness=min(1.0,0.25+m.importance/10), created_at=datetime.now(UTC))
        self.memories[ident]=out; self._fingerprints[fp]=ident; return out
    def search(self, q:str):
        terms=set(self._tokens(q)); scored=[]
        for m in self.memories.values():
            title=set(self._tokens(m.title)); content=set(self._tokens(m.content)); tags=set(self._tokens(' '.join(m.tags)))
            score=len(terms & title)*4 + len(terms & tags)*3 + len(terms & content)*2 + m.importance/20
            if score: scored.append((score, m.created_at, m))
        return [m for *_,m in sorted(scored,key=lambda x:(x[0],x[1]), reverse=True)]
    def realms(self):
        data={}
        for m in self.memories.values(): data.setdefault(m.realm,[]).append(m)
        return data
spatial_memory=SpatialMemoryAgent()
