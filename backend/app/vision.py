import base64
import binascii
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from .schemas import Event
from .websocket import bus

logger = logging.getLogger('noor.vision')

@dataclass
class VisionFrame:
    source: str
    width: int
    height: int
    mime: str
    data_base64: str
    captured_at: float = field(default_factory=time.time)

class LiveVisionContextEngine:
    def __init__(self, max_frames: int = 24, max_pixels: int = 8_294_400):
        self.max_frames = max_frames
        self.max_pixels = max_pixels
        self.frames: dict[str, list[dict[str, Any]]] = {}

    def _signature(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()[:24]

    def _safe_payload(self, frame: VisionFrame) -> bytes:
        if not frame.data_base64:
            return b''
        try:
            return base64.b64decode(frame.data_base64.encode(), validate=True)
        except (binascii.Error, ValueError) as exc:
            logger.warning('invalid base64 frame from %s: %s', frame.source, exc)
            return b''

    def _dimensions(self, width: int, height: int) -> tuple[int, int]:
        width = max(1, min(int(width or 1), 7680))
        height = max(1, min(int(height or 1), 4320))
        if width * height > self.max_pixels:
            scale = (self.max_pixels / (width * height)) ** 0.5
            width = max(1, int(width * scale))
            height = max(1, int(height * scale))
        return width, height

    def _regions(self, width: int, height: int) -> list[dict[str, Any]]:
        thirds_x = [0, width // 3, (width * 2) // 3, width]
        thirds_y = [0, height // 3, (height * 2) // 3, height]
        regions: list[dict[str, Any]] = []
        for yi in range(3):
            for xi in range(3):
                x1, y1, x2, y2 = thirds_x[xi], thirds_y[yi], thirds_x[xi + 1], thirds_y[yi + 1]
                regions.append({'id': f'r{yi}{xi}', 'label': ['top', 'middle', 'bottom'][yi] + '-' + ['left', 'center', 'right'][xi], 'bbox': [x1, y1, x2, y2], 'center': [(x1 + x2) // 2, (y1 + y2) // 2]})
        return regions

    async def ingest(self, frame: VisionFrame) -> dict[str, Any]:
        width, height = self._dimensions(frame.width, frame.height)
        payload = self._safe_payload(frame)
        snapshot = {'source': frame.source or 'unknown', 'width': width, 'height': height, 'mime': frame.mime or 'application/octet-stream', 'signature': self._signature(payload), 'captured_at': frame.captured_at, 'regions': self._regions(width, height)}
        frames = self.frames.setdefault(snapshot['source'], [])
        frames.append(snapshot)
        del frames[:-self.max_frames]
        await bus.publish(Event(type='vision.frame', payload=snapshot))
        return snapshot

    async def inspect(self, source: str, objective: str) -> dict[str, Any]:
        frames = self.frames.get(source, [])
        latest = frames[-1] if frames else {'source': source, 'width': 1, 'height': 1, 'regions': self._regions(1, 1), 'signature': None}
        objective_l = (objective or '').lower()
        vertical = 'middle'
        horizontal = 'center'
        if 'top' in objective_l: vertical = 'top'
        if 'bottom' in objective_l: vertical = 'bottom'
        if 'left' in objective_l: horizontal = 'left'
        if 'right' in objective_l: horizontal = 'right'
        target_label = f'{vertical}-{horizontal}'
        region = next((r for r in latest.get('regions', []) if r['label'] == target_label), None)
        result = {'source': source, 'objective': objective, 'frame_signature': latest.get('signature'), 'target_region': region, 'confidence': 0.72 if region else 0.0, 'strategy': 'safe grid-layout visual fallback; multimodal adapter can refine this target'}
        await bus.publish(Event(type='vision.inspect', payload=result))
        return result

vision_engine = LiveVisionContextEngine()
