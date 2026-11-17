"""Layouts de slide (1080×1350). Cada layout devolve a imagem e as áreas usadas
na validação: `foto_livre` (onde a foto deve aparecer sem texto por cima),
`texto` (caixa ocupada pelo texto) e `logo`.

Layouts disponíveis:
- foto_topo  : foto na metade superior, degradê para azul, texto embaixo.
- foto_cheia : foto em tela cheia, véu azul na base, texto sobre o véu.
- cartao     : fundo azul, título no topo, foto em cartão arredondado, texto abaixo.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from . import identidade as idv
from . import render as r

W, H, M = idv.W, idv.H, idv.MARGEM
LARG = W - 2 * M
RODAPE_Y = H - 44 - idv.LOGO_LADO - 24  # texto não pode descer além disso


def foto_topo(foto, s, numero=None, total=None):
    alt_foto, fade = 860, 560
    base = Image.new("RGBA", (W, H), idv.AZUL_ESCURO + (255,))
    camada = r.cobrir(foto, W, alt_foto, s.get("foco", (0.5, 0.4))).convert("RGBA")
    alfa = Image.new("L", (W, alt_foto), 255)
    d = ImageDraw.Draw(alfa)
    for y in range(fade, alt_foto):
        t = (y - fade) / (alt_foto - fade)
        d.line([(0, y), (W, y)], fill=round(255 * (1 - t) ** 1.6))
    camada.putalpha(alfa)
    base.alpha_composite(camada)
    base.alpha_composite(r.degrade_vertical(W, H - fade, idv.AZUL_ESCURO, 0, 110), (0, fade))
    m = r.medir_bloco(s.get("titulo"), s.get("destaque"), s.get("texto"), LARG,
                      alt_max=RODAPE_Y - 760)
    y = max(760, RODAPE_Y - m["altura"])  # encosta o texto no rodapé (sem vazio)
    y = min(y, 815)
    caixa = r.desenhar_bloco(base, M, y, m)
    logo = r.rodape(base, numero, total)
    return base, {"foto_livre": (0, 0, W, fade), "texto": caixa, "logo": logo}


def foto_cheia(foto, s, numero=None, total=None):
    base = r.cobrir(foto, W, H, s.get("foco", (0.5, 0.5))).convert("RGBA")
    m = r.medir_bloco(s.get("titulo"), s.get("destaque"), s.get("texto"), LARG,
                      alt_max=RODAPE_Y - 620)
    y = RODAPE_Y - m["altura"]
    veu_ini = max(0, y - 380)
    # Rampa suave até o topo do título e véu quase opaco sob o texto (sem degrau visível).
    base.alpha_composite(r.degrade_vertical(W, y - veu_ini, idv.AZUL_ESCURO, 0, 215, curva=1.2), (0, veu_ini))
    base.alpha_composite(r.degrade_vertical(W, H - y, idv.AZUL_ESCURO, 215, 250), (0, y))
    caixa = r.desenhar_bloco(base, M, y, m)
    logo = r.rodape(base, numero, total)
    return base, {"foto_livre": (0, 0, W, veu_ini), "texto": caixa, "logo": logo}


def cartao(foto, s, numero=None, total=None):
    base = Image.new("RGBA", (W, H), idv.AZUL_ESCURO + (255,))
    base.alpha_composite(r.degrade_vertical(W, H, idv.AZUL_VIBRANTE, 70, 0, curva=1.4))
    # Título acima do cartão; texto complementar abaixo.
    m_tit = r.medir_bloco(s.get("titulo"), s.get("destaque"), None, LARG, tam_titulo=80, alt_max=330)
    cx_tit = r.desenhar_bloco(base, M, 84, m_tit)
    topo_cartao = cx_tit[3] + 36
    m_txt = None
    alt_txt = 0
    if s.get("texto"):
        fx = idv.fonte("texto", 40)
        linhas = r._equilibrar(s["texto"], fx, LARG)
        m_txt = (fx, linhas)
        alt_txt = 30 + len(linhas) * 55
    base_cartao = RODAPE_Y - alt_txt
    alt_cartao = base_cartao - topo_cartao
    if alt_cartao < 360:
        raise ValueError("Título/texto longos demais para o layout 'cartao'.")
    img = r.cobrir(foto, LARG, alt_cartao, s.get("foco", (0.5, 0.5))).convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=28, fill=255)
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((M, topo_cartao + 10, M + LARG, base_cartao + 10),
                                             radius=28, fill=(0, 8, 30, 150))
    base.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(14)))
    base.paste(img, (M, topo_cartao), mask)
    caixa_txt = cx_tit
    if m_txt:
        y = base_cartao + 30
        for ln in m_txt[1]:
            r.texto_sombra(base, (M, y), ln, m_txt[0], idv.TEXTO_SUAVE, sombra=3)
            y += 55
        caixa_txt = (M, cx_tit[1], W - M, y)
    logo = r.rodape(base, numero, total)
    return base, {"foto_livre": (M, topo_cartao, M + LARG, base_cartao),
                  "texto": cx_tit, "texto_inferior": (M, base_cartao, W - M, RODAPE_Y),
                  "texto_total": caixa_txt, "logo": logo}


LAYOUTS = {"foto_topo": foto_topo, "foto_cheia": foto_cheia, "cartao": cartao}
