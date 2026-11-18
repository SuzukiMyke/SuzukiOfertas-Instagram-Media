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


# ---------------------------------------------------------------------------------------------------------------------------------
# Helpers da B2R (novos; ``validar_slide`` acima não mudou): contraste efetivo e área decorativa.
# ---------------------------------------------------------------------------------------------------------------------------------
def _linear(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminancia_relativa(rgb) -> float:
    """Luminância relativa WCAG (0 a 1) de uma cor RGB."""
    r, g, b = (_linear(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razao_contraste(a, b) -> float:
    """Razão de contraste WCAG entre duas cores (1 a 21)."""
    la, lb = luminancia_relativa(a), luminancia_relativa(b)
    claro, escuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (escuro + 0.05)


def contraste_efetivo(im: Image.Image, caixa, cor_texto, *, passo: int = 2) -> dict:
    """Contraste EFETIVO do texto na caixa, medido nos pixels que ocupam a área (não pela mediana do fundo).

    O fundo dominante (cor mais frequente da caixa) e a cor do texto definem um eixo; pixels sobre esse eixo são texto/borda
    suavizada e saem da amostra; os demais pixels são FUNDO (inclusive qualquer variação forte, que reduz o contraste). O pior
    fundo é o mais claro (texto claro) ou o mais escuro (texto escuro), no percentil 99. Devolve ``{"razao", "fundo_pior", "amostras"}``."""
    x0, y0, x1, y1 = (int(v) for v in caixa)
    rec = im.convert("RGB").crop((x0, y0, x1, y1))
    if passo > 1:
        rec = rec.resize((max(1, rec.width // passo), max(1, rec.height // passo)), Image.NEAREST)
    px = list(zip(*[iter(rec.tobytes())] * 3))
    if not px:
        return {"razao": 0.0, "fundo_pior": None, "amostras": 0}
    cont: dict = {}
    for p in px:
        k = (p[0] // 8, p[1] // 8, p[2] // 8)
        cont[k] = cont.get(k, 0) + 1
    modo = max(cont, key=cont.get)
    b = tuple(v * 8 + 4 for v in modo)
    f = tuple(cor_texto[:3])
    ex = [f[i] - b[i] for i in range(3)]
    n2 = sum(e * e for e in ex) or 1
    fundo = []
    for p in px:
        d = [p[i] - b[i] for i in range(3)]
        t = sum(d[i] * ex[i] for i in range(3)) / n2
        perp = sum((d[i] - t * ex[i]) ** 2 for i in range(3)) ** 0.5
        if perp < 36 and t > 0.12:                                   # sobre o eixo fundo→texto: glifo ou borda suavizada
            continue
        fundo.append(p)
    if not fundo:
        return {"razao": razao_contraste(f, b), "fundo_pior": b, "amostras": 0}
    lum = sorted(fundo, key=luminancia_relativa)
    claro = luminancia_relativa(f) > 0.5
    pior = lum[min(len(lum) - 1, int(len(lum) * 0.99))] if claro else lum[int(len(lum) * 0.01)]
    return {"razao": round(razao_contraste(f, pior), 2), "fundo_pior": tuple(pior), "amostras": len(fundo)}


def maior_area_vazia(caixas, largura: int, altura: int, margem: int, celula: int = 18) -> dict:
    """Maior retângulo livre (sem nenhuma caixa de conteúdo) dentro da área segura. ``{"px", "fracao", "caixa"}`` (fração do slide)."""
    x0, y0, x1, y1 = margem, margem, largura - margem, altura - margem
    cols, lins = (x1 - x0) // celula, (y1 - y0) // celula
    livre = [[True] * cols for _ in range(lins)]
    for (a, b, c, d) in caixas:
        for j in range(lins):
            cy0, cy1 = y0 + j * celula, y0 + (j + 1) * celula
            if cy1 <= b or cy0 >= d:
                continue
            for i in range(cols):
                cx0, cx1 = x0 + i * celula, x0 + (i + 1) * celula
                if cx1 > a and cx0 < c:
                    livre[j][i] = False
    melhor, onde, alt = 0, None, [0] * cols
    for j in range(lins):
        for i in range(cols):
            alt[i] = alt[i] + 1 if livre[j][i] else 0
        pilha = []
        for i in range(cols + 1):
            h = alt[i] if i < cols else 0
            ini = i
            while pilha and pilha[-1][1] >= h:
                pos, hh = pilha.pop()
                area = hh * (i - pos)
                if area > melhor:
                    melhor, onde = area, (pos, j - hh + 1, i, j + 1)
                ini = pos
            pilha.append((ini, h))
    px = melhor * celula * celula
    caixa = None if onde is None else (x0 + onde[0] * celula, y0 + onde[1] * celula, x0 + onde[2] * celula, y0 + onde[3] * celula)
    return {"px": px, "fracao": round(px / (largura * altura), 4), "caixa": caixa}
