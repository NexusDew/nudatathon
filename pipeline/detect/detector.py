"""Детектор объектов D-FINE (Objects365, Apache 2.0) через transformers.

Возвращает для каждого кадра список детекций только по интересующим классам,
приведённым к нашим коротким именам (phone, cup, food, laptop, bag, ...).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

WEIGHTS_DIR = Path(os.getenv("WEIGHTS_DIR", "D:/nudatathon_weights"))

# Objects365 -> наши классы
CLASS_MAP = {
    "Person": "person",
    "Cell Phone": "phone",
    "Cup": "cup", "Bottle": "cup", "Canned": "cup", "Tea pot": "cup",
    "Bread": "food", "Sandwich": "food", "Hamburger": "food", "Cookies": "food",
    "Donut": "food", "Cake": "food", "Candy": "food",
    "Laptop": "laptop", "Monitor/TV": "laptop", "Tablet": "tablet",
    "Handbag/Satchel": "bag", "Backpack": "bag", "Luggage": "bag", "Briefcase": "bag", "Wallet/Purse": "wallet",
    "Chair": "chair",
    "Desk": "desk", "Dinning Table": "desk", "Side Table": "desk",
    "Telephone": "desk_phone", "Storage box": "box", "Cabinet/shelf": "cabinet",
}


@dataclass
class Det:
    cls: str
    score: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 в пикселях исходного кадра


class Detector:
    def __init__(self, model_dir: str | Path | None = None, device: str | None = None, threshold: float = 0.3):
        import torch
        from transformers import AutoImageProcessor, DFineForObjectDetection

        model_dir = Path(model_dir or WEIGHTS_DIR / "dfine")
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.processor = AutoImageProcessor.from_pretrained(model_dir)
        self.model = DFineForObjectDetection.from_pretrained(model_dir, torch_dtype=self.dtype).to(self.device).eval()
        self.threshold = threshold
        id2label = self.model.config.id2label
        self.keep = {int(i): CLASS_MAP[name] for i, name in id2label.items() if name in CLASS_MAP}

    def __call__(self, frames_bgr: list[np.ndarray], batch: int = 2) -> list[list[Det]]:
        # Малые батчи + сброс кэша PyTorch: на 8 ГБ рядом с VLM каждые 0.5 ГБ резерва
        # выталкивают модель в общую память Windows и замедляют всё в разы
        out = []
        for i in range(0, len(frames_bgr), batch):
            out += self._run(frames_bgr[i:i + batch])
        if self.device == "cuda":
            self.torch.cuda.empty_cache()
        return out

    def _run(self, frames_bgr: list[np.ndarray]) -> list[list[Det]]:
        torch = self.torch
        # Препроцессор растягивает кадр до 640×640 (bilinear) и на Full HD делает это медленно (~1 с на кадр).
        # Делаем то же самое заранее через OpenCV — геометрия для модели не меняется, его resize становится
        # холостым. Рамки возвращаются в размерах исходника через target_sizes ниже.
        small = [cv2.resize(f, (640, 640), interpolation=cv2.INTER_LINEAR) for f in frames_bgr]
        rgb = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in small]
        inputs = self.processor(images=rgb, return_tensors="pt").to(self.device)
        inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)
        with torch.inference_mode():
            out = self.model(**inputs)
        sizes = torch.tensor([f.shape[:2] for f in frames_bgr], device=self.device)
        res = self.processor.post_process_object_detection(out, target_sizes=sizes, threshold=self.threshold)
        batch = []
        for r in res:
            dets = []
            for s, l, b in zip(r["scores"].tolist(), r["labels"].tolist(), r["boxes"].tolist()):
                if l in self.keep:
                    dets.append(Det(self.keep[l], round(s, 3), tuple(round(x, 1) for x in b)))
            batch.append(dets)
        return batch
