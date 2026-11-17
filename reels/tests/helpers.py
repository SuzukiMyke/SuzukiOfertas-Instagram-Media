"""Utilitários de teste: config válida mínima em memória."""
import copy
import json
from pathlib import Path

from reel_gen.config import REELS_ROOT, normalize

PILOT = REELS_ROOT / "configs" / "pilot_demo_01.json"


def raw_pilot() -> dict:
    return json.loads(PILOT.read_text(encoding="utf-8"))


def cfg_from(raw: dict) -> dict:
    return normalize(copy.deepcopy(raw))


def pilot_cfg() -> dict:
    return cfg_from(raw_pilot())
