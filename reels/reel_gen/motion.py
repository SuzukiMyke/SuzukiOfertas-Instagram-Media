"""Movimento de câmera e de texto: easing e expressões FFmpeg.

Técnica de câmera (registrada no STATUS_REELS.md): o fundo é pré-ampliado
(``output.supersample``, padrão 2x = 2160x3840) em RGB sem subamostragem de
croma e animado com ``zoompan`` (um único quadro de entrada, ``d`` = nº de
quadros da cena). O zoompan arredonda a janela para pixels inteiros DA
ENTRADA; com a entrada 2x o erro máximo cai para 0,5 px na saída e, em RGB,
x/y não são forçados a valores pares (como ocorreria em yuv420p). Isso elimina
a trepidação típica do zoompan aplicado sobre a imagem em 1x.
"""
from __future__ import annotations

import math

# --------------------------------------------------------------- easing
# Expressões em função de p (0..1). Usadas tanto no FFmpeg quanto em Python (testes).
EASE_EXPR = {
    "linear": "({p})",
    "ease_in": "(({p})*({p}))",
    "ease_out": "(1-(1-({p}))*(1-({p})))",
    "ease_in_out": "(({p})*({p})*(3-2*({p})))",
}


def ease(name: str, p: float) -> float:
    p = min(max(p, 0.0), 1.0)
    if name == "linear":
        return p
    if name == "ease_in":
        return p * p
    if name == "ease_out":
        return 1 - (1 - p) * (1 - p)
    if name == "ease_in_out":
        return p * p * (3 - 2 * p)
    raise ValueError(f"easing desconhecido: {name}")


def ease_expr(name: str, p_expr: str) -> str:
    return EASE_EXPR[name].format(p=p_expr)


def _f(x: float) -> str:
    """Número em formato curto e determinístico para expressões."""
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


# --------------------------------------------------------------- câmera
def camera_values(cam: dict, n_frames: int, frame: int) -> tuple[float, float, float]:
    """(zoom, cx, cy) no quadro ``frame`` — espelho em Python da expressão FFmpeg."""
    p = frame / max(n_frames - 1, 1)
    e = ease(cam["easing"], p)
    z = cam["zoom_start"] + (cam["zoom_end"] - cam["zoom_start"]) * e
    cx = cam["pan_start"][0] + (cam["pan_end"][0] - cam["pan_start"][0]) * e
    cy = cam["pan_start"][1] + (cam["pan_end"][1] - cam["pan_start"][1]) * e
    return z, cx, cy


def window(cam: dict, n_frames: int, frame: int, iw: int, ih: int) -> tuple[float, float, float, float]:
    """Janela (x, y, w, h) na imagem de entrada, com os mesmos limites do zoompan."""
    z, cx, cy = camera_values(cam, n_frames, frame)
    w, h = iw / z, ih / z
    x = min(max(cx * iw - w / 2, 0), iw - w)
    y = min(max(cy * ih - h / 2, 0), ih - h)
    return x, y, w, h


def zoompan_filter(cam: dict, n_frames: int, out_w: int, out_h: int, fps: int) -> str:
    """Filtro zoompan com easing. Opções entre aspas simples (vírgulas internas protegidas)."""
    p = f"on/{max(n_frames - 1, 1)}"
    e = ease_expr(cam["easing"], p)
    zs, ze = cam["zoom_start"], cam["zoom_end"]
    (pxs, pys), (pxe, pye) = cam["pan_start"], cam["pan_end"]
    z = f"{_f(zs)}+({_f(ze - zs)})*{e}"
    cx = f"({_f(pxs)}+({_f(pxe - pxs)})*{e})"
    cy = f"({_f(pys)}+({_f(pye - pys)})*{e})"
    x = f"clip({cx}*iw-iw/zoom/2,0,iw-iw/zoom)"
    y = f"clip({cy}*ih-ih/zoom/2,0,ih-ih/zoom)"
    return (f"zoompan=z='{z}':x='{x}':y='{y}':d={n_frames}"
            f":s={out_w}x{out_h}:fps={fps}")


# --------------------------------------------------------------- texto
def slide_offsets(anim: str, slide_px: int) -> tuple[int, int]:
    """Deslocamento inicial (dx, dy) da animação; a camada termina na posição final."""
    if anim == "slide_up":
        return 0, slide_px
    if anim == "slide_left":
        return slide_px, 0
    return 0, 0


def overlay_xy(x: int, y: int, anim: str, slide_px: int, t_in: float, dur: float) -> tuple[str, str]:
    """Expressões x/y do overlay: desliza com ease_out de (x+dx, y+dy) até (x, y)."""
    dx, dy = slide_offsets(anim, slide_px)
    if dx == 0 and dy == 0:
        return str(x), str(y)
    p = f"clip((t-{_f(t_in)})/{_f(max(dur, 1e-3))},0,1)"
    rem = f"(1-{ease_expr('ease_out', p)})"
    xs = f"{x}+{dx}*{rem}" if dx else str(x)
    ys = f"{y}+{dy}*{rem}" if dy else str(y)
    return xs, ys


def frames_for(seconds: float, fps: int) -> int:
    return max(1, int(round(seconds * fps)))


def smoothness_ratio(diffs: list[float]) -> float:
    """max/mediana das diferenças entre quadros consecutivos (1 = perfeitamente regular)."""
    vals = sorted(d for d in diffs if d > 0)
    if not vals:
        return math.inf
    med = vals[len(vals) // 2]
    return max(vals) / med if med > 0 else math.inf
