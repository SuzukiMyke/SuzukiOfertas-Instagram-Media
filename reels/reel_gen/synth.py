"""Materiais sintéticos de demonstração (somente Pillow, determinísticos).

Gera fundos abstratos — degradês e formas geométricas neutras — a partir de
``configs/synth_assets.json``. NÃO representam produtos, marcas ou pessoas e
devem ser sempre exibidos com o rótulo de demonstração. Nenhuma IA envolvida.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .brand import hex_rgb
from .config import load_json, resolve_path, strip_comments

PATTERNS = ("circuit", "blobs", "bands", "rings", "dots", "waves")


def gradient(w: int, h: int, c1, c2, angle_deg: float = 90.0) -> Image.Image:
    """Degradê linear entre duas cores (ângulo em graus; 90 = vertical)."""
    diag = int(math.hypot(w, h)) + 2
    ramp = Image.linear_gradient("L").resize((diag, diag))
    ramp = ramp.rotate(angle_deg - 90, resample=Image.BICUBIC, expand=False)
    l, t = (diag - w) // 2, (diag - h) // 2
    mask = ramp.crop((l, t, l + w, t + h))
    return Image.composite(Image.new("RGB", (w, h), c2), Image.new("RGB", (w, h), c1), mask)


def _shapes(img: Image.Image, pattern: str, colors, rnd: random.Random) -> Image.Image:
    w, h = img.size
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    u = w / 1080
    if pattern == "circuit":  # grade de linhas e nós (tema "tecnologia", abstrato)
        step = int(120 * u)
        for x in range(0, w, step):
            d.line([(x, 0), (x, h)], fill=colors[0] + (40,), width=max(1, int(2 * u)))
        for y in range(0, h, step):
            d.line([(0, y), (w, y)], fill=colors[0] + (40,), width=max(1, int(2 * u)))
        for _ in range(42):
            x, y = rnd.randrange(0, w, step), rnd.randrange(0, h, step)
            r = int(rnd.choice((10, 16, 24)) * u)
            d.ellipse((x - r, y - r, x + r, y + r), fill=colors[1] + (200,))
        for _ in range(9):
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            s = int(rnd.randint(160, 360) * u)
            d.rounded_rectangle((x, y, x + s, y + int(s * 0.62)), radius=int(28 * u),
                                outline=colors[2] + (150,), width=int(6 * u))
    elif pattern == "blobs":
        for _ in range(14):
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            r = int(rnd.randint(120, 380) * u)
            d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.choice(colors) + (90,))
        over = over.filter(ImageFilter.GaussianBlur(int(18 * u)))
        d = ImageDraw.Draw(over)
        for _ in range(18):
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            r = int(rnd.randint(20, 60) * u)
            d.ellipse((x - r, y - r, x + r, y + r), outline=colors[2] + (170,), width=int(5 * u))
    elif pattern == "bands":
        for i in range(-6, 16):
            x0 = int(i * 180 * u)
            col = colors[i % len(colors)]
            d.polygon([(x0, 0), (x0 + int(90 * u), 0), (x0 + int(90 * u) - h // 2, h), (x0 - h // 2, h)],
                      fill=col + (70,))
        for _ in range(16):
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            r = int(rnd.randint(14, 34) * u)
            d.regular_polygon((x, y, r), n_sides=rnd.choice((3, 4, 6)), fill=colors[2] + (180,))
    elif pattern == "rings":
        cx, cy = w * 0.5, h * 0.45
        for k in range(12):
            r = int((140 + k * 110) * u)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colors[k % len(colors)] + (110,),
                      width=int(rnd.choice((6, 10, 16)) * u))
    elif pattern == "dots":
        step = int(90 * u)
        for y in range(step // 2, h, step):
            for x in range(step // 2, w, step):
                r = int((6 + 12 * (0.5 + 0.5 * math.sin(x / (210 * u) + y / (330 * u)))) * u)
                d.ellipse((x - r, y - r, x + r, y + r), fill=colors[(x // step + y // step) % len(colors)] + (150,))
    elif pattern == "waves":
        for k in range(14):
            pts = [(x, h * (0.08 + k * 0.068) + 60 * u * math.sin(x / (160 * u) + k * 0.7))
                   for x in range(0, w + 8, 8)]
            d.line(pts, fill=colors[k % len(colors)] + (130,), width=int(rnd.choice((6, 12, 20)) * u))
    else:
        raise ValueError(f"padrão sintético desconhecido: {pattern}")
    base = img.convert("RGBA")
    base.alpha_composite(over)
    return base.convert("RGB")


def make_image(spec: dict) -> Image.Image:
    w, h = spec["size"]
    c = [hex_rgb(x) for x in spec["colors"]]
    img = gradient(w, h, c[0], c[1], spec.get("angle", 90))
    return _shapes(img, spec["pattern"], c[1:] + c[:1], random.Random(spec["seed"]))


def generate_all(spec_file: str | Path) -> list[Path]:
    spec = strip_comments(load_json(Path(spec_file)))
    out = []
    for item in spec["images"]:
        if item["pattern"] not in PATTERNS:
            raise ValueError(f"{item['path']}: padrão inválido {item['pattern']}")
        p = resolve_path(item["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        make_image(item).save(p, quality=item.get("quality", 88), optimize=True, subsampling=0)
        out.append(p)
    return out


def brand_background(cfg: dict, w: int, h: int) -> Image.Image:
    """Fundo próprio do CTA (sem foto): degradê da paleta + anéis suaves. Independente de cena."""
    pal = cfg["theme"]["palette"]
    bg, pr = hex_rgb(pal["bg"]), hex_rgb(pal["primary"])
    img = gradient(w, h, bg, pr, 90).convert("RGBA")
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    u = w / 1080
    cx, cy = w / 2, h * 0.36
    for k in range(9):
        r = (220 + k * 120) * u
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 22 - k * 2), width=int(8 * u))
    img.alpha_composite(over.filter(ImageFilter.GaussianBlur(2 * u)))
    return img.convert("RGB")
