"""Primitivas de renderização Pillow reutilizadas pelos layouts."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from . import identidade as idv


def cobrir(foto: Image.Image, w: int, h: int, foco=(0.5, 0.5)) -> Image.Image:
    """Escala uniforme até cobrir w×h e recorta em torno do foco. Nunca deforma."""
    foto = foto.convert("RGB")
    escala = max(w / foto.width, h / foto.height)
    nw, nh = round(foto.width * escala), round(foto.height * escala)
    foto = foto.resize((max(nw, w), max(nh, h)), Image.LANCZOS)
    fx = min(max(float(foco[0]), 0.0), 1.0)
    fy = min(max(float(foco[1]), 0.0), 1.0)
    x = round((foto.width - w) * fx)
    y = round((foto.height - h) * fy)
    return foto.crop((x, y, x + w, y + h))


def degrade_vertical(w: int, h: int, cor, alfa_ini: int, alfa_fim: int, curva: float = 1.0) -> Image.Image:
    camada = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for y in range(h):
        t = (y / max(h - 1, 1)) ** curva
        d.line([(0, y), (w, y)], fill=tuple(cor) + (round(alfa_ini + (alfa_fim - alfa_ini) * t),))
    return camada


def texto_sombra(base: Image.Image, xy, texto: str, fnt, cor, sombra: int = 5) -> None:
    camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(camada).text((xy[0], xy[1] + sombra), texto, font=fnt, fill=(0, 10, 30, 170))
    base.alpha_composite(camada.filter(ImageFilter.GaussianBlur(max(2, sombra))))
    ImageDraw.Draw(base).text(xy, texto, font=fnt, fill=cor)


def _quebrar(tokens, fnt, largura):
    """tokens: [(palavra, cor)] -> linhas [[(palavra, cor)]] cabendo em `largura`."""
    linhas, atual = [], []
    esp = fnt.getlength(" ")
    larg_atual = 0.0
    for palavra, cor in tokens:
        lp = fnt.getlength(palavra)
        if atual and larg_atual + esp + lp > largura:
            linhas.append(atual)
            atual, larg_atual = [], 0.0
        if lp > largura:
            return None  # palavra sozinha não cabe neste tamanho
        larg_atual += (esp if atual else 0) + lp
        atual.append((palavra, cor))
    if atual:
        linhas.append(atual)
    return linhas


def _equilibrar(texto: str, fnt, largura: int) -> list[str]:
    """Quebra texto corrido evitando palavra órfã na última linha."""
    linhas = [" ".join(p for p, _ in ln) for ln in _quebrar([(p, None) for p in texto.split()], fnt, largura) or []]
    if len(linhas) == 2:
        palavras = texto.split()
        opcoes = []
        for i in range(1, len(palavras)):
            a, b = " ".join(palavras[:i]), " ".join(palavras[i:])
            m = max(fnt.getlength(a), fnt.getlength(b))
            if m <= largura:
                opcoes.append((m, [a, b]))
        if opcoes:
            linhas = min(opcoes)[1]
    return linhas


def medir_bloco(titulo, destaque, texto, largura, tam_titulo=96, tam_min=52, tam_texto=40, alt_max=10_000):
    """Escolhe o maior tamanho de título que caiba em largura × alt_max."""
    tokens = [(p, idv.BRANCO) for p in (titulo or "").split()] + \
             [(p, idv.AMARELO) for p in (destaque or "").split()]
    for tam in range(tam_titulo, tam_min - 1, -2):
        ft = idv.fonte("titulo", tam)
        linhas = _quebrar(tokens, ft, largura)
        if linhas is None or len(linhas) > 4:
            continue
        asc, desc = ft.getmetrics()
        alt_l = asc + desc - round(tam * 0.06)
        fx = idv.fonte("texto", tam_texto)
        linhas_txt = _equilibrar(texto, fx, largura) if texto else []
        alt_txt = round(tam_texto * 1.38)
        altura = 34 + len(linhas) * alt_l + (26 + len(linhas_txt) * alt_txt if linhas_txt else 0)
        if altura <= alt_max:
            return {"ft": ft, "linhas": linhas, "alt_l": alt_l, "fx": fx,
                    "linhas_txt": linhas_txt, "alt_txt": alt_txt, "altura": altura}
    raise ValueError(f"Texto não cabe no layout: '{titulo} {destaque}'. Encurte o título.")


def desenhar_bloco(base: Image.Image, x: int, y: int, m: dict) -> tuple[int, int, int, int]:
    """Desenha faixa vermelha + título bicolor + texto. Retorna a caixa ocupada."""
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((x, y, x + 110, y + 12), radius=6, fill=idv.VERMELHO + (255,))
    yy = y + 34
    esp = m["ft"].getlength(" ")
    larg_max = 0
    for ln in m["linhas"]:
        xx = x
        for palavra, cor in ln:
            texto_sombra(base, (xx, yy), palavra, m["ft"], cor)
            xx += m["ft"].getlength(palavra) + esp
        larg_max = max(larg_max, xx - esp - x)
        yy += m["alt_l"]
    if m["linhas_txt"]:
        yy += 26
        for ln in m["linhas_txt"]:
            texto_sombra(base, (x, yy), ln, m["fx"], idv.TEXTO_SUAVE, sombra=3)
            larg_max = max(larg_max, m["fx"].getlength(ln))
            yy += m["alt_txt"]
    return (x, y, round(x + larg_max), yy)


def rodape(base: Image.Image, numero: int | None, total: int | None, *, grande: bool = False) -> tuple[int, int, int, int]:
    """Logo discreto no canto inferior direito + indicador de página. Retorna a caixa do logo.

    ``grande=False`` (padrão): comportamento de sempre. ``grande=True`` (estilo B2R): logotipo de 160 px INTEIRO, dentro da margem
    de segurança de 72 px, e contador de páginas de 40 px."""
    if grande:
        lado, m = idv.LOGO_GRANDE, idv.MARGEM_SEGURANCA
        logo = idv.logo_marca_dagua(lado, 1.0)
        lx, ly = idv.W - m - logo.width, idv.H - m - logo.height
        base.alpha_composite(logo, (lx, ly))
        if numero and total and total > 1:
            f = idv.fonte("rotulo", idv.CONTADOR_GRANDE)
            ImageDraw.Draw(base).text((m, ly + logo.height // 2), f"{numero}/{total}", font=f, fill=(255, 255, 255, 235), anchor="lm")
        return (lx, ly, lx + logo.width, ly + logo.height)
    logo = idv.logo_marca_dagua()
    lx = idv.W - idv.MARGEM - logo.width + 10
    ly = idv.H - 44 - logo.height
    base.alpha_composite(logo, (lx, ly))
    if numero and total and total > 1:
        f = idv.fonte("rotulo", 26)
        ImageDraw.Draw(base).text((idv.MARGEM, ly + logo.height // 2), f"{numero}/{total}",
                                  font=f, fill=(255, 255, 255, 190), anchor="lm")
    return (lx, ly, lx + logo.width, ly + logo.height)
