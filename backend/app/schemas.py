from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Optional
from uuid import uuid4

class Risk(str, Enum): low='low'; medium='medium'; high='high'; critical='critical'
class Status(str, Enum): pending='pending'; running='running'; waiting_user='waiting_user'; completed='completed'; failed='failed'; blocked='blocked'

class CommandRequest(BaseModel): prompt: str; context: dict[str, Any] = Field(default_factory=dict)
class TaskRecord(BaseModel): id: str = Field(default_factory=lambda: str(uuid4())); prompt: str; status: Status = Status.pending; risk: Risk = Risk.low; created_at: datetime = Field(default_factory=datetime.utcnow); result: Optional[str]=None
class Event(BaseModel): type: str; payload: dict[str, Any]; ts: datetime = Field(default_factory=datetime.utcnow)
class MemoryIn(BaseModel): title: str; content: str; tags: list[str]=Field(default_factory=list); source: str='user'; importance: int=5
class MemoryOut(MemoryIn): id: str; realm: str; position: dict[str,float]; brightness: float; created_at: datetime
class DeviceCommand(BaseModel): serial: str | None = None; action: str; x: int | None = None; y: int | None = None; text: str | None = None; objective: str | None = None
class VisionFrameIn(BaseModel): source: str; width: int; height: int; mime: str = 'image/png'; data_base64: str = ''
