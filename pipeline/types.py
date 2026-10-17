"""Контракт между пайплайном и сервисом. Менять только по договорённости команды."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvidenceFrame:
    timestamp_sec: float
    image_base64: str  # JPEG в base64, без префикса data:


@dataclass
class Violation:
    type_id: str          # ключ из rules/catalog.yaml
    timecode_sec: float   # момент события от начала видео
    description: str      # что видно на видео и почему это может быть нарушением
    evidence_frames: list[EvidenceFrame] = field(default_factory=list)  # 1–3 кадра
    confidence: float = 1.0
