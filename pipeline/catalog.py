"""Каталог типов нарушений и нормативных источников (rules/catalog.yaml)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).resolve().parent.parent / "rules" / "catalog.yaml"


@lru_cache
def load_catalog() -> dict[str, dict]:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {item["id"]: item for item in data["violation_types"]}


def rule_for(type_id: str) -> dict:
    cat = load_catalog()
    if type_id not in cat:
        raise KeyError(f"тип {type_id!r} отсутствует в rules/catalog.yaml")
    return cat[type_id]


def verified_sources(type_id: str) -> list[dict]:
    """Только источники с verified: true — непроверенные ссылки наружу не отдаём."""
    return [s for s in rule_for(type_id).get("sources", []) if s.get("verified")]
