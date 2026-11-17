"""Política de títulos (contrato v1.1 §7.1). Módulo novo, só modo 1.1.

O título identifica o produto, **não autoriza alegação**. Níveis:
- ALTA: o título não pode ser texto de peça pública (usar variante genérica ou bloquear).
- MÉDIA: aviso na ficha; o trecho não é fato verificado; revisão humana obrigatória.
A lista é versionada aqui e é **mínima**; sujeita a falsos positivos (limitação registrada no contrato §14).
Nada é editado automaticamente no título.
"""
from __future__ import annotations

import re
import unicodedata

POLITICA_VERSAO = "1.0"
NENHUM, MEDIA, ALTA = "nenhum", "media", "alta"

_ALTA = (
    r"garantia|garantido|garantida|original|originais|autentico|autentica|oficial|gratis|gratuito|gratuita",
    r"menor preco|mais barato|mais barata",
    r"melhor|n ?[o°º]? ?1|numero 1|numero um",
    r"anvisa|inmetro",
    r"cura|curar|trata|tratamento|emagrece|emagrecer|emagrecimento",
    r"exclusivo|exclusiva",
    r"oferta|ofertas|desconto|promocao|promocional|\d+ ?% ?off|% ?off",
)
_MEDIA = (
    r"\d+(?:[.,]\d+)? ?(?:mah|gb|tb|w|v|hz|mm|polegadas?|anos?)",
    r"100 ?%",
    r"potente|ultra|profissional",
    r"a prova d ?agua|resistente a agua|ip ?\d{2}",
)
_RE_ALTA = [re.compile(rf"(?<![a-z0-9])(?:{p})(?![a-z0-9])") for p in _ALTA]
_RE_MEDIA = [re.compile(rf"(?<![a-z0-9])(?:{p})(?![a-z0-9])") for p in _MEDIA]


def _normalizar(txt: str) -> str:
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[’'`´]", " ", s)


def avaliar_titulo(titulo: str) -> dict:
    """``{"nivel": nenhum|media|alta, "trechos": [...]}``; os trechos são do título normalizado."""
    n = _normalizar(titulo or "")
    alta = sorted({m.group(0) for r in _RE_ALTA for m in r.finditer(n)})
    media = sorted({m.group(0) for r in _RE_MEDIA for m in r.finditer(n)})
    if alta:
        return {"nivel": ALTA, "trechos": alta + [t for t in media if t not in alta]}
    if media:
        return {"nivel": MEDIA, "trechos": media}
    return {"nivel": NENHUM, "trechos": []}


def identificacao_para_peca(titulo: str, categoria: str | None, loja: str) -> dict:
    """Como identificar o produto em texto público.

    ``acao``: ``usar_titulo`` (nenhum/média; média ainda exige revisão humana), ``variante_sem_titulo`` (ALTA com
    categoria disponível: nome genérico = categoria + loja) ou ``bloquear`` (ALTA sem variante possível).
    """
    av = avaliar_titulo(titulo)
    if av["nivel"] != ALTA:
        return {"acao": "usar_titulo", "texto": titulo, "revisaoHumanaObrigatoria": av["nivel"] == MEDIA, **av}
    if categoria and loja:
        genero = categoria.split(">")[-1].strip()
        return {"acao": "variante_sem_titulo", "texto": f"{genero} na {loja}", "revisaoHumanaObrigatoria": True, **av}
    return {"acao": "bloquear", "texto": None, "revisaoHumanaObrigatoria": True, **av}
