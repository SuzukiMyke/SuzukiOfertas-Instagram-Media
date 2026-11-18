"""Fundo de marca determinístico (1080×1350) para a classe visual ``composicao_grafica``.

Gerado só com Pillow e as cores oficiais de ``identidade.py`` (``AZUL_ESCURO``, ``AZUL_VIBRANTE``, ``AMARELO``); usa o logotipo oficial
como marca-d'água em memória (``identidade.logo_marca_dagua``: o arquivo de ``brand/`` nunca é alterado). **Sem fotografia, sem
texto, sem produto, sem rede, sem serviço externo.** A mesma ``variante`` produz os mesmos bytes e o mesmo SHA-256 (mesma versão do
Pillow/libjpeg; outra versão pode codificar o JPEG de outro jeito, o que é uma limitação conhecida).

O registro no catálogo (``registrar``) cria a foto como ``provedor = composicao-grafica`` (prefixo ``cg``), ``origem = composicao-grafica`` e
aprovação **pendente**: nada é aprovado aqui; a aprovação é humana. Não altera ``photos/catalogo.json`` a menos que o chamador passe
justamente esse catálogo (os testes usam catálogo temporário). A renderização de carrosséis com esse fundo é da etapa seguinte.
"""
from __future__ import annotations

import hashlib
import io
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import identidade as idv
from .catalogo import ORIGEM_COMPOSICAO_GRAFICA, Catalogo, agora_utc

W, H = idv.W, idv.H
VARIANTES = 12
VERSAO = "1.0"
PROVEDOR = "composicao-grafica"
QUALIDADE_JPEG = 95
RESTRICOES = ["Composição gráfica: não representa produto algum", "Sem fotografias nem textos de produtos",
              "Rotular como \"Arte ilustrativa\" quando usada com produto", "Aprovação visual humana obrigatória"]


def _validar_variante(variante) -> int:
    if isinstance(variante, bool) or not isinstance(variante, int) or not 0 <= variante < VARIANTES:
        raise ValueError(f"variante deve ser um inteiro de 0 a {VARIANTES - 1}")
    return variante


def _gradiente(variante: int) -> Image.Image:
    """Degradê diagonal AZUL_ESCURO → AZUL_VIBRANTE; o ângulo muda com a variante."""
    angulo = (variante * 37) % 360
    lado = 2 * math.ceil(math.hypot(W, H))
    mascara = Image.linear_gradient("L").resize((lado, lado), Image.BILINEAR).rotate(angulo, resample=Image.BILINEAR)
    ex, ey = (lado - W) // 2, (lado - H) // 2
    mascara = mascara.crop((ex, ey, ex + W, ey + H))
    escuro = Image.new("RGB", (W, H), idv.AZUL_ESCURO)
    vibrante = Image.new("RGB", (W, H), idv.AZUL_VIBRANTE)
    return Image.composite(vibrante, escuro, mascara)


def _formas(variante: int) -> Image.Image:
    """Círculos, anéis e faixas diagonais (AMARELO e BRANCO translúcidos); posições fixas pela variante (semente inteira)."""
    rnd = random.Random(1000003 * (variante + 1))
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    for _ in range(5):                                                          # círculos cheios
        r = rnd.randint(90, 280)
        x, y = rnd.randint(-80, W + 80), rnd.randint(-80, H + 80)
        cor = rnd.choice((idv.AMARELO, idv.BRANCO))
        d.ellipse((x - r, y - r, x + r, y + r), fill=cor + (rnd.randint(46, 96),))
    for _ in range(4):                                                          # anéis
        r = rnd.randint(160, 460)
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        d.ellipse((x - r, y - r, x + r, y + r), outline=idv.AMARELO + (rnd.randint(110, 170),), width=rnd.randint(8, 20))
    for _ in range(3):                                                          # faixas diagonais
        x0 = rnd.randint(-300, W)
        larg = rnd.randint(40, 120)
        d.polygon([(x0, 0), (x0 + larg, 0), (x0 + larg + H // 2, H), (x0 + H // 2, H)],
                  fill=idv.BRANCO + (rnd.randint(26, 54),))
    for _ in range(3):                                                          # manchas escuras (profundidade)
        r = rnd.randint(200, 420)
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        d.ellipse((x - r, y - r, x + r, y + r), fill=idv.AZUL_ESCURO + (rnd.randint(90, 150),))
    return camada


def _textura(variante: int) -> Image.Image:
    """Trama regular em TODA a imagem (faixas diagonais finas + pontos), com deslocamento pela variante: garante contraste mínimo
    em qualquer recorte (o validador do gerador exige desvio de luminância ≥ 12 na área da foto)."""
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    passo, esp = 150, 70
    desloc = (variante * 23) % passo
    for k in range(-H, W + H, passo):
        x = k + desloc
        d.polygon([(x, 0), (x + esp, 0), (x + esp + H, H), (x + H, H)], fill=idv.BRANCO + (58,))
    for yy in range(40, H, 110):
        for xx in range(40 + (yy // 110 % 2) * 55 + desloc // 3, W, 110):
            d.ellipse((xx - 9, yy - 9, xx + 9, yy + 9), fill=idv.AMARELO + (150,))
    return camada


def gerar_fundo(variante: int = 0) -> Image.Image:
    """Imagem RGB 1080×1350, determinística para a ``variante`` (0 a ``VARIANTES - 1``)."""
    variante = _validar_variante(variante)
    base = _gradiente(variante).convert("RGBA")
    formas = _formas(variante)
    base.alpha_composite(_textura(variante))
    base.alpha_composite(formas.filter(ImageFilter.GaussianBlur(2)))
    brilho = Image.new("RGBA", (W, H), (0, 0, 0, 0))                           # brilho suave em AZUL_VIBRANTE no canto da variante
    cx, cy = (W * (1 + variante % 3) // 4), (H * (1 + (variante // 3) % 3) // 4)
    ImageDraw.Draw(brilho).ellipse((cx - 420, cy - 420, cx + 420, cy + 420), fill=idv.AZUL_VIBRANTE + (90,))
    base.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(140)))
    marca = idv.logo_marca_dagua(420, 0.12)                                     # logotipo oficial, só em memória, discreto
    base.alpha_composite(marca, ((W - marca.width) // 2, H - marca.height - 150))
    return base.convert("RGB")


def fundo_bytes(variante: int = 0) -> bytes:
    """JPEG (qualidade 95, sem otimização/progressivo, sem EXIF): mesmos bytes para a mesma variante."""
    buf = io.BytesIO()
    gerar_fundo(variante).save(buf, "JPEG", quality=QUALIDADE_JPEG, subsampling=0, optimize=False, progressive=False)
    return buf.getvalue()


def sha256_fundo(variante: int = 0) -> str:
    return hashlib.sha256(fundo_bytes(variante)).hexdigest()


def registrar(catalogo: Catalogo, variante: int = 0, descricao: str | None = None, agora: str | None = None) -> tuple[str, bool]:
    """Grava o fundo em ``<raiz do catálogo>/photos/cg-NNNN.jpg`` e o registra PENDENTE. Devolve ``(id, nova)``.

    O catálogo é obrigatório (não há padrão): nunca toca o catálogo do repositório sem que o chamador o passe. Mesmo conteúdo (SHA-256)
    não é registrado duas vezes."""
    variante = _validar_variante(variante)
    dados = fundo_bytes(variante)
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
        "id": foto_id, "provedor": PROVEDOR, "nome_arquivo_original": f"fundo_marca_v{variante:02d}.jpg",
        "sha256_original": sha, "sha256": sha, "largura": W, "altura": H, "formato_original": "JPEG",
        "data": agora or agora_utc(), "tipo_data": "geracao", "origem": ORIGEM_COMPOSICAO_GRAFICA,
        "descricao": descricao or f"Fundo de marca gerado por código (variante {variante})", "prompt": None,
        "gerador": {"modulo": "gerador.fundo_marca", "versao": VERSAO, "variante": variante},
        "restricoes_uso": list(RESTRICOES), "caminho_github": rel, "caminho_original": rel,
    })                                                                           # sem 'aprovacao': Catalogo.adicionar o cria PENDENTE
    catalogo.salvar()
    return foto_id, True
