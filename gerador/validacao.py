"""Validações automáticas de cada slide exportado."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageStat

from . import identidade as idv

DESVIO_MINIMO_FOTO = 12.0  # abaixo disso a "foto" é praticamente um fundo liso


def _intersecta(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _dentro(caixa, x0, y0, x1, y1) -> bool:
    return caixa[0] >= x0 and caixa[1] >= y0 and caixa[2] <= x1 and caixa[3] <= y1


def validar_slide(arquivo: Path, areas: dict) -> list[str]:
    """Retorna lista de problemas (vazia = aprovado)."""
    erros = []
    with Image.open(arquivo) as im:
        if im.format != "JPEG":
            erros.append(f"formato {im.format}, esperado JPEG")
        if im.size != (idv.W, idv.H):
            erros.append(f"dimensões {im.size}, esperado {(idv.W, idv.H)}")
        if im.mode != "RGB":
            erros.append(f"modo {im.mode}, esperado RGB")
        fl = areas["foto_livre"]
        if (fl[3] - fl[1]) < 300:
            erros.append("área de foto visível menor que 300 px de altura")
        desvio = max(ImageStat.Stat(im.crop(fl).convert("L")).stddev[0], 0)
        if desvio < DESVIO_MINIMO_FOTO:
            erros.append(f"foto não aparece (desvio {desvio:.1f} na área da foto)")
    m = idv.MARGEM - 8
    for nome in ("texto", "texto_total"):
        if nome in areas and not _dentro(areas[nome], m, m, idv.W - m, idv.H - m):
            erros.append(f"{nome} fora da margem de segurança: {areas[nome]}")
    if _intersecta(areas["texto"], areas["foto_livre"]):
        erros.append("título cobre a área principal da foto")
    if _intersecta(areas.get("texto_total", areas["texto"]), areas["logo"]):
        erros.append("texto encosta no logotipo")
    lg = areas["logo"]
    if (lg[2] - lg[0]) > 0.16 * idv.W:
        erros.append("logotipo grande demais para marca-d'água")
    return erros
