"""Regras adicionais da fonte ``curadoria_manual`` (contrato v1.1, GOAL 5.14-B1). Módulo novo; só modo 1.1.

A curadoria manual é uma fonte do tipo B feita por pessoa: sem preço, sem disponibilidade, sem afiliado e sem alegação comercial.
Este módulo concentra o que o ``esquema`` não tinha: encurtadores e origens não verificáveis (por NOME do host, sem consultar a
rede nem resolver redirecionamentos) e a detecção de alegações comerciais em títulos e fatos.

Limitações registradas (heurística textual, sem rede):
- falso positivo: palavras comerciais usadas em sentido técnico ("garantia" de fabricante, "oferta" de energia) são recusadas;
- falso negativo: alegação comercial escrita de forma criativa, com erro de grafia ou em outro idioma passa; a revisão humana
  continua obrigatória;
- a lista de encurtadores é finita; um host de redirecionamento desconhecido passa pelo esquema;
- uma URL HTTPS válida e fora das listas NÃO prova que o conteúdo é verdadeiro nem que a página é oficial.
"""
from __future__ import annotations

import re
import unicodedata

from .politica_titulos import ALTA, avaliar_titulo

ENCURTADORES = frozenset({
    "bit.ly", "bitly.com", "t.co", "tinyurl.com", "tiny.cc", "goo.gl", "ow.ly", "is.gd", "v.gd", "buff.ly", "cutt.ly",
    "rebrand.ly", "shorturl.at", "rb.gy", "t.ly", "u.to", "bit.do", "clck.ru", "lnkd.in", "fb.me", "amzn.to", "a.co",
    "shp.ee", "s.shopee.com.br", "s.click.aliexpress.com", "mercadolivre.com.br/sec", "link.tree", "linktr.ee", "l.instagram.com",
    "lnk.bio", "tr.ee", "short.io", "soo.gd", "qr.ae", "wp.me", "dlvr.it", "ift.tt", "trib.al", "po.st", "adf.ly",
})

# categoria -> padrão (sobre o texto normalizado: sem acento, caixa baixa)
COMERCIAIS = {
    "preco": r"r\$|\breais\b|\d\s*reais|\bpreco\b|\bvalor promocional\b|\bpor apenas\b|\bapenas r",
    "desconto_promocao": r"desconto|\bpromo\b|promocao|promocional|\boferta\b|\bofertas\b|liquidacao|cupom|black friday|imperdivel|queima de estoque",
    "frete_gratis": r"frete gratis|frete gratuito|entrega gratis|entrega gratuita|\bfrete\b.{0,12}\bgratis",
    "estoque_disponibilidade": r"\bestoque\b|\bdisponivel\b|\bdisponibilidade\b|\besgotad[oa]s?\b|ultimas? unidades?|em falta",
    "urgencia": r"\bcorra\b|so hoje|apenas hoje|ultimo dia|ate acabar|tempo limitado|acaba (?:hoje|amanha)|\burgente\b|aproveite ja",
    "menor_preco": r"menor preco|mais barato|mais barata|preco baixo|preco imbativel",
    "percentual_promocional": r"\d+\s*%\s*(?:off|de desconto|desc\b)|\boff\b",
}
_COMP = {k: re.compile(v) for k, v in COMERCIAIS.items()}


def _norm(txt: str) -> str:
    s = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip()


def host_encurtador(host: str) -> bool:
    """``True`` se o host (ou um sufixo dele) é de encurtador/redirecionador conhecido."""
    h = (host or "").lower().rstrip(".")
    return any(h == e.split("/")[0] or h.endswith("." + e.split("/")[0]) for e in ENCURTADORES if "/" not in e)


def host_nao_verificavel(host: str) -> str | None:
    """Motivo se a procedência do host não é verificável pelo NOME (sem rede); ``None`` se passa."""
    h = (host or "").lower().rstrip(".")
    if host_encurtador(h):
        return "encurtador/redirecionador conhecido"
    if any(lab.startswith("xn--") for lab in h.split(".")):
        return "domínio internacionalizado (punycode): procedência não verificável"
    if re.fullmatch(r"[0-9.]+|[0-9a-f:]+", h):
        return "endereço IP"
    return None


def alegacoes_comerciais(texto: str) -> list[str]:
    """Categorias de alegação comercial encontradas (ordem fixa); lista vazia se nenhuma."""
    n = _norm(texto)
    return [cat for cat, rx in _COMP.items() if rx.search(n)]


def avaliar_titulo_curadoria(titulo: str) -> tuple[list[str], list[str]]:
    """``(erros, avisos)`` para o título: ALTA e alegação comercial rejeitam; MÉDIA só avisa. Não ecoa o texto."""
    erros, avisos = [], []
    t = avaliar_titulo(titulo)
    comerciais = alegacoes_comerciais(titulo)
    if comerciais:
        erros.append("título com alegação comercial proibida em curadoria (" + ", ".join(comerciais) + ")")
    if t["nivel"] == ALTA:
        erros.append("título com termo de risco ALTA (não pode ser texto público)")
    elif t["nivel"] == "media":
        avisos.append("título com termo de risco MÉDIA: não é fato verificado; revisão humana obrigatória")
    return erros, avisos


def avaliar_fato_curadoria(texto: str) -> tuple[list[str], list[str]]:
    """``(erros, avisos)`` para um fato: alegação comercial rejeita; ALTA/MÉDIA só avisam (ex.: garantia técnica)."""
    erros, avisos = [], []
    comerciais = alegacoes_comerciais(texto)
    if comerciais:
        erros.append("fato com alegação comercial proibida em curadoria (" + ", ".join(comerciais) + ")")
    nivel = avaliar_titulo(texto)["nivel"]
    if nivel == ALTA and not comerciais:
        avisos.append("fato com termo de risco ALTA: ficará fora de textos públicos; revisão humana")
    elif nivel == "media":
        avisos.append("fato com termo de risco MÉDIA: revisão humana obrigatória")
    return erros, avisos
