"""Ilustrações gráficas determinísticas por categoria (B2R). Só Pillow, offline, sem dependências novas, sem fotografias.

Seis categorias: ``tecnologia``, ``casa_cozinha``, ``ferramentas``, ``moda_beleza``, ``utilidades`` e ``generica`` (categoria desconhecida
usa ``generica``). São desenhos estilizados em formas simples e nas cores da marca (azul-marinho, azul, amarelo e vermelho); não imitam
marcas nem modelos e não têm texto. Entram no catálogo TEMPORÁRIO como ``composicao-grafica``, PENDENTES de aprovação humana, e os slides
que as usam trazem o rótulo "Arte ilustrativa". A mesma categoria e ``variante`` geram os mesmos bytes (mesma versão do Pillow/libjpeg).
"""
from __future__ import annotations

import hashlib
import io
import math
import random
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from gerador import identidade as idv
from gerador.catalogo import ORIGEM_COMPOSICAO_GRAFICA, Catalogo, agora_utc

LARGURA, ALTURA = 1080, 776                      # proporção da área de ilustração do layout ilustracao_capa (936×672)
CATEGORIAS = ("tecnologia", "casa_cozinha", "ferramentas", "moda_beleza", "utilidades", "generica")
VARIANTES = 4
VERSAO = "1.0"
PROVEDOR = "composicao-grafica"
QUALIDADE_JPEG = 95
BRANCO_SUAVE = (240, 244, 252)
CINZA_CLARO = (205, 214, 232)
CINZA_MEDIO = (150, 165, 195)
AZUL_CLARO = (120, 170, 255)
RESTRICOES = ["Ilustração gráfica: não representa produto algum", "Sem fotografias, textos ou marcas de produtos",
              "Rotular como \"Arte ilustrativa\" quando usada com produto", "Aprovação visual humana obrigatória"]

_PALAVRAS = {
    "tecnologia": ("tecnolog", "eletron", "fone", "audio", "celular", "informat", "computador", "bluetooth", "gadget", "smart"),
    "casa_cozinha": ("casa", "cozinha", "panela", "utensil", "eletrodomest", "mesa", "talher", "decorac"),
    "ferramentas": ("ferrament", "furadeira", "constru", "parafus", "reforma", "oficina", "bricolagem"),
    "moda_beleza": ("moda", "beleza", "roupa", "vestu", "cosmet", "perfum", "maquiag", "calcad", "acessorio"),
    "utilidades": ("utilidad", "limpeza", "organiz", "lampada", "pilha", "bateria", "tomada", "eletric"),
}


def _sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode("ascii").lower()


def normalizar_categoria(categoria) -> str:
    """Categoria conhecida ou ``generica``."""
    return categoria if categoria in CATEGORIAS else "generica"


def categoria_de(categoria_ficha: str | None, titulo: str | None = None) -> str:
    """Deduz a categoria de ilustração a partir da categoria (e, se preciso, do título) da ficha; desconhecida = ``generica``."""
    for texto in (categoria_ficha, titulo):
        n = _sem_acento(texto or "")
        for cat, palavras in _PALAVRAS.items():
            if any(p in n for p in palavras):
                return cat
    return "generica"


# ------------------------------------------------------------------ primitivas
def _fundo(cat: str, variante: int) -> Image.Image:
    ang = {"tecnologia": 20, "casa_cozinha": 150, "ferramentas": 200, "moda_beleza": 100, "utilidades": 60, "generica": 330}[cat] + variante * 17
    lado = 2 * math.ceil(math.hypot(LARGURA, ALTURA))
    masc = Image.linear_gradient("L").resize((lado, lado), Image.BILINEAR).rotate(ang, resample=Image.BILINEAR)
    ex, ey = (lado - LARGURA) // 2, (lado - ALTURA) // 2
    masc = masc.crop((ex, ey, ex + LARGURA, ey + ALTURA))
    return Image.composite(Image.new("RGB", (LARGURA, ALTURA), idv.AZUL_VIBRANTE), Image.new("RGB", (LARGURA, ALTURA), idv.AZUL_ESCURO), masc)


def _camada() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    c = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
    return c, ImageDraw.Draw(c)


def _compor(base: Image.Image, camada: Image.Image, desfoque: float = 0) -> None:
    base.alpha_composite(camada.filter(ImageFilter.GaussianBlur(desfoque)) if desfoque else camada)


def _sombra(base: Image.Image, formas, desloc=(14, 22)) -> None:
    c, d = _camada()
    formas(d, desloc)
    _compor(base, c, 14)


def _halo(base: Image.Image, cx: int, cy: int, r: int, cor=idv.AMARELO, alfa=70) -> None:
    c, d = _camada()
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=cor + (alfa,))
    _compor(base, c, 60)


def _fundo_padrao(base: Image.Image, cat: str, variante: int) -> None:
    """Círculos e anéis translúcidos e pontos: dão profundidade (determinísticos por categoria e variante)."""
    rnd = random.Random(7919 * (CATEGORIAS.index(cat) + 1) + 31 * variante)
    c, d = _camada()
    for _ in range(4):
        r = rnd.randint(110, 300)
        x, y = rnd.randint(0, LARGURA), rnd.randint(0, ALTURA)
        d.ellipse((x - r, y - r, x + r, y + r), outline=idv.AMARELO + (rnd.randint(60, 110),), width=rnd.randint(6, 14))
    for _ in range(3):
        r = rnd.randint(120, 260)
        x, y = rnd.randint(0, LARGURA), rnd.randint(0, ALTURA)
        d.ellipse((x - r, y - r, x + r, y + r), fill=idv.BRANCO + (rnd.randint(14, 30),))
    for yy in range(34, ALTURA, 78):
        for xx in range(34 + (yy // 78 % 2) * 39, LARGURA, 78):
            d.ellipse((xx - 5, yy - 5, xx + 5, yy + 5), fill=idv.BRANCO + (46,))
    _compor(base, c)


def _faisca(d: ImageDraw.ImageDraw, x: int, y: int, r: int, cor=idv.AMARELO) -> None:
    d.polygon([(x, y - r), (x + r // 4, y - r // 4), (x + r, y), (x + r // 4, y + r // 4), (x, y + r), (x - r // 4, y + r // 4),
               (x - r, y), (x - r // 4, y - r // 4)], fill=cor + (255,))


def _girar(base: Image.Image, desenho, centro, angulo: float) -> None:
    c, d = _camada()
    desenho(d)
    c = c.rotate(angulo, resample=Image.BICUBIC, center=centro)
    base.alpha_composite(c)


# ------------------------------------------------------------------ categorias
def _tecnologia(base: Image.Image, v: int) -> None:
    cx, cy = 560, 410
    _halo(base, cx, cy, 330)
    def case(d, o=(0, 0)):
        ox, oy = o
        d.rounded_rectangle((cx - 120 + ox, cy - 20 + oy, cx + 300 + ox, cy + 250 + oy), radius=70, fill=BRANCO_SUAVE + (255,) if o == (0, 0) else (0, 8, 30, 255))
    _sombra(base, case)
    c, d = _camada()
    d.rounded_rectangle((cx - 120, cy - 20, cx + 300, cy + 250), radius=70, fill=BRANCO_SUAVE + (255,))
    d.rounded_rectangle((cx - 120, cy - 20, cx + 300, cy + 80), radius=70, fill=CINZA_CLARO + (255,))
    d.line((cx - 112, cy + 80, cx + 292, cy + 80), fill=CINZA_MEDIO + (255,), width=6)
    d.ellipse((cx + 70, cy + 150, cx + 110, cy + 190), fill=idv.AMARELO + (255,))
    d.rounded_rectangle((cx + 130, cy + 166, cx + 230, cy + 176), radius=5, fill=CINZA_MEDIO + (255,))
    _compor(base, c)
    for k, (ex, ey, ang) in enumerate(((cx - 230, cy - 140, 22), (cx - 20, cy - 175, -22))):
        def fone(d, ex=ex, ey=ey):
            d.rounded_rectangle((ex + 58, ey + 70, ex + 100, ey + 250), radius=21, fill=BRANCO_SUAVE + (255,))
            d.ellipse((ex, ey, ex + 150, ey + 150), fill=BRANCO_SUAVE + (255,))
            d.ellipse((ex + 36, ey + 36, ex + 114, ey + 114), fill=idv.AZUL_VIBRANTE + (255,))
            d.ellipse((ex + 56, ey + 56, ex + 94, ey + 94), fill=idv.AMARELO + (255,))
        _girar(base, fone, (ex + 75, ey + 75), ang)
    c, d = _camada()
    for i, r in enumerate((90, 150, 210)):                       # ondas de som
        d.arc((cx - 430 - r, cy + 20 - r, cx - 430 + r, cy + 20 + r), 300, 60, fill=idv.AMARELO + (255 - 60 * i,), width=14)
    for i in range(5):                                           # linhas de circuito
        y = 90 + i * 70
        d.line((780, y, 900 + (i % 2) * 60, y, 900 + (i % 2) * 60, y + 36), fill=idv.BRANCO + (120,), width=5)
        d.ellipse((894 + (i % 2) * 60, y + 30, 912 + (i % 2) * 60, y + 48), fill=idv.AMARELO + (230,))
    _faisca(d, 180, 150, 38)
    _faisca(d, 900, 640, 28, idv.BRANCO)
    _compor(base, c)


def _casa_cozinha(base: Image.Image, v: int) -> None:
    cx, cy = 540, 440
    _halo(base, cx, cy, 340, idv.BRANCO, 55)
    c, d = _camada()
    for gx in range(0, LARGURA, 108):                            # azulejos
        for gy in range(0, ALTURA, 108):
            d.rectangle((gx + 4, gy + 4, gx + 104, gy + 104), outline=idv.BRANCO + (34,), width=3)
    _compor(base, c)
    def corpo(d, o=(0, 0)):
        ox, oy = o
        cor = BRANCO_SUAVE + (255,) if o == (0, 0) else (0, 8, 30, 255)
        d.rounded_rectangle((cx - 220 + ox, cy - 10 + oy, cx + 220 + ox, cy + 260 + oy), radius=60, fill=cor)
        d.pieslice((cx - 220 + ox, cy - 130 + oy, cx + 220 + ox, cy + 90 + oy), 180, 360, fill=cor)
    _sombra(base, corpo)
    c, d = _camada()
    corpo(d)
    d.rounded_rectangle((cx - 220, cy + 60, cx + 220, cy + 96), radius=18, fill=CINZA_CLARO + (255,))
    d.rounded_rectangle((cx - 40, cy - 168, cx + 40, cy - 118), radius=22, fill=idv.VERMELHO + (255,))      # botão da tampa
    d.rounded_rectangle((cx - 320, cy + 50, cx - 215, cy + 100), radius=24, fill=idv.VERMELHO + (255,))      # alças
    d.rounded_rectangle((cx + 215, cy + 50, cx + 320, cy + 100), radius=24, fill=idv.VERMELHO + (255,))
    d.ellipse((cx + 130, cy - 70, cx + 180, cy - 20), fill=idv.AMARELO + (255,))                              # válvula
    for i, ox in enumerate((-110, 0, 110)):                       # vapor
        pts = [(cx + ox + 22 * math.sin(t / 14 + i), cy - 230 - t) for t in range(0, 150, 6)]
        d.line(pts, fill=idv.BRANCO + (190,), width=14, joint="curve")
    _compor(base, c)
    c, d = _camada()
    d.ellipse((90, 520, 190, 600), fill=CINZA_CLARO + (255,))                                                # colher
    d.rounded_rectangle((132, 590, 148, 740), radius=8, fill=CINZA_CLARO + (255,))
    d.rectangle((870, 560, 886, 740), fill=CINZA_CLARO + (255,))                                             # espátula
    d.rounded_rectangle((830, 500, 926, 580), radius=14, fill=CINZA_CLARO + (255,))
    _faisca(d, 170, 130, 34)
    _faisca(d, 930, 150, 26, idv.BRANCO)
    _compor(base, c)


def _ferramentas(base: Image.Image, v: int) -> None:
    cx, cy = 540, 400
    _halo(base, cx, cy, 330)
    c, d = _camada()
    for k in range(3):                                           # engrenagens ao fundo
        gx, gy, gr = (170, 590, 120) if k == 0 else ((910, 170, 95) if k == 1 else (930, 640, 70))
        for i in range(12):
            a = math.radians(i * 30)
            d.polygon([(gx + (gr - 6) * math.cos(a - .12), gy + (gr - 6) * math.sin(a - .12)), (gx + (gr + 24) * math.cos(a - .07), gy + (gr + 24) * math.sin(a - .07)),
                       (gx + (gr + 24) * math.cos(a + .07), gy + (gr + 24) * math.sin(a + .07)), (gx + (gr - 6) * math.cos(a + .12), gy + (gr - 6) * math.sin(a + .12))],
                      fill=idv.BRANCO + (70,))
        d.ellipse((gx - gr, gy - gr, gx + gr, gy + gr), fill=idv.BRANCO + (70,))
        d.ellipse((gx - gr // 2, gy - gr // 2, gx + gr // 2, gy + gr // 2), fill=idv.AZUL_ESCURO + (200,))
    _compor(base, c)
    def furadeira(d, o=(0, 0)):
        ox, oy = o
        cor = idv.AMARELO + (255,) if o == (0, 0) else (0, 8, 30, 255)
        d.rounded_rectangle((cx - 280 + ox, cy - 110 + oy, cx + 150 + ox, cy + 40 + oy), radius=50, fill=cor)         # corpo
        d.polygon([(cx - 120 + ox, cy + 30 + oy), (cx + 10 + ox, cy + 30 + oy), (cx + 60 + ox, cy + 270 + oy), (cx - 110 + ox, cy + 270 + oy)], fill=cor)  # cabo
    _sombra(base, furadeira)
    c, d = _camada()
    furadeira(d)
    d.rounded_rectangle((cx - 110, cy + 200, cx + 55, cy + 270), radius=20, fill=idv.AZUL_ESCURO + (255,))       # base da bateria
    d.rounded_rectangle((cx - 280, cy - 70, cx - 120, cy - 10), radius=14, fill=idv.AZUL_ESCURO + (255,))
    d.ellipse((cx - 250, cy - 58, cx - 226, cy - 34), fill=idv.VERMELHO + (255,))
    d.rounded_rectangle((cx - 50, cy + 40, cx + 10, cy + 120), radius=18, fill=idv.VERMELHO + (255,))             # gatilho
    d.rounded_rectangle((cx + 150, cy - 80, cx + 250, cy + 10), radius=18, fill=CINZA_CLARO + (255,))            # mandril
    d.rectangle((cx + 250, cy - 40, cx + 420, cy - 20), fill=CINZA_MEDIO + (255,))                                # broca
    for i in range(7):
        d.line((cx + 262 + i * 22, cy - 40, cx + 282 + i * 22, cy - 20), fill=BRANCO_SUAVE + (255,), width=5)
    d.polygon([(cx + 420, cy - 40), (cx + 470, cy - 30), (cx + 420, cy - 20)], fill=CINZA_MEDIO + (255,))
    _compor(base, c)
    c, d = _camada()
    for hx, hy in ((220, 130), (820, 560)):                       # porcas sextavadas
        d.polygon([(hx + 60 * math.cos(math.radians(a)), hy + 60 * math.sin(math.radians(a))) for a in range(0, 360, 60)], fill=CINZA_CLARO + (255,))
        d.ellipse((hx - 24, hy - 24, hx + 24, hy + 24), fill=idv.AZUL_ESCURO + (255,))
    _faisca(d, 330, 640, 30)
    _compor(base, c)


def _moda_beleza(base: Image.Image, v: int) -> None:
    cx, cy = 480, 400
    _halo(base, cx, cy, 320, idv.VERMELHO, 55)
    def vestido(d, o=(0, 0)):
        ox, oy = o
        cor = idv.VERMELHO + (255,) if o == (0, 0) else (0, 8, 30, 255)
        d.polygon([(cx - 70 + ox, cy - 60 + oy), (cx + 70 + ox, cy - 60 + oy), (cx + 100 + ox, cy + 40 + oy), (cx + 250 + ox, cy + 300 + oy),
                   (cx - 250 + ox, cy + 300 + oy), (cx - 100 + ox, cy + 40 + oy)], fill=cor)
    _sombra(base, vestido)
    c, d = _camada()
    vestido(d)
    d.polygon([(cx - 100, cy + 40), (cx + 100, cy + 40), (cx + 120, cy + 90), (cx - 120, cy + 90)], fill=idv.AMARELO + (255,))    # cinto
    d.polygon([(cx - 70, cy - 60), (cx - 20, cy - 60), (cx, cy - 10)], fill=BRANCO_SUAVE + (255,))
    d.polygon([(cx + 70, cy - 60), (cx + 20, cy - 60), (cx, cy - 10)], fill=BRANCO_SUAVE + (255,))
    d.arc((cx - 80, cy - 190, cx + 80, cy - 50), 200, 340, fill=BRANCO_SUAVE + (255,), width=12)                                # cabide
    d.line((cx, cy - 120, cx, cy - 190), fill=BRANCO_SUAVE + (255,), width=12)
    d.arc((cx - 28, cy - 232, cx + 28, cy - 176), 90, 360, fill=BRANCO_SUAVE + (255,), width=12)
    _compor(base, c)
    c, d = _camada()
    d.rounded_rectangle((760, 400, 840, 620), radius=14, fill=BRANCO_SUAVE + (255,))                                            # batom
    d.rounded_rectangle((768, 300, 832, 410), radius=10, fill=idv.AMARELO + (255,))
    d.polygon([(768, 300), (832, 300), (808, 230), (792, 230)], fill=idv.VERMELHO + (255,))
    d.ellipse((140, 150, 330, 340), fill=CINZA_CLARO + (255,))                                                                   # espelho
    d.ellipse((160, 170, 310, 320), fill=AZUL_CLARO + (255,))
    d.rounded_rectangle((226, 335, 244, 470), radius=9, fill=CINZA_CLARO + (255,))
    _faisca(d, 740, 150, 40)
    _faisca(d, 220, 600, 30, idv.BRANCO)
    _faisca(d, 900, 690, 26)
    _compor(base, c)


def _utilidades(base: Image.Image, v: int) -> None:
    cx, cy = 500, 360
    _halo(base, cx, cy, 340, idv.AMARELO, 90)
    c, d = _camada()
    for i in range(12):                                           # raios
        a = math.radians(i * 30 + 15)
        d.line((cx + 200 * math.cos(a), cy + 200 * math.sin(a), cx + 280 * math.cos(a), cy + 280 * math.sin(a)), fill=idv.AMARELO + (255,), width=14)
    _compor(base, c)
    def lampada(d, o=(0, 0)):
        ox, oy = o
        cor = idv.AMARELO + (255,) if o == (0, 0) else (0, 8, 30, 255)
        d.ellipse((cx - 150 + ox, cy - 150 + oy, cx + 150 + ox, cy + 150 + oy), fill=cor)
        d.polygon([(cx - 90 + ox, cy + 100 + oy), (cx + 90 + ox, cy + 100 + oy), (cx + 60 + ox, cy + 200 + oy), (cx - 60 + ox, cy + 200 + oy)], fill=cor)
    _sombra(base, lampada)
    c, d = _camada()
    lampada(d)
    d.ellipse((cx - 110, cy - 110, cx + 110, cy + 110), fill=(255, 226, 120, 255))
    for i, y in enumerate((cy + 205, cy + 235, cy + 265)):        # rosca
        d.rounded_rectangle((cx - 70 + i * 6, y - 8, cx + 70 - i * 6, y + 14), radius=8, fill=CINZA_CLARO + (255,))
    d.line((cx - 32, cy + 96, cx - 32, cy + 10), fill=idv.AZUL_ESCURO + (255,), width=10)                                   # filamento
    d.line((cx + 32, cy + 96, cx + 32, cy + 10), fill=idv.AZUL_ESCURO + (255,), width=10)
    d.arc((cx - 32, cy - 40, cx + 32, cy + 24), 180, 360, fill=idv.AZUL_ESCURO + (255,), width=10)
    _compor(base, c)
    c, d = _camada()
    for k, (bx, by) in enumerate(((120, 520), (250, 556))):       # pilhas
        d.rounded_rectangle((bx, by, bx + 100, by + 190), radius=16, fill=idv.AZUL_ESCURO + (255,), outline=BRANCO_SUAVE + (255,), width=6)
        d.rounded_rectangle((bx + 30, by - 18, bx + 70, by + 4), radius=6, fill=BRANCO_SUAVE + (255,))
        d.rectangle((bx + 14, by + 100, bx + 86, by + 150), fill=idv.AMARELO + (255,))
    d.rounded_rectangle((800, 470, 940, 620), radius=24, fill=BRANCO_SUAVE + (255,))                                              # plugue
    d.rectangle((830, 410, 846, 475), fill=CINZA_CLARO + (255,))
    d.rectangle((894, 410, 910, 475), fill=CINZA_CLARO + (255,))
    d.line((870, 620, 870, 720, 760, 720), fill=BRANCO_SUAVE + (255,), width=14)
    _faisca(d, 840, 200, 36)
    _faisca(d, 130, 220, 28, idv.BRANCO)
    _compor(base, c)


def _generica(base: Image.Image, v: int) -> None:
    cx, cy = 540, 420
    _halo(base, cx, cy, 340)
    def sacola(d, o=(0, 0)):
        ox, oy = o
        cor = idv.AMARELO + (255,) if o == (0, 0) else (0, 8, 30, 255)
        d.polygon([(cx - 210 + ox, cy - 90 + oy), (cx + 210 + ox, cy - 90 + oy), (cx + 250 + ox, cy + 270 + oy), (cx - 250 + ox, cy + 270 + oy)], fill=cor)
    _sombra(base, sacola)
    c, d = _camada()
    sacola(d)
    d.arc((cx - 120, cy - 230, cx + 120, cy + 10), 180, 360, fill=BRANCO_SUAVE + (255,), width=22)
    d.ellipse((cx - 130, cy - 104, cx - 100, cy - 74), fill=idv.AZUL_ESCURO + (255,))
    d.ellipse((cx + 100, cy - 104, cx + 130, cy - 74), fill=idv.AZUL_ESCURO + (255,))
    _faisca(d, cx, cy + 90, 100, idv.VERMELHO)
    _compor(base, c)
    c, d = _camada()
    d.polygon([(130, 520), (260, 520), (300, 580), (260, 640), (130, 640)], fill=BRANCO_SUAVE + (255,))                           # etiqueta
    d.ellipse((150, 566, 178, 594), fill=idv.AZUL_ESCURO + (255,))
    d.rounded_rectangle((820, 470, 960, 610), radius=18, fill=idv.VERMELHO + (255,))                                              # presente
    d.rectangle((880, 470, 900, 610), fill=idv.AMARELO + (255,))
    d.rectangle((820, 528, 960, 548), fill=idv.AMARELO + (255,))
    _faisca(d, 220, 160, 42)
    _faisca(d, 880, 170, 30, idv.BRANCO)
    _faisca(d, 140, 720, 26)
    _compor(base, c)


_DESENHOS = {"tecnologia": _tecnologia, "casa_cozinha": _casa_cozinha, "ferramentas": _ferramentas, "moda_beleza": _moda_beleza,
             "utilidades": _utilidades, "generica": _generica}


def desenhar(categoria, variante: int = 0) -> Image.Image:
    """Ilustração RGB 1080×776 da categoria (desconhecida = ``generica``), determinística para a ``variante`` (0 a 3)."""
    if isinstance(variante, bool) or not isinstance(variante, int) or not 0 <= variante < VARIANTES:
        raise ValueError(f"variante deve ser um inteiro de 0 a {VARIANTES - 1}")
    cat = normalizar_categoria(categoria)
    base = _fundo(cat, variante).convert("RGBA")
    _fundo_padrao(base, cat, variante)
    _DESENHOS[cat](base, variante)
    return base.convert("RGB")


def ilustracao_bytes(categoria, variante: int = 0) -> bytes:
    buf = io.BytesIO()
    desenhar(categoria, variante).save(buf, "JPEG", quality=QUALIDADE_JPEG, subsampling=0, optimize=False, progressive=False)
    return buf.getvalue()


def sha256_ilustracao(categoria, variante: int = 0) -> str:
    return hashlib.sha256(ilustracao_bytes(categoria, variante)).hexdigest()


def registrar_ilustracao(catalogo: Catalogo, categoria, variante: int = 0, agora: str | None = None) -> tuple[str, bool]:
    """Grava a ilustração em ``<raiz do catálogo>/photos/cg-NNNN.jpg`` e a registra como ``composicao-grafica`` PENDENTE. ``(id, nova)``.

    O catálogo é obrigatório (nunca o do repositório por padrão); mesmo conteúdo (SHA-256) não é registrado duas vezes."""
    cat = normalizar_categoria(categoria)
    dados = ilustracao_bytes(cat, variante)
    sha = hashlib.sha256(dados).hexdigest()
    existente = catalogo.por_hash(sha)
    if existente:
        return existente, False
    foto_id = catalogo.proximo_id(PROVEDOR)
    rel = f"photos/{foto_id}.jpg"
    destino = Path(catalogo.raiz) / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    catalogo.adicionar(foto_id, {
        "id": foto_id, "provedor": PROVEDOR, "nome_arquivo_original": f"ilustracao_{cat}_v{variante:02d}.jpg",
        "sha256_original": sha, "sha256": sha, "largura": LARGURA, "altura": ALTURA, "formato_original": "JPEG",
        "data": agora or agora_utc(), "tipo_data": "geracao", "origem": ORIGEM_COMPOSICAO_GRAFICA,
        "descricao": f"Ilustração gráfica da categoria {cat} (variante {variante})", "prompt": None,
        "gerador": {"modulo": "orquestrador_b2.ilustracoes", "versao": VERSAO, "categoria": cat, "variante": variante},
        "restricoes_uso": list(RESTRICOES), "caminho_github": rel, "caminho_original": rel,
    })
    catalogo.salvar()
    return foto_id, True
