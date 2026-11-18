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


def contraste_efetivo(im: Image.Image, caixa, cor_texto, *, passo: int = 2, anel: int = 12, fundo=None) -> dict:
    """Contraste EFETIVO do texto na caixa, medido nos pixels que ocupam a área (não pela mediana do fundo).

    O fundo dominante é estimado no ANEL de ``anel`` px em volta da caixa (nunca dentro dela: em texto grande o glifo domina a caixa);
    ele e a cor do texto definem um eixo; pixels sobre esse eixo são texto/borda suavizada e saem da amostra; os demais pixels da área
    ampliada são FUNDO (inclusive qualquer variação forte, que reduz o contraste). O pior fundo é o mais claro (texto claro) ou o mais
    escuro (texto escuro), no percentil 99. Devolve ``{"razao", "fundo_pior", "amostras"}``.

    Com ``fundo`` (a cor da superfície controlada declarada pelo layout) não há anel: mede-se SÓ a caixa do texto, e tudo o que não for
    glifo (sobre o eixo fundo→texto) conta como fundo; qualquer pixel inesperado na caixa reduz o contraste medido."""
    rgb = im.convert("RGB")
    x0, y0, x1, y1 = (int(v) for v in caixa)
    if fundo is not None:
        anel = 0
    ex = (max(0, x0 - anel), max(0, y0 - anel), min(rgb.width, x1 + anel), min(rgb.height, y1 + anel))
    rec = rgb.crop(ex)
    if passo > 1:
        rec = rec.resize((max(1, rec.width // passo), max(1, rec.height // passo)), Image.NEAREST)
    w = rec.width
    px = list(zip(*[iter(rec.tobytes())] * 3))
    if not px:
        return {"razao": 0.0, "fundo_pior": None, "amostras": 0}
    if fundo is not None:
        b = tuple(fundo[:3])
    else:
        ix0, iy0 = (x0 - ex[0]) // passo, (y0 - ex[1]) // passo
        ix1, iy1 = -(-(x1 - ex[0]) // passo), -(-(y1 - ex[1]) // passo)
        cont: dict = {}
        for n, p in enumerate(px):
            xx, yy = n % w, n // w
            if ix0 <= xx < ix1 and iy0 <= yy < iy1:
                continue                                              # só o anel externo define o fundo
            k = (p[0] // 8, p[1] // 8, p[2] // 8)
            cont[k] = cont.get(k, 0) + 1
        if not cont:
            return {"razao": 0.0, "fundo_pior": None, "amostras": 0}
        modo = max(cont, key=cont.get)
        b = tuple(v * 8 + 4 for v in modo)
    f = tuple(cor_texto[:3])
    eixo = [f[i] - b[i] for i in range(3)]
    n2 = sum(e * e for e in eixo) or 1
    fundo = []
    for p in px:
        d = [p[i] - b[i] for i in range(3)]
        t = sum(d[i] * eixo[i] for i in range(3)) / n2
        perp = sum((d[i] - t * eixo[i]) ** 2 for i in range(3)) ** 0.5
        if perp < 36 and t > 0.12:                                   # sobre o eixo fundo→texto: glifo ou borda suavizada
            continue
        fundo.append(p)
    if not fundo:
        return {"razao": razao_contraste(f, b), "fundo_pior": b, "amostras": 0}
    lum = sorted(fundo, key=luminancia_relativa)
    claro = luminancia_relativa(f) > 0.5
    pior = lum[min(len(lum) - 1, int(len(lum) * 0.99))] if claro else lum[int(len(lum) * 0.01)]
    return {"razao": round(razao_contraste(f, pior), 2), "fundo_pior": tuple(pior), "amostras": len(fundo)}


def contraste_sobre_fundo(fundo_img: Image.Image, caixa, cor_texto) -> dict:
    """Contraste EXATO: razão entre a cor do texto e o PIOR pixel do fundo (render sem texto) dentro da caixa (percentil 99 do mais
    claro, para texto claro; do mais escuro, para texto escuro)."""
    x0, y0, x1, y1 = (int(v) for v in caixa)
    rec = fundo_img.convert("RGB").crop((max(0, x0), max(0, y0), min(fundo_img.width, x1), min(fundo_img.height, y1)))
    px = sorted(zip(*[iter(rec.tobytes())] * 3), key=luminancia_relativa)
    if not px:
        return {"razao": 0.0, "fundo_pior": None, "amostras": 0}
    claro = luminancia_relativa(cor_texto) > 0.5
    pior = px[min(len(px) - 1, int(len(px) * 0.99))] if claro else px[int(len(px) * 0.01)]
    return {"razao": round(razao_contraste(cor_texto, pior), 2), "fundo_pior": tuple(pior), "amostras": len(px)}


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


# ---------------------------------------------------------------------------------------------------------------------------------
# Validação dos layouts B2R (nova; ``validar_slide`` não mudou). Usa ``areas["v2"]`` devolvido pelos layouts novos.
# ---------------------------------------------------------------------------------------------------------------------------------
FONTE_MIN_POR_TIPO = {"titulo": idv.FONTE_TITULO_MIN, "texto": idv.FONTE_TEXTO_MIN, "botao": idv.FONTE_TEXTO_MIN,
                      "rotulo": idv.FONTE_ROTULO_MIN, "contador": idv.FONTE_CONTADOR_MIN, "destaque": 160}
AREA_DECORATIVA_MAX = 0.25


def _cx(c, p=4):
    return (c[0] + p, c[1] + p, c[2] - p, c[3] - p)


def validar_slide_v2(arquivo, areas: dict, *, contraste_min: float = idv.CONTRASTE_MIN, fundo_sem_texto=None) -> dict:
    """Verificações da B2R sobre o slide JÁ exportado: dimensões, margem de segurança de 72 px, tamanhos mínimos de fonte, contraste
    efetivo ≥ 4,5:1 em cada bloco de texto, ausência de sobreposição, logotipo de 160 px inteiro, rótulo "Arte ilustrativa" e área
    decorativa contígua ≤ 25 % do slide. Devolve ``{"ok", "erros", "medidas"}``.

    ``fundo_sem_texto``: o MESMO slide renderizado sem os textos (``layouts.sem_texto()``). Com ele o contraste é medido de forma EXATA, contra o
    pior pixel do fundo real em cada área de texto (sem heurística de separar glifo e fundo). Sem ele, usa-se ``contraste_efetivo`` (heurística)."""
    v2 = areas["v2"]
    erros: list[str] = []
    with Image.open(arquivo) as im0:
        im = im0.convert("RGB")
        formato = im0.format
    if im.size != (idv.W, idv.H):
        erros.append(f"dimensões {im.size}, esperado {(idv.W, idv.H)}")
    m = v2["margem"]
    seguro = (m, m, idv.W - m, idv.H - m)

    def dentro(c):
        return c[0] >= seguro[0] and c[1] >= seguro[1] and c[2] <= seguro[2] and c[3] <= seguro[3]

    fontes: dict[str, int] = {}
    contrastes = []
    for it in v2["itens"]:
        tipo, c = it["tipo"], _cx(it["caixa"])
        fontes[tipo] = min(fontes.get(tipo, 10 ** 6), it["tamanho"])
        if it["tamanho"] < FONTE_MIN_POR_TIPO[tipo]:
            erros.append(f"fonte de {it['tamanho']}px em '{tipo}' (mínimo {FONTE_MIN_POR_TIPO[tipo]}px)")
        if not dentro(c):
            erros.append(f"texto '{tipo}' fora da margem de segurança de {m}px: {tuple(it['caixa'])}")
        ce = (contraste_sobre_fundo(fundo_sem_texto, it["caixa"], it["cor"]) if fundo_sem_texto is not None
              else contraste_efetivo(im, it["caixa"], it["cor"], fundo=it.get("fundo")))
        contrastes.append(ce["razao"])
        if ce["razao"] < contraste_min:
            erros.append(f"contraste {ce['razao']}:1 em '{tipo}' abaixo de {contraste_min}:1")
    itens = [_cx(it["caixa"]) for it in v2["itens"]]
    for i in range(len(itens)):
        for j in range(i + 1, len(itens)):
            if _intersecta(itens[i], itens[j]):
                erros.append(f"textos sobrepostos: {v2['itens'][i]['tipo']} × {v2['itens'][j]['tipo']}")
    lg = v2["logo"]
    if (lg[2] - lg[0], lg[3] - lg[1]) != (v2["logo_lado"], v2["logo_lado"]) or v2["logo_lado"] < idv.LOGO_GRANDE:
        erros.append(f"logotipo {(lg[2] - lg[0], lg[3] - lg[1])} diferente de {idv.LOGO_GRANDE}px")
    if not dentro(lg):
        erros.append("logotipo cortado ou fora da margem de segurança")
    if any(_intersecta(lg, c) for c in itens):
        erros.append("texto encosta no logotipo")
    if not any(it["tipo"] == "rotulo" and it["texto"] == idv.ROTULO_ARTE for it in v2["itens"]):
        erros.append(f"rótulo \"{idv.ROTULO_ARTE}\" ausente")
    vazia = maior_area_vazia(v2["conteudo"], idv.W, idv.H, m)
    if vazia["fracao"] > AREA_DECORATIVA_MAX:
        erros.append(f"área decorativa contígua de {vazia['fracao']:.0%} do slide (máximo {AREA_DECORATIVA_MAX:.0%})")
    medidas = {"layout": v2["layout"], "formato": formato, "dimensoes": list(im.size), "fontes_min_px": dict(sorted(fontes.items())),
               "contraste_min": min(contrastes) if contrastes else None, "contraste_por_bloco": [round(c, 2) for c in contrastes],
               "maior_area_decorativa": vazia["fracao"], "logo_px": [lg[2] - lg[0], lg[3] - lg[1]], "blocos_de_texto": len(itens)}
    return {"ok": not erros, "erros": erros, "medidas": medidas}
