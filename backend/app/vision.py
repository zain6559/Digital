import base64,binascii,hashlib,logging,time
from dataclasses import dataclass, field
from typing import Any
from .schemas import Event
from .websocket import bus
logger=logging.getLogger('noor.vision')
@dataclass
class VisionFrame:
    source:str; width:int; height:int; mime:str; data_base64:str; captured_at:float=field(default_factory=time.time)
class LiveVisionContextEngine:
    def __init__(self,max_frames:int=24,max_pixels:int=8_294_400): self.max_frames=max_frames; self.max_pixels=max_pixels; self.frames={}; self.mode='grid_fallback'
    def _signature(self,payload:bytes)->str: return hashlib.sha256(payload).hexdigest()[:24]
    def _safe_payload(self,frame:VisionFrame)->tuple[bytes,list[str]]:
        warnings=[]
        if frame.mime not in {'image/png','image/jpeg','image/webp','application/octet-stream'}: warnings.append('unsupported_mime_treated_as_bytes')
        if not frame.data_base64: return b'', warnings+['empty_payload']
        try: return base64.b64decode(frame.data_base64.encode(),validate=True), warnings
        except (binascii.Error,ValueError) as exc: logger.warning('invalid base64 frame from %s: %s',frame.source,exc); return b'', warnings+['invalid_base64']
    def _dimensions(self,width:int,height:int)->tuple[int,int,list[str]]:
        warnings=[]; ow,oh=width,height; width=max(1,min(int(width or 1),7680)); height=max(1,min(int(height or 1),4320))
        if (ow,oh)!=(width,height): warnings.append('dimensions_clamped')
        if width*height>self.max_pixels:
            scale=(self.max_pixels/(width*height))**0.5; width=max(1,int(width*scale)); height=max(1,int(height*scale)); warnings.append('dimensions_scaled_to_limit')
        return width,height,warnings
    def _regions(self,width:int,height:int)->list[dict[str,Any]]:
        xs=[0,width//3,(width*2)//3,width]; ys=[0,height//3,(height*2)//3,height]; out=[]
        for yi in range(3):
            for xi in range(3):
                x1,y1,x2,y2=xs[xi],ys[yi],xs[xi+1],ys[yi+1]
                out.append({'id':f'r{yi}{xi}','label':['top','middle','bottom'][yi]+'-'+['left','center','right'][xi],'bbox':[x1,y1,x2,y2],'center':[(x1+x2)//2,(y1+y2)//2]})
        return out
    async def ingest(self,frame:VisionFrame)->dict[str,Any]:
        width,height,w1=self._dimensions(frame.width,frame.height); payload,w2=self._safe_payload(frame)
        snap={'source':frame.source or 'unknown','width':width,'height':height,'mime':frame.mime or 'application/octet-stream','signature':self._signature(payload),'captured_at':frame.captured_at,'regions':self._regions(width,height),'mode':self.mode,'confidence':0.35 if payload else 0.2,'warnings':w1+w2}
        frames=self.frames.setdefault(snap['source'],[]); frames.append(snap); del frames[:-self.max_frames]
        await bus.publish(Event(type='vision.frame',payload=snap)); return snap
    async def inspect(self,source:str,objective:str)->dict[str,Any]:
        frames=self.frames.get(source,[]); latest=frames[-1] if frames else {'source':source,'width':1,'height':1,'regions':self._regions(1,1),'signature':None,'warnings':['no_frame_available']}
        o=(objective or '').lower(); v='middle'; h='center'
        if 'top' in o: v='top'
        if 'bottom' in o: v='bottom'
        if 'left' in o: h='left'
        if 'right' in o: h='right'
        region=next((r for r in latest.get('regions',[]) if r['label']==f'{v}-{h}'),None)
        directional=any(w in o for w in ['top','bottom','left','right','center','middle'])
        res={'source':source,'objective':objective,'frame_signature':latest.get('signature'),'target_region':region,'confidence':0.55 if directional and region else 0.25,'mode':self.mode,'strategy':'Grid fallback only: estimates a region from objective words; it does not identify visual objects.','warnings':latest.get('warnings',[])}
        await bus.publish(Event(type='vision.inspect',payload=res)); return res
vision_engine=LiveVisionContextEngine()
