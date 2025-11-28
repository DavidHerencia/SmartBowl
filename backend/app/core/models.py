from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    topic: str
    payload: str
    ts: int


class ActuatorCmd(BaseModel):
    topic: Optional[str] = None
    message: str
    qos: int = Field(default=1, ge=0, le=2)
    retain: bool = False


class HydrationEvent(BaseModel):
    volumen_inicio: float
    volumen_fin: float
    duracion: float
    ts: Optional[int] = None


class HydrationLogItem(BaseModel):
    day: str
    ml: int
    updated_ts: int


class ClassificationResult(BaseModel):
    label: str
    cluster: int
    ml: float
    duracion: float
    hour: int
