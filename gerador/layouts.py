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


# =================================================================================================================================
# B2R — quatro layouts novos (somente acréscimos; os três acima não mudaram). Todos: 1080×1350, margem de segurança de 72 px, texto
# SEMPRE sobre painéis opacos de cor controlada (contraste ≥ 4,5:1), títulos ≥ 72 px, texto ≥ 44 px, rótulo "Arte ilustrativa" ≥ 36 px,
# contador ≥ 36 px e logotipo de 160 px inteiro. Texto que não cabe respeitando esses mínimos NÃO é reduzido nem truncado:
# o layout levanta ``ErroTextoNaoCabe``. O campo ``foto`` é a imagem de fundo (``ilustracao_capa``: a ilustração da categoria).
# Cada layout devolve ``(imagem, areas)`` como os antigos; ``areas["v2"]`` traz os itens de texto (caixa, cor, tamanho), o conteúdo e o logo
# para ``validacao.validar_slide_v2``.
# =================================================================================================================================
_SEM_TEXTO = False


class sem_texto:
    """Contexto que faz os layouts B2R renderizarem SEM desenhar os textos (mesma geometria): usado para medir o contraste exato."""

    def __enter__(self):
        global _SEM_TEXTO
        self._anterior, _SEM_TEXTO = _SEM_TEXTO, True

    def __exit__(self, *exc):
        global _SEM_TEXTO
        _SEM_TEXTO = self._anterior


class ErroTextoNaoCabe(ValueError):
    """O texto não cabe no layout respeitando os tamanhos mínimos (nada é reduzido abaixo do limite nem truncado)."""


M2 = idv.MARGEM_SEGURANCA                       # 72
LARG2 = W - 2 * M2                              # 936
Y_RODAPE = H - M2 - idv.LOGO_GRANDE             # 1118: topo do logotipo
Y_FIM = Y_RODAPE - 22                           # 1096: fim da área de conteúdo
PAINEL = idv.AZUL_ESCURO


def _alt_linha(fnt) -> int:
    asc, desc = fnt.getmetrics()
    return asc + desc


def _linhas(texto: str, fnt, largura: float) -> list[str]:
    linhas, atual = [], ""
    for p in texto.split():
        if fnt.getlength(p) > largura:
            raise ErroTextoNaoCabe(f"palavra mais larga que a área ({largura:.0f}px)")
        cand = f"{atual} {p}".strip()
        if fnt.getlength(cand) <= largura:
            atual = cand
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def _ajustar(texto: str, tipo: str, tam_max: int, tam_min: int, largura: float, max_linhas: int):
    """Maior fonte (≤ tam_max, ≥ tam_min) com o texto em até max_linhas linhas; levanta ``ErroTextoNaoCabe`` se nenhuma serve."""
    for tam in range(tam_max, tam_min - 1, -2):
        fnt = idv.fonte(tipo, tam)
        try:
            ln = _linhas(texto, fnt, largura)
        except ErroTextoNaoCabe:
            continue
        if ln and len(ln) <= max_linhas:
            return fnt, ln, tam
    raise ErroTextoNaoCabe(f"texto não cabe em {max_linhas} linha(s) com fonte mínima de {tam_min}px: {texto}")


def _ajustar_tokens(tokens, tam_max: int, tam_min: int, largura: float, max_linhas: int):
    """Como ``_ajustar`` para palavras coloridas ``[(palavra, cor)]``; devolve (fonte, linhas de runs, tam)."""
    for tam in range(tam_max, tam_min - 1, -2):
        fnt = idv.fonte("titulo", tam)
        esp = fnt.getlength(" ")
        linhas, atual, larg = [], [], 0.0
        ok = True
        for pal, cor in tokens:
            lp = fnt.getlength(pal)
            if lp > largura:
                ok = False
                break
            if atual and larg + esp + lp > largura:
                linhas.append(atual)
                atual, larg = [], 0.0
            larg += (esp if atual else 0) + lp
            atual.append((pal, cor))
        if not ok:
            continue
        if atual:
            linhas.append(atual)
        if linhas and len(linhas) <= max_linhas:
            return fnt, linhas, tam
    raise ErroTextoNaoCabe("título não cabe com fonte mínima de %dpx: %s" % (tam_min, " ".join(p for p, _ in tokens)))


class _Tela:
    """Canvas dos layouts B2R: desenha, registra itens de texto (caixa, cor, tamanho) e caixas de conteúdo."""

    def __init__(self, fundo: Image.Image, numero, total):
        self.base = fundo.convert("RGBA")
        self.d = ImageDraw.Draw(self.base)
        self.numero, self.total = numero, total
        self.itens: list[dict] = []
        self.conteudo: list[tuple] = []

    def painel(self, caixa, fill=PAINEL, raio=34, borda=None, largura_borda=5):
        self.d.rounded_rectangle(caixa, radius=raio, fill=fill + (255,), outline=(borda + (255,)) if borda else None, width=largura_borda)
        self.conteudo.append(tuple(caixa))

    def texto(self, xy, txt: str, fnt, cor, tipo: str, ancora: str = "la", fundo=None) -> tuple:
        if not _SEM_TEXTO:
            self.d.text(xy, txt, font=fnt, fill=cor + (255,), anchor=ancora)
        x0, y0, x1, y1 = self.d.textbbox(xy, txt, font=fnt, anchor=ancora)
        caixa = (x0 - 4, y0 - 4, x1 + 4, y1 + 4)
        self.itens.append({"tipo": tipo, "texto": txt, "caixa": caixa, "cor": tuple(cor), "tamanho": fnt.size,
                           "fundo": tuple(fundo or PAINEL)})              # superfície controlada sob o texto (painel opaco)
        return caixa

    def linhas(self, x, y, linhas, fnt, cor, tipo, espaco=0) -> int:
        alt = _alt_linha(fnt)
        for ln in linhas:
            self.texto((x, y), ln, fnt, cor, tipo)
            y += alt + espaco
        return y

    def titulo(self, x, y, linhas, fnt) -> int:
        alt = _alt_linha(fnt) - round(fnt.size * 0.06)
        for ln in linhas:
            xx = x
            for pal, cor in ln:
                self.texto((xx, y), pal, fnt, cor, "titulo")
                xx += fnt.getlength(pal) + fnt.getlength(" ")
            y += alt
        return y

    def rotulo(self) -> tuple:
        """Pílula "Arte ilustrativa" (36 px) no canto superior esquerdo, sobre painel opaco."""
        fnt = idv.fonte("rotulo", idv.FONTE_ROTULO_MIN)
        larg = int(fnt.getlength(idv.ROTULO_ARTE)) + 44
        caixa = (M2, M2, M2 + larg, M2 + 68)
        self.painel(caixa, raio=34, borda=idv.AMARELO, largura_borda=3)
        self.texto((M2 + 22, M2 + 34), idv.ROTULO_ARTE, fnt, idv.BRANCO, "rotulo", "lm")
        return caixa

    def rodape(self) -> tuple:
        """Contador (pílula própria, 40 px) à esquerda e logotipo de 160 px inteiro à direita."""
        if self.numero and self.total and self.total > 1:
            fnt = idv.fonte("rotulo", idv.CONTADOR_GRANDE)
            txt = f"{self.numero}/{self.total}"
            larg = int(fnt.getlength(txt)) + 44
            cy = Y_RODAPE + idv.LOGO_GRANDE // 2
            self.painel((M2, cy - 36, M2 + larg, cy + 36), raio=36)
            self.texto((M2 + 22, cy), txt, fnt, idv.BRANCO, "contador", "lm")
        caixa = r.rodape(self.base, None, None, grande=True)
        self.conteudo.append(caixa)
        return caixa

    def areas(self, nome, foto_livre, texto, texto_total, logo) -> dict:
        return {"foto_livre": tuple(foto_livre), "texto": tuple(texto), "texto_total": tuple(texto_total), "logo": logo,
                "v2": {"layout": nome, "itens": self.itens, "conteudo": self.conteudo, "logo": logo, "logo_lado": idv.LOGO_GRANDE,
                       "margem": M2}}


def _fundo_b2r(foto) -> Image.Image:
    return r.cobrir(foto, W, H, (0.5, 0.5)).convert("RGBA")


def _fundo_calmo(foto) -> Image.Image:
    """Fundo com os elementos decorativos atenuados (azul-marinho a 50 %), para os slides de lista e de captação."""
    base = _fundo_b2r(foto)
    return Image.blend(base, Image.new("RGBA", base.size, idv.AZUL_ESCURO + (255,)), 0.5)


def _bloco_titulo(t: _Tela, y: int, titulo: str, destaque: str | None, max_linhas: int = 2, alt_extra: int = 0, tam_max: int = 96):
    """Painel com título (≥72 px; palavras de ``destaque`` em amarelo). Devolve (caixa do painel, caixa do texto)."""
    tokens = [(p, idv.BRANCO) for p in (titulo or "").split()] + [(p, idv.AMARELO) for p in (destaque or "").split()]
    if not tokens:
        raise ErroTextoNaoCabe("título vazio")
    fnt, linhas, _ = _ajustar_tokens(tokens, tam_max, idv.FONTE_TITULO_MIN, LARG2 - 64, max_linhas)
    alt = _alt_linha(fnt) - round(fnt.size * 0.06)
    h = len(linhas) * alt + 56 + alt_extra
    painel = (M2, y, W - M2, y + h)
    t.painel(painel)
    fim = t.titulo(M2 + 32, y + 28, linhas, fnt)
    return painel, (M2 + 32, y + 28, W - M2 - 32, fim)


def _ilustracao_capa(foto, s, numero, total, tam_max):
    """Capa: ilustração grande da categoria, nome do produto (título + destaque), nome da loja e rótulo "Arte ilustrativa"."""
    fundo = Image.new("RGBA", (W, H), PAINEL + (255,))
    fundo.alpha_composite(r.degrade_vertical(W, H, idv.AZUL_VIBRANTE, 110, 0, curva=1.2))
    t = _Tela(fundo, numero, total)
    box = (M2, M2, W - M2, M2 + 672)
    img = r.cobrir(foto, LARG2, 672, s.get("foco", (0.5, 0.5))).convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=36, fill=255)
    t.base.paste(img, (box[0], box[1]), mask)
    t.d.rounded_rectangle(box, radius=36, outline=idv.AMARELO + (255,), width=6)
    t.conteudo.append(box)
    t.rotulo_xy = None
    # rótulo dentro da ilustração (canto superior esquerdo)
    fnt = idv.fonte("rotulo", idv.FONTE_ROTULO_MIN)
    larg = int(fnt.getlength(idv.ROTULO_ARTE)) + 44
    cx = (M2 + 24, M2 + 24, M2 + 24 + larg, M2 + 24 + 68)
    t.painel(cx, raio=34, borda=idv.AMARELO, largura_borda=3)
    t.texto((cx[0] + 22, cx[1] + 34), idv.ROTULO_ARTE, fnt, idv.BRANCO, "rotulo", "lm")
    # painel de texto
    topo = M2 + 672 + 24
    tokens = [(p, idv.BRANCO) for p in (s.get("titulo") or "").split()] + [(p, idv.AMARELO) for p in (s.get("destaque") or "").split()]
    if not tokens:
        raise ErroTextoNaoCabe("título vazio")
    ftit, ltit, _ = _ajustar_tokens(tokens, tam_max, idv.FONTE_TITULO_MIN, LARG2 - 64, 2)
    loja = (s.get("texto") or "").strip()
    alt_t = _alt_linha(ftit) - round(ftit.size * 0.06)
    if loja:
        floja, lloja, _ = _ajustar(loja, "texto", 52, idv.FONTE_TEXTO_MIN, LARG2 - 64, 1)
    painel = (M2, topo, W - M2, Y_FIM)
    y = topo + 26
    t.painel(painel)
    t.d.rounded_rectangle((M2 + 32, y, M2 + 142, y + 12), radius=6, fill=idv.VERMELHO + (255,))
    y += 12 + 16
    y_ini = y
    y = t.titulo(M2 + 32, y, ltit, ftit)
    caixa_titulo = (M2 + 32, y_ini, W - M2 - 32, y)
    if loja:
        y = t.linhas(M2 + 32, y + 8, lloja, floja, idv.TEXTO_SUAVE, "texto")
    if y > Y_FIM - 16:
        raise ErroTextoNaoCabe("título e loja não cabem no painel da capa respeitando os tamanhos mínimos")
    logo = t.rodape()
    return t.base, t.areas("ilustracao_capa", box, caixa_titulo, painel, logo)


def _icone_verificacao(t: _Tela, cx: int, cy: int, raio: int) -> None:
    """Elemento GRÁFICO decorativo (círculo com marca de seleção): não indica certificação nem comprovação."""
    t.d.ellipse((cx - raio, cy - raio, cx + raio, cy + raio), fill=idv.AMARELO + (255,))
    t.d.line([(cx - raio * .42, cy + raio * .02), (cx - raio * .1, cy + raio * .36), (cx + raio * .46, cy - raio * .32)],
             fill=PAINEL + (255,), width=max(8, raio // 5), joint="curve")


def _destaque_numerico(foto, s, numero, total, tam_max):
    """Característica em destaque: título curto, número e unidade grandes (``destaque``, ex.: "5 L") e texto explicativo."""
    t = _Tela(_fundo_b2r(foto), numero, total)
    t.rotulo()
    y = M2 + 68 + 24
    painel_t, caixa_t = _bloco_titulo(t, y, s.get("titulo"), None, 2, tam_max=tam_max)
    topo_card = painel_t[3] + 24
    texto = (s.get("texto") or "").strip()
    destaque = (s.get("destaque") or "").strip()
    if destaque:
        if not texto:
            raise ErroTextoNaoCabe("texto explicativo vazio")
        fx, lx, _ = _ajustar(texto, "texto", 52, idv.FONTE_TEXTO_MIN, LARG2 - 64, 4)
        alt_x = _alt_linha(fx)
        h_expl = len(lx) * alt_x + 56
        painel_x = (M2, Y_FIM - h_expl, W - M2, Y_FIM)
        card = (M2, topo_card, W - M2, painel_x[1] - 24)
    else:                                                   # sem número: a característica ocupa o cartão em letras grandes
        card = (M2, topo_card, W - M2, Y_FIM)
        painel_x = None
    if card[3] - card[1] < 300:
        raise ErroTextoNaoCabe("área da característica menor que 300 px com os textos e tamanhos mínimos")
    t.painel(card, borda=idv.AMARELO, largura_borda=5)
    _icone_verificacao(t, card[2] - 76, card[1] + 76, 40)
    if destaque:
        partes = destaque.split(" ", 1)
        num, uni = partes[0], (partes[1] if len(partes) > 1 else "")
        area_w, area_h = LARG2 - 140, card[3] - card[1] - 80
        for tam in range(400, 159, -8):
            fn = idv.fonte("titulo", tam)
            fu = idv.fonte("titulo", max(idv.FONTE_TITULO_MIN, tam // 2))
            larg = fn.getlength(num) + (24 + fu.getlength(uni) if uni else 0)
            if larg <= area_w and _alt_linha(fn) <= area_h:
                break
        else:
            raise ErroTextoNaoCabe("número e unidade não cabem em tamanho grande (mínimo 160 px)")
        x0 = card[0] + (LARG2 - larg) / 2
        yc = (card[1] + card[3]) / 2 + 20
        t.texto((x0, yc), num, fn, idv.AMARELO, "destaque", "lm")
        if uni:
            t.texto((x0 + fn.getlength(num) + 24, yc + (fn.size - fu.size) * 0.18), uni, fu, idv.BRANCO, "destaque", "lm")
        t.painel(painel_x)
        t.linhas(M2 + 32, painel_x[1] + 28, lx, fx, idv.BRANCO, "texto")
        caixa_total = (M2, y, W - M2, Y_FIM)
    else:
        fx, lx, _ = _ajustar(texto, "texto", 88, idv.FONTE_TITULO_MIN, LARG2 - 140, 4)
        alt_x = _alt_linha(fx)
        yy = card[1] + ((card[3] - card[1]) - len(lx) * alt_x) // 2
        t.linhas(M2 + 40, yy, lx, fx, idv.BRANCO, "titulo")
        caixa_total = (M2, y, W - M2, Y_FIM)
    logo = t.rodape()
    return t.base, t.areas("destaque_numerico", card, caixa_t, caixa_total, logo)


def _lista_caracteristicas(foto, s, numero, total, tam_max):
    """Lista de 2 a 3 características (``texto`` com um item por linha, separados por \n), marcadores visuais e título curto."""
    t = _Tela(_fundo_calmo(foto), numero, total)
    t.rotulo()
    itens = [i.strip() for i in (s.get("texto") or "").split("\n") if i.strip()]
    if not 2 <= len(itens) <= 3:
        raise ErroTextoNaoCabe("a lista exige de 2 a 3 características")
    y = M2 + 68 + 24
    painel_t, caixa_t = _bloco_titulo(t, y, s.get("titulo"), s.get("destaque"), 2, tam_max=min(tam_max, 80))
    topo = painel_t[3] + 24
    disp = Y_FIM - topo
    larg_txt = LARG2 - 2 * 28 - 100
    for tam in range(76, idv.FONTE_TEXTO_MIN - 1, -2):    # fonte maior: melhor uso do espaço do cartão
        fnt = idv.fonte("texto", tam)
        try:
            blocos = [_linhas(i, fnt, larg_txt) for i in itens]
        except ErroTextoNaoCabe:
            continue
        alturas = [len(b) * _alt_linha(fnt) + 56 for b in blocos]
        if all(len(b) <= 3 for b in blocos) and sum(alturas) + 20 * (len(itens) - 1) <= disp:
            break
    else:
        raise ErroTextoNaoCabe("a lista não cabe com fonte mínima de %dpx" % idv.FONTE_TEXTO_MIN)
    extra = (disp - sum(alturas) - 20 * (len(itens) - 1)) // len(itens)
    extra = max(0, min(extra, 150))
    yy = topo
    primeiro = topo
    for k, (b, h) in enumerate(zip(blocos, alturas)):
        h += extra
        linha = (M2, yy, W - M2, yy + h)
        t.painel(linha, borda=idv.AMARELO if k == 0 else None, largura_borda=4)
        cy = yy + h // 2
        t.d.ellipse((M2 + 28, cy - 38, M2 + 104, cy + 38), fill=idv.AMARELO + (255,))
        t.d.line([(M2 + 50, cy + 2), (M2 + 62, cy + 16), (M2 + 84, cy - 14)], fill=PAINEL + (255,), width=10, joint="curve")
        alt = _alt_linha(fnt)
        t.linhas(M2 + 128, cy - len(b) * alt // 2, b, fnt, idv.BRANCO, "texto")
        yy += h + 20
    fim = yy - 20
    lista = (M2, primeiro, W - M2, fim)
    logo = t.rodape()
    return t.base, t.areas("lista_caracteristicas", lista, caixa_t, (M2, y, W - M2, fim), logo)


def _cta_seguir(foto, s, numero, total, tam_max):
    """Captação de seguidores: faixa da marca, título persuasivo, texto, botões gráficos WhatsApp e Telegram (sem links inventados).

    ``titulo``: chamada; ``texto``: corpo e complemento separados por \n; ``destaque``: linha opcional com os links já validados."""
    t = _Tela(_fundo_calmo(foto), numero, total)
    t.rotulo()
    y = M2 + 68 + 20
    if not s.get("destaque"):                                   # faixa da marca; com a linha de links o espaço é usado por eles
        fb = idv.fonte("titulo", idv.FONTE_TITULO_MIN)
        faixa = (M2, y, W - M2, y + _alt_linha(fb) + 20)
        t.painel(faixa, fill=idv.AZUL_VIBRANTE, borda=idv.AMARELO, largura_borda=4)
        t.texto((W // 2, (faixa[1] + faixa[3]) // 2), "SUZUKI OFERTAS", fb, idv.BRANCO, "titulo", "mm", fundo=idv.AZUL_VIBRANTE)
        y = faixa[3] + 20
    else:
        faixa = (M2, y, W - M2, y)
    painel_t, caixa_t = _bloco_titulo(t, y, s.get("titulo"), None, 2, tam_max=tam_max)
    partes = [p.strip() for p in (s.get("texto") or "").split("\n") if p.strip()]
    if not partes:
        raise ErroTextoNaoCabe("texto da chamada vazio")
    corpo, complemento = partes[0], (partes[1] if len(partes) > 1 else "")
    y = painel_t[3] + 20
    fc, lc, _ = _ajustar(corpo, "texto", 56, idv.FONTE_TEXTO_MIN, LARG2 - 64, 2)
    h_corpo = len(lc) * _alt_linha(fc) + 44
    t.painel((M2, y, W - M2, y + h_corpo))
    t.linhas(M2 + 32, y + 22, lc, fc, idv.BRANCO, "texto")
    y += h_corpo + 20
    fbt = idv.fonte("titulo", 56)
    w_bt = (LARG2 - 24) // 2
    topo_botoes = y
    for k, (nome, bg) in enumerate((("WhatsApp", idv.AMARELO), ("Telegram", idv.BRANCO))):
        x0 = M2 + k * (w_bt + 24)
        caixa = (x0, y, x0 + w_bt, y + 132)
        t.painel(caixa, fill=bg, raio=62)
        t.texto(((caixa[0] + caixa[2]) // 2, (caixa[1] + caixa[3]) // 2), nome, fbt, PAINEL, "botao", "mm", fundo=bg)
    y += 132 + 22
    resto = []
    if complemento:
        resto.append((complemento, 56))
    if s.get("destaque"):
        resto.append((s["destaque"], 52))
    caixa_fim = y
    if resto:
        blocos = []
        for txt, tam in resto:
            fnt, ln, _ = _ajustar(txt, "texto", tam, idv.FONTE_TEXTO_MIN, LARG2 - 64, 2)
            blocos.append((fnt, ln))
        h = sum(len(l) * _alt_linha(f) for f, l in blocos) + 44 + 8 * (len(blocos) - 1)
        t.painel((M2, y, W - M2, y + h))
        yy = y + 22
        for fnt, ln in blocos:
            yy = t.linhas(M2 + 32, yy, ln, fnt, idv.TEXTO_SUAVE, "texto") + 8
        y += h
        caixa_fim = y
    if caixa_fim > Y_FIM:
        raise ErroTextoNaoCabe("a chamada de captação não cabe respeitando os tamanhos mínimos")
    area_visual = (M2, topo_botoes, W - M2, Y_FIM)
    if area_visual[3] - area_visual[1] < 300:
        area_visual = (M2, Y_FIM - 300, W - M2, Y_FIM)
    logo = t.rodape()
    return t.base, t.areas("cta_seguir", area_visual, caixa_t, (M2, faixa[1], W - M2, caixa_fim), logo)


def _com_tentativas(impl):
    """Tenta títulos de 96 a 72 px até o layout inteiro caber; só então levanta ``ErroTextoNaoCabe`` (nunca abaixo de 72 px)."""
    def layout(foto, s, numero=None, total=None):
        ultimo = None
        for tam_max in (96, 88, 80, 72):
            try:
                return impl(foto, s, numero, total, tam_max)
            except ErroTextoNaoCabe as e:
                ultimo = e
        raise ultimo
    layout.__name__, layout.__doc__ = impl.__name__.lstrip("_"), impl.__doc__
    return layout


ilustracao_capa = _com_tentativas(_ilustracao_capa)
destaque_numerico = _com_tentativas(_destaque_numerico)
lista_caracteristicas = _com_tentativas(_lista_caracteristicas)
cta_seguir = _com_tentativas(_cta_seguir)

LAYOUTS_B2R = {"ilustracao_capa": ilustracao_capa, "destaque_numerico": destaque_numerico,
               "lista_caracteristicas": lista_caracteristicas, "cta_seguir": cta_seguir}
LAYOUTS.update(LAYOUTS_B2R)
