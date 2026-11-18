"""Folha de contato (Pillow): todos os slides numerados, com o aviso "RASCUNHO FICTÍCIO — NÃO PUBLICAR".

Determinística: mesma lista de slides gera os mesmos bytes (PNG sem metadados de data). Usa as cores e as fontes oficiais de
``gerador.identidade``. Não grava nada além do arquivo de destino e não acessa rede.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw

from gerador import identidade as idv

TEXTO_RASCUNHO = "RASCUNHO FICTÍCIO — NÃO PUBLICAR"
MINIATURA = (360, 450)                     # 1/3 de 1080×1350
MARGEM = 48
TOPO, RODAPE = 190, 110
LARGURA_MINIMA = 1272


def _texto(d: ImageDraw.ImageDraw, xy, texto: str, fonte, cor, ancora: str = "la") -> None:
    d.text(xy, texto, font=fonte, fill=cor, anchor=ancora)


def colunas(n: int) -> int:
    return n if n <= 4 else 3


def gerar_folha(slides: list[Path], destino: Path, *, rotulo: str = "Carrossel editorial fictício") -> dict:
    """Grava ``destino`` (PNG) e devolve ``{"arquivo", "largura", "altura", "formato", "sha256", "slides", "colunas"}``."""
    if not slides:
        raise ValueError("nenhum slide para a folha de contato")
    n, cols = len(slides), colunas(len(slides))
    linhas = -(-n // cols)
    larg = max(LARGURA_MINIMA, cols * MINIATURA[0] + (cols + 1) * MARGEM)
    alt = TOPO + linhas * (MINIATURA[1] + 90) + RODAPE
    folha = Image.new("RGB", (larg, alt), idv.AZUL_ESCURO)
    d = ImageDraw.Draw(folha)
    d.rectangle((0, 0, larg, 110), fill=idv.VERMELHO)                                     # faixa de aviso
    _texto(d, (larg // 2, 55), TEXTO_RASCUNHO, idv.fonte("titulo", 54), idv.BRANCO, "mm")
    _texto(d, (MARGEM, 150), f"{rotulo} · {n} slides · 1080×1350", idv.fonte("rotulo", 30), idv.TEXTO_SUAVE, "lm")
    x0 = (larg - (cols * MINIATURA[0] + (cols - 1) * MARGEM)) // 2
    for i, arq in enumerate(slides):
        c, r = i % cols, i // cols
        x, y = x0 + c * (MINIATURA[0] + MARGEM), TOPO + r * (MINIATURA[1] + 90)
        with Image.open(arq) as im:
            miniatura = im.convert("RGB").resize(MINIATURA, Image.LANCZOS)
        d.rectangle((x - 3, y - 3, x + MINIATURA[0] + 2, y + MINIATURA[1] + 2), outline=idv.AMARELO, width=3)
        folha.paste(miniatura, (x, y))
        by = y + MINIATURA[1] + 14                                                          # selo numérico FORA da miniatura (não cobre o slide)
        d.ellipse((x, by, x + 56, by + 56), fill=idv.AMARELO)
        _texto(d, (x + 28, by + 28), str(i + 1), idv.fonte("titulo", 34), idv.AZUL_ESCURO, "mm")
        _texto(d, (x + 72, by + 28), f"Slide {i + 1} de {n}", idv.fonte("rotulo", 26), idv.BRANCO, "lm")
    _texto(d, (larg // 2, alt - 52), TEXTO_RASCUNHO, idv.fonte("rotulo", 32), idv.AMARELO, "mm")
    destino = Path(destino)
    folha.save(destino, "PNG")
    dados = destino.read_bytes()
    return {"arquivo": destino.name, "largura": larg, "altura": alt, "formato": "PNG", "sha256": hashlib.sha256(dados).hexdigest(),
            "slides": n, "colunas": cols}


def gerar_folha_geral(carrosseis: dict[str, list[Path]], destino: Path) -> dict:
    """Folha geral: uma linha por carrossel (miniaturas lado a lado), com o aviso de rascunho fictício."""
    if not carrosseis or not all(carrosseis.values()):
        raise ValueError("nenhum slide para a folha geral")
    mini, cols = (270, 337), max(len(v) for v in carrosseis.values())
    larg = max(LARGURA_MINIMA, cols * mini[0] + (cols + 1) * MARGEM)
    alt = 190 + len(carrosseis) * (mini[1] + 100) + 90
    folha = Image.new("RGB", (larg, alt), idv.AZUL_ESCURO)
    d = ImageDraw.Draw(folha)
    d.rectangle((0, 0, larg, 110), fill=idv.VERMELHO)
    _texto(d, (larg // 2, 55), TEXTO_RASCUNHO, idv.fonte("titulo", 54), idv.BRANCO, "mm")
    total = sum(len(v) for v in carrosseis.values())
    _texto(d, (MARGEM, 150), f"Folha geral · {len(carrosseis)} carrosséis · {total} slides · 1080×1350", idv.fonte("rotulo", 30), idv.TEXTO_SUAVE, "lm")
    for r, (nome, arqs) in enumerate(carrosseis.items()):
        y = 190 + r * (mini[1] + 100)
        _texto(d, (MARGEM, y + mini[1] + 40), nome, idv.fonte("rotulo", 30), idv.AMARELO, "lm")
        for c, arq in enumerate(arqs):
            x = MARGEM + c * (mini[0] + MARGEM)
            with Image.open(arq) as im:
                m = im.convert("RGB").resize(mini, Image.LANCZOS)
            d.rectangle((x - 3, y - 3, x + mini[0] + 2, y + mini[1] + 2), outline=idv.AMARELO, width=3)
            folha.paste(m, (x, y))
    _texto(d, (larg // 2, alt - 45), TEXTO_RASCUNHO, idv.fonte("rotulo", 32), idv.AMARELO, "mm")
    destino = Path(destino)
    folha.save(destino, "PNG")
    dados = destino.read_bytes()
    return {"arquivo": destino.name, "largura": larg, "altura": alt, "formato": "PNG", "sha256": hashlib.sha256(dados).hexdigest(),
            "slides": total, "carrosseis": len(carrosseis)}
