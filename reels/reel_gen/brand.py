"""Marca: paleta, fontes e logotipo.

Reaproveita o gerador híbrido (``gerador/identidade.py`` e ``gerador/render.py``):
lista de fontes por papel ("auto:titulo", "auto:texto", "auto:rotulo"), caminho do
logotipo oficial e recorte "cobrir sem deformar". A paleta é APROXIMADA (amostrada
do logo; não é especificação oficial) e vem sempre da config.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import REPO_ROOT, resolve_path

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gerador import identidade as _idv  # noqa: E402  (reuso do gerador híbrido)
from gerador.render import cobrir  # noqa: E402,F401  (reexportado para layers/synth)


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def color(cfg: dict, name_or_hex: str) -> tuple[int, int, int]:
    """Aceita nome da paleta (bg, primary, ...) ou #RRGGBB."""
    pal = cfg["theme"]["palette"]
    return hex_rgb(pal[name_or_hex] if name_or_hex in pal else name_or_hex)


@lru_cache(maxsize=None)
def font_path(spec: str) -> str:
    """'auto:<papel>' usa a lista de fontes do gerador híbrido; senão é um caminho."""
    if spec.startswith("auto:"):
        role = spec.split(":", 1)[1]
        for nome in _idv.FONTES[role]:
            for pasta in _idv._PASTAS:
                p = Path(pasta) / nome
                if p.exists():
                    return str(p)
        raise FileNotFoundError(f"nenhuma fonte disponível para '{spec}'")
    p = resolve_path(spec)
    if not p.is_file():
        raise FileNotFoundError(f"fonte não encontrada: {spec}")
    return str(p)


@lru_cache(maxsize=None)
def font(spec: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(spec), size)


def logo_image(path: str, size_px: int, opacity: float, mask: str) -> Image.Image:
    """Logo redimensionado com proporção preservada; cores NUNCA alteradas.

    ``mask``: rounded (cantos arredondados), ellipse (como no gerador híbrido) ou none.
    A opacidade só multiplica o canal alfa.
    """
    src = Image.open(resolve_path(path)).convert("RGBA")
    w = size_px
    h = round(size_px * src.height / src.width)
    img = src.resize((w, h), Image.LANCZOS)
    alpha = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(alpha)
    if mask == "rounded":
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(min(w, h) * 0.12), fill=255)
    elif mask == "ellipse":
        m = round(w * 0.04)
        d.ellipse((m, m, w - 1 - m, h - 1 - m), fill=255)
    else:
        d.rectangle((0, 0, w, h), fill=255)
    a = Image.composite(img.getchannel("A"), Image.new("L", (w, h), 0), alpha)
    img.putalpha(a.point(lambda v: round(v * opacity)))
    return img


def source_aspect(path: str) -> float:
    with Image.open(resolve_path(path)) as im:
        return im.width / im.height
