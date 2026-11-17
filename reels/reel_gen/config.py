"""Carga e validação do esquema JSON de um reel (somente biblioteca padrão).

Regras gerais:
- chaves desconhecidas são ERRO (exceto chaves iniciadas por "_", tratadas como comentário);
- os valores padrão vêm de ``configs/defaults.json`` e são mesclados sob a config;
- caminhos relativos são resolvidos a partir da RAIZ DO REPOSITÓRIO.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

REELS_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = REELS_ROOT.parent
DEFAULTS_FILE = REELS_ROOT / "configs" / "defaults.json"
POLICY_FILE = REELS_ROOT / "configs" / "content_policy.json"

SCHEMA_VERSION = 1


class ConfigError(ValueError):
    """Erro bloqueante de esquema/conteúdo. ``errors`` lista todas as falhas."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


# ---------------------------------------------------------------- esquema
def _num(lo=None, hi=None):
    return {"t": "num", "lo": lo, "hi": hi}


def _int(lo=None, hi=None):
    return {"t": "int", "lo": lo, "hi": hi}


STR = {"t": "str"}
NESTR = {"t": "str", "nonempty": True}
BOOL = {"t": "bool"}
HEX = {"t": "hex"}


def _enum(*vals):
    return {"t": "enum", "vals": vals}


def _list(item, lo=0, hi=None):
    return {"t": "list", "item": item, "lo": lo, "hi": hi}


def _obj(fields: dict, extra_ok: bool = False):
    """fields: nome -> (spec, obrigatório)."""
    return {"t": "obj", "fields": fields, "extra_ok": extra_ok}


def _map(value):
    return {"t": "map", "value": value}


PAIR01 = {"t": "pair01"}
EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out")
TEXT_ANIMS = ("slide_up", "slide_left", "fade", "none")
TRANSITIONS = ("fade", "slideleft", "slideright", "slideup", "slidedown", "wipeleft", "wiperight",
               "wipeup", "wipedown", "circleopen", "circleclose", "dissolve", "smoothleft", "smoothup")
PRESETS = ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium")

CAMERA = _obj({
    "zoom_start": (_num(1.0, 3.0), True),
    "zoom_end": (_num(1.0, 3.0), True),
    "pan_start": (PAIR01, True),
    "pan_end": (PAIR01, True),
    "easing": (_enum(*EASINGS), True),
})
TRANSITION = _obj({"type": (_enum(*TRANSITIONS), True), "duration": (_num(0.1, 1.5), True)})
HIGHLIGHT = _obj({"text": (NESTR, True), "at": (_num(0, 60), True), "style": (_enum("pill", "tag"), False)})
SOURCE = _obj({
    "path": (NESTR, True),
    "kind": (_enum("real_photo", "illustrative", "synthetic_demo"), True),
    "origin": (NESTR, True),
    "license": (NESTR, True),
    "catalog_id": (STR, False),
    "focus": (PAIR01, False),
})
SCENE = _obj({
    "id": (NESTR, True),
    "category": (NESTR, True),
    "duration": (_num(1.0, 30.0), True),
    "source": (SOURCE, True),
    "title": (NESTR, True),
    "subtitle": (STR, False),
    "highlights": (_list(HIGHLIGHT, 0, 3), False),
    "camera": (CAMERA, True),
    "text_animation": (_enum(*TEXT_ANIMS), False),
    "transition_out": (TRANSITION, False),
    "label": (STR, False),
    "badge": (STR, False),
    "product_model": (STR, False),
    # campos comerciais: só com verified_at + source_url (ver rules.py); vazios no piloto
    "price": (STR, False),
    "discount": (STR, False),
    "stock": (STR, False),
    "rating": (STR, False),
    "verified_at": (STR, False),
    "source_url": (STR, False),
})
AUDIO_TRACK = _obj({
    "file": (NESTR, True),
    "type": (_enum("music", "voice", "sfx"), True),
    "license_id": (NESTR, True),
    "license_url_or_proof": (NESTR, True),
    "author": (NESTR, True),
    "start": (_num(0, 90), True),
    "gain_db": (_num(-60, 12), True),
    "loop": (BOOL, True),
    "fade_in": (_num(0, 10), True),
    "fade_out": (_num(0, 10), True),
})

SCHEMA = _obj({
    "schema_version": (_int(1, 1), True),
    "id": ({"t": "str", "pattern": r"^[a-z0-9][a-z0-9_\-]{0,63}$"}, True),
    "output": (_obj({
        "width": (_int(64, 4096), True),
        "height": (_int(64, 4096), True),
        "fps": (_int(1, 60), True),
        "crf": (_int(0, 51), True),
        "intermediate_crf": (_int(0, 51), True),
        "preset": (_enum(*PRESETS), True),
        "filename": ({"t": "str", "pattern": r"^[A-Za-z0-9_\-.]+\.mp4$"}, True),
        "threads": (_int(1, 8), True),
        "max_bitrate_mbps": (_num(1, 50), True),
        "supersample": (_int(1, 3), True),
    }), True),
    "theme": (_obj({
        "palette": (_obj({k: (HEX, True) for k in ("bg", "primary", "accent", "alert", "text", "text_dark")}), True),
        "font": (_obj({"bold": (NESTR, True), "regular": (NESTR, True), "label": (NESTR, True)}), True),
        "sizes": (_obj({k: (_int(8, 300), True) for k in (
            "hook", "title", "subtitle", "highlight", "category", "label",
            "cta_headline", "button", "button_sub", "disclosure")}), True),
        "panel": (_obj({
            "color": (NESTR, True), "opacity": (_num(0, 1), True),
            "radius": (_int(0, 200), True), "padding": (_list(_int(0, 200), 2, 2), True),
        }), True),
    }), True),
    "safe_zone": (_obj({k: (_int(0, 2000), True) for k in ("top", "bottom", "left", "right")}), True),
    "demo_label": (_obj({"enabled": (BOOL, True), "text": (NESTR, True)}), True),
    "illustrative_label": (NESTR, True),
    "animation": (_obj({
        "fade_in": (_num(0, 2), True), "fade_out": (_num(0, 2), True), "slide_px": (_int(0, 400), True),
        "stagger": (_num(0, 2), True), "text_delay": (_num(0, 2), True), "hook_dim": (_num(0, 0.9), True),
    }), True),
    "hook": (_obj({
        "duration": (_num(0.5, 10), True),
        "lines": (_list(NESTR, 1, 2), True),
        "background": ({"t": "str", "pattern": r"^(scene:\d+|brand)$"}, True),
        "animation": (_enum(*TEXT_ANIMS), True),
        "camera": (CAMERA, False),
        "transition_out": (TRANSITION, False),
    }), False),
    "scenes": (_list(SCENE, 1, 10), True),
    "cta": (_obj({
        "duration": (_num(0.5, 15), True),
        "headline": (NESTR, True),
        "buttons": (_list(NESTR, 1, 3), True),
        "links_display": (_enum("channels_official"), True),
        "show_logo": (BOOL, True),
        "disclosure": (STR, True),
        "independent_background": (BOOL, True),
        "camera": (CAMERA, False),
    }), False),
    "channels": (_map(_obj({"label": (NESTR, True), "url": (NESTR, True), "display": (NESTR, True)})), False),
    "logo": (_obj({
        "path": (NESTR, True),
        "position": (_enum("top_left", "top_right"), True),
        "size_px": (_int(40, 600), True),
        "cta_size_px": (_int(40, 900), True),
        "opacity": (_num(0.1, 1.0), True),
        "show_on_scenes": (BOOL, True),
        "mask": (_enum("rounded", "ellipse", "none"), True),
    }), True),
    "audio": (_obj({
        "mode": (_enum("silent", "licensed"), True),
        "tracks": (_list(AUDIO_TRACK, 0, 8), True),
        "silent_track": (BOOL, True),
        "loudnorm": (_obj({"I": (_num(-40, -5), True), "TP": (_num(-9, 0), True), "LRA": (_num(1, 20), True)}), True),
        "ducking": (BOOL, True),
    }), True),
    "policy": (_obj({"extra_forbidden_terms": (_list(NESTR), False)}), False),
    "validation": (_obj({k: (_num(0, 10_000), True) for k in (
        "duration_min", "duration_max", "duration_tolerance", "duration_hard_max",
        "max_bitrate_mbps", "max_size_mb", "hook_max", "cta_min",
        "min_body_px", "min_title_px", "min_contrast",
        "min_frame_stddev", "motion_spike_ratio", "logo_max_mad")}), True),
})

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _check(v, spec, path: str, errs: list[str]) -> None:
    t = spec["t"]
    if t in ("num", "int"):
        ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        if t == "int":
            ok = ok and float(v).is_integer()
        if not ok:
            errs.append(f"{path}: esperado {'inteiro' if t == 'int' else 'número'}, recebido {v!r}")
            return
        if spec["lo"] is not None and v < spec["lo"]:
            errs.append(f"{path}: {v} < mínimo {spec['lo']}")
        if spec["hi"] is not None and v > spec["hi"]:
            errs.append(f"{path}: {v} > máximo {spec['hi']}")
    elif t == "str":
        if not isinstance(v, str):
            errs.append(f"{path}: esperado texto, recebido {type(v).__name__}")
            return
        if spec.get("nonempty") and not v.strip():
            errs.append(f"{path}: não pode ser vazio")
        if spec.get("pattern") and not re.match(spec["pattern"], v):
            errs.append(f"{path}: valor {v!r} fora do formato {spec['pattern']}")
    elif t == "bool":
        if not isinstance(v, bool):
            errs.append(f"{path}: esperado true/false, recebido {v!r}")
    elif t == "hex":
        if not (isinstance(v, str) and _HEX_RE.match(v)):
            errs.append(f"{path}: cor deve ser #RRGGBB, recebido {v!r}")
    elif t == "enum":
        if v not in spec["vals"]:
            errs.append(f"{path}: {v!r} não é uma opção válida {list(spec['vals'])}")
    elif t == "pair01":
        if not (isinstance(v, list) and len(v) == 2 and all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1 for x in v)):
            errs.append(f"{path}: esperado [x, y] com valores entre 0 e 1, recebido {v!r}")
    elif t == "list":
        if not isinstance(v, list):
            errs.append(f"{path}: esperado lista, recebido {type(v).__name__}")
            return
        if len(v) < spec["lo"] or (spec["hi"] is not None and len(v) > spec["hi"]):
            errs.append(f"{path}: lista com {len(v)} itens (permitido {spec['lo']}..{spec['hi'] or '∞'})")
        for i, item in enumerate(v):
            _check(item, spec["item"], f"{path}[{i}]", errs)
    elif t == "map":
        if not isinstance(v, dict):
            errs.append(f"{path}: esperado objeto")
            return
        for k, item in v.items():
            _check(item, spec["value"], f"{path}.{k}", errs)
    elif t == "obj":
        if not isinstance(v, dict):
            errs.append(f"{path}: esperado objeto, recebido {type(v).__name__}")
            return
        fields = spec["fields"]
        for k in v:
            if k not in fields and not spec["extra_ok"]:
                errs.append(f"{path}.{k}: chave desconhecida")
        for k, (sub, req) in fields.items():
            if k in v:
                _check(v[k], sub, f"{path}.{k}", errs)
            elif req:
                errs.append(f"{path}.{k}: campo obrigatório ausente")
    else:  # pragma: no cover
        raise AssertionError(t)


def strip_comments(obj):
    """Remove chaves iniciadas por "_" (comentários) recursivamente."""
    if isinstance(obj, dict):
        return {k: strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_comments(x) for x in obj]
    return obj


def deep_merge(base, over):
    """Mescla dicionários recursivamente; listas e escalares de ``over`` substituem."""
    if isinstance(base, dict) and isinstance(over, dict):
        out = copy.deepcopy(base)
        for k, v in over.items():
            out[k] = deep_merge(base[k], v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def load_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError([f"{path}: JSON inválido ({e})"]) from e


def load_defaults() -> dict:
    return strip_comments(load_json(DEFAULTS_FILE))


def resolve_path(p: str) -> Path:
    """Resolve caminho relativo à raiz do repositório (absoluto é aceito como está)."""
    pp = Path(p)
    return pp if pp.is_absolute() else (REPO_ROOT / pp)


def validate_schema(cfg: dict) -> list[str]:
    errs: list[str] = []
    _check(cfg, SCHEMA, "config", errs)
    return errs


def normalize(raw: dict) -> dict:
    """Comentários removidos + padrões mesclados + validação de esquema. Levanta ConfigError."""
    user = strip_comments(raw)
    errs: list[str] = []
    # chaves desconhecidas são verificadas ANTES da mescla, para não serem mascaradas
    _check_unknown_only(user, SCHEMA, "config", errs)
    if errs:
        raise ConfigError(errs)
    cfg = deep_merge(load_defaults(), user)
    errs = validate_schema(cfg)
    if errs:
        raise ConfigError(errs)
    return cfg


def _check_unknown_only(v, spec, path, errs):
    if spec["t"] == "obj" and isinstance(v, dict):
        for k, item in v.items():
            if k not in spec["fields"]:
                if not spec["extra_ok"]:
                    errs.append(f"{path}.{k}: chave desconhecida")
            else:
                _check_unknown_only(item, spec["fields"][k][0], f"{path}.{k}", errs)
    elif spec["t"] == "list" and isinstance(v, list):
        for i, item in enumerate(v):
            _check_unknown_only(item, spec["item"], f"{path}[{i}]", errs)
    elif spec["t"] == "map" and isinstance(v, dict):
        for k, item in v.items():
            _check_unknown_only(item, spec["value"], f"{path}.{k}", errs)


def load_config(path: str | Path) -> dict:
    """Carrega, mescla padrões e valida esquema. Regras de conteúdo ficam em rules.py."""
    raw = load_json(Path(path))
    cfg = normalize(raw)
    if cfg["schema_version"] != SCHEMA_VERSION:
        raise ConfigError([f"schema_version {cfg['schema_version']} não suportada"])
    return cfg
