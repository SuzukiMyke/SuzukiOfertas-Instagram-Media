"""Identidade visual: cores, fontes e marca-d'água do logotipo oficial."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .catalogo import RAIZ

W, H = 1080, 1350
MARGEM = 72

AZUL_ESCURO = (1, 45, 107)      # #012D6B
AZUL_VIBRANTE = (3, 78, 231)    # #034EE7
AMARELO = (254, 198, 24)        # #FEC618
VERMELHO = (246, 2, 19)         # #F60213
BRANCO = (255, 255, 255)
TEXTO_SUAVE = (230, 236, 248)

LOGO = RAIZ / "brand" / "logo-suzuki-ofertas.png"
LOGO_LADO = 120

_PASTAS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu",
           "/usr/share/fonts/truetype/liberation"]
FONTES = {
    "titulo": ["InterDisplay-Black.otf", "Inter-Black.otf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
    "texto": ["Inter-Medium.otf", "Inter-Regular.otf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
    "rotulo": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
}


@lru_cache(maxsize=None)
def fonte(tipo: str, tamanho: int) -> ImageFont.FreeTypeFont:
    for nome in FONTES[tipo]:
        for pasta in _PASTAS:
            p = Path(pasta) / nome
            if p.exists():
                return ImageFont.truetype(str(p), tamanho)
    raise FileNotFoundError(f"Nenhuma fonte disponível para '{tipo}'.")


@lru_cache(maxsize=4)
def logo_marca_dagua(lado: int = LOGO_LADO, opacidade: float = 0.92) -> Image.Image:
    """Cópia em memória do logo com cantos transparentes (o arquivo original não muda)."""
    logo = Image.open(LOGO).convert("RGBA")
    mascara = Image.new("L", logo.size, 0)
    m = int(logo.width * 0.04)
    ImageDraw.Draw(mascara).ellipse((m, m, logo.width - m, logo.height - m), fill=255)
    mascara = mascara.filter(ImageFilter.GaussianBlur(logo.width * 0.03))
    logo.putalpha(mascara.point(lambda v: round(v * opacidade)))
    return logo.resize((lado, round(lado * logo.height / logo.width)), Image.LANCZOS)


# --- Constantes da B2R (refinamento visual). Só acréscimos: nenhuma constante anterior foi alterada. ---
MARGEM_SEGURANCA = 72            # nenhum texto ou logotipo (estilo B2R) fora desta margem
LOGO_GRANDE = 160                # logotipo inteiro do rodapé "grande"
CONTADOR_GRANDE = 40             # contador de páginas do rodapé "grande" (mínimo exigido: 38)
FONTE_TITULO_MIN = 72
FONTE_TEXTO_MIN = 44
FONTE_ROTULO_MIN = 36
FONTE_CONTADOR_MIN = 36
CONTRASTE_MIN = 4.5              # razão de contraste mínima (WCAG AA, texto normal)
ROTULO_ARTE = "Arte ilustrativa"
