"""Gera o slide realista 01 (1080x1350) da Suzuki Ofertas com Pillow.

Uso (a partir da raiz do repositório):
    python3.12 scripts/gerar_slide.py

Entradas:
    photos/foto_flux_01.jpg          fotografia gerada por IA (não é gerada aqui)
    brand/logo-suzuki-ofertas.png    logotipo oficial (somente leitura)
Saída:
    slides/slide_realista_01.jpg

O logotipo original não é alterado: uma versão derivada com transparência
(máscara circular suave que remove os cantos do fundo quadrado) é criada
apenas em memória.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FOTO = ROOT / "photos" / "foto_flux_01.jpg"
LOGO = ROOT / "brand" / "logo-suzuki-ofertas.png"
SAIDA = ROOT / "slides" / "slide_realista_01.jpg"

W, H = 1080, 1350
MARGEM = 72

AZUL_ESCURO = (1, 45, 107)      # #012D6B
AMARELO = (254, 198, 24)        # #FEC618
VERMELHO = (246, 2, 19)         # #F60213
BRANCO = (255, 255, 255)

TITULO_L1 = "5 ERROS QUE FAZEM"
TITULO_L2 = "VOCÊ GASTAR MAIS!"
SUBTITULO = "Descubra como evitar desperdícios nas compras online."

# Área da foto: ocupa do topo até FOTO_ALTURA; o degradê começa em FADE_INI.
FOTO_ALTURA = 860
FADE_INI = 560


def fonte(nomes, tamanho):
    pastas = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu"]
    for nome in nomes:
        for pasta in pastas:
            p = Path(pasta) / nome
            if p.exists():
                return ImageFont.truetype(str(p), tamanho)
    raise FileNotFoundError(f"Nenhuma fonte encontrada: {nomes}")


def ajustar_fonte(texto, nomes, tam_max, largura_max):
    tam = tam_max
    while tam > 20:
        f = fonte(nomes, tam)
        if f.getlength(texto) <= largura_max:
            return f
        tam -= 2
    return fonte(nomes, tam)


def camada_foto():
    if not FOTO.exists():
        raise SystemExit(f"ERRO: fotografia ausente em {FOTO}. Interrompendo (sem fundo substituto).")
    foto = Image.open(FOTO).convert("RGB")
    # Escala para cobrir a largura total e recorta a altura FOTO_ALTURA,
    # mantendo a parte superior/central (mesa, notebook e caixa).
    escala = W / foto.width
    foto = foto.resize((W, round(foto.height * escala)), Image.LANCZOS)
    topo = max(0, min(foto.height - FOTO_ALTURA, 150))
    return foto.crop((0, topo, W, topo + FOTO_ALTURA))


def logo_transparente(lado):
    """Versão derivada do logo com cantos transparentes (original intocado)."""
    logo = Image.open(LOGO).convert("RGBA")
    mascara = Image.new("L", logo.size, 0)
    d = ImageDraw.Draw(mascara)
    m = int(logo.width * 0.04)
    d.ellipse((m, m, logo.width - m, logo.height - m), fill=255)
    mascara = mascara.filter(ImageFilter.GaussianBlur(logo.width * 0.03))
    logo.putalpha(mascara)
    return logo.resize((lado, lado), Image.LANCZOS)  # quadrado: proporção preservada


def texto_com_sombra(base, xy, texto, f, cor, sombra=6):
    sombra_img = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra_img).text((xy[0], xy[1] + sombra), texto, font=f, fill=(0, 10, 30, 170))
    sombra_img = sombra_img.filter(ImageFilter.GaussianBlur(6))
    base.alpha_composite(sombra_img)
    ImageDraw.Draw(base).text(xy, texto, font=f, fill=cor)


def main():
    slide = Image.new("RGBA", (W, H), AZUL_ESCURO + (255,))

    # 1) Fotografia com transição suave para o azul-escuro.
    foto = camada_foto().convert("RGBA")
    alfa = Image.new("L", (W, FOTO_ALTURA), 255)
    da = ImageDraw.Draw(alfa)
    for y in range(FADE_INI, FOTO_ALTURA):
        t = (y - FADE_INI) / (FOTO_ALTURA - FADE_INI)
        da.line([(0, y), (W, y)], fill=round(255 * (1 - t) ** 1.6))
    foto.putalpha(alfa)
    slide.alpha_composite(foto, (0, 0))

    # Leve escurecimento azul no topo da área de texto para reforçar contraste.
    veu = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dv = ImageDraw.Draw(veu)
    for y in range(FADE_INI, H):
        t = min(1.0, (y - FADE_INI) / 260)
        dv.line([(0, y), (W, y)], fill=AZUL_ESCURO + (round(110 * t),))
    slide.alpha_composite(veu)

    largura_util = W - 2 * MARGEM
    pesadas = ["InterDisplay-Black.otf", "Inter-Black.otf", "DejaVuSans-Bold.ttf"]
    medias = ["Inter-Medium.otf", "Inter-Regular.otf", "DejaVuSans.ttf"]

    # 2) Título (branco + amarelo), mesmo tamanho nas duas linhas.
    f_tit = ajustar_fonte(max(TITULO_L1, TITULO_L2, key=len), pesadas, 100, largura_util)
    f_tit = min(
        (ajustar_fonte(TITULO_L1, pesadas, f_tit.size, largura_util),
         ajustar_fonte(TITULO_L2, pesadas, f_tit.size, largura_util)),
        key=lambda f: f.size,
    )
    asc, desc = f_tit.getmetrics()
    alt_linha = asc + desc

    y_tit = 815
    # Faixa de destaque vermelha (cor da marca) acima do título.
    ImageDraw.Draw(slide).rounded_rectangle(
        (MARGEM, y_tit - 34, MARGEM + 110, y_tit - 22), radius=6, fill=VERMELHO + (255,)
    )
    texto_com_sombra(slide, (MARGEM, y_tit), TITULO_L1, f_tit, BRANCO)
    texto_com_sombra(slide, (MARGEM, y_tit + alt_linha - 6), TITULO_L2, f_tit, AMARELO)

    # 3) Texto complementar (quebra automática dentro das margens).
    # Quebra equilibrada em duas linhas (evita palavra órfã).
    f_sub = fonte(medias, 42)
    palavras = SUBTITULO.split()
    melhor = None
    for i in range(1, len(palavras)):
        l1, l2 = " ".join(palavras[:i]), " ".join(palavras[i:])
        larg = max(f_sub.getlength(l1), f_sub.getlength(l2))
        if larg <= largura_util and (melhor is None or larg < melhor[0]):
            melhor = (larg, [l1, l2])
    linhas = melhor[1] if melhor else [SUBTITULO]
    y_sub = y_tit + 2 * alt_linha + 30
    for ln in linhas:
        texto_com_sombra(slide, (MARGEM, y_sub), ln, f_sub, (230, 236, 248), sombra=3)
        y_sub += 58

    # 4) Logotipo pequeno no rodapé (marca-d'água discreta), canto inferior direito.
    lado = 132
    logo = logo_transparente(lado)
    a = logo.getchannel("A").point(lambda v: round(v * 0.92))
    logo.putalpha(a)
    slide.alpha_composite(logo, (W - MARGEM - lado + 10, H - 48 - lado))

    # Linha fina de rodapé à esquerda, alinhada ao logo, para equilibrar o espaço.
    d = ImageDraw.Draw(slide)
    y_rod = H - 48 - lado // 2
    d.line([(MARGEM, y_rod), (W - MARGEM - lado - 20, y_rod)], fill=(255, 255, 255, 45), width=2)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    slide.convert("RGB").save(SAIDA, "JPEG", quality=92, optimize=True, progressive=True)
    print(f"Slide salvo em {SAIDA} ({W}x{H})")


if __name__ == "__main__":
    main()
