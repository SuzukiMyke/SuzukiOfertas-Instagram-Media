"""Ficha de curadoria manual (entrada humana) e conversão para o objeto de exportação B do contrato 1.1.

A ficha NÃO aceita preço, disponibilidade nem afiliado. O que o receptor 1.1 também valida (URLs, encurtadores, alegações comerciais,
título ALTA) é reaproveitado: depois da conversão o objeto passa por ``produtos.esquema.validar_produto(contrato="1.1")``.
Enquanto ``PRODUTOS_REAIS_HABILITADO`` for ``False``, só domínios reservados para teste (``.example``, ``.invalid``, ``.test``,
``example.com/.net/.org``) são aceitos em ``officialUrl``, ``sourceRef`` e ``referencias[].url``: o bloqueio é por NOME do
domínio, sem consultar a rede.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

from produtos.esquema import (BLOCK_REASON_CURADORIA, FONTE_CURADORIA, PROVIDER_CURADORIA, SISTEMA_CURADORIA, validar_produto)
from produtos.tempo import formatar, parse_data

FICHA_VERSION = "1.0"
PRODUTOS_REAIS_HABILITADO = False                      # NÃO alterar nesta etapa
TLDS_RESERVADOS = ("example", "invalid", "test")
DOMINIOS_RESERVADOS = ("example.com", "example.net", "example.org")
MAX_FATOS = MAX_REFERENCIAS = 20

CAMPOS = ("fichaCuradoriaVersion", "id", "title", "store", "category", "officialUrl", "fatos", "referencias")
OBRIGATORIOS = ("fichaCuradoriaVersion", "id", "title", "store", "officialUrl", "fatos", "referencias")
CAMPOS_FATO = ("text", "sourceRef", "verifiedAt")
CAMPOS_REFERENCIA = ("label", "url")
_COMERCIAIS = ("price", "preco", "amount", "availability", "disponibilidade", "estoque", "stock", "affiliate", "afiliado",
               "desconto", "discount", "frete", "promo", "cupom")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")


class ErroFicha(ValueError):
    """Ficha inválida; ``erros`` lista os problemas (caminho do campo, nunca o valor)."""

    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


def dominio_reservado(host: str) -> bool:
    h = (host or "").lower().rstrip(".")
    return (h.rsplit(".", 1)[-1] in TLDS_RESERVADOS
            or any(h == d or h.endswith("." + d) for d in DOMINIOS_RESERVADOS))


def _nome_comercial(chave: str) -> bool:
    n = unicodedata.normalize("NFKD", str(chave)).encode("ascii", "ignore").decode("ascii").lower()
    return any(c in n for c in _COMERCIAIS)


def _checar_dominio(erros: list[str], caminho: str, url) -> None:
    if PRODUTOS_REAIS_HABILITADO or not isinstance(url, str):
        return
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return                                          # URL malformada: o esquema do receptor a recusa com mensagem própria
    if not dominio_reservado(host):
        erros.append(f"{caminho}: domínio não reservado para teste (produtos reais estão desabilitados)")


def ler_ficha(obj, agora: datetime) -> dict:
    """Valida a ficha humana. Devolve a ficha normalizada ou levanta ``ErroFicha``."""
    erros: list[str] = []
    if not isinstance(obj, dict):
        raise ErroFicha(["(raiz): a ficha deve ser um objeto JSON"])
    for k in obj:
        if _nome_comercial(k):
            erros.append(f"{str(k)[:40]}: campo comercial proibido na ficha de curadoria (preço, disponibilidade e afiliado não entram)")
        elif k not in CAMPOS:
            erros.append(f"{str(k)[:40]}: campo desconhecido")
    for k in OBRIGATORIOS:
        if k not in obj:
            erros.append(f"{k}: campo obrigatório ausente")
    if obj.get("fichaCuradoriaVersion", FICHA_VERSION) != FICHA_VERSION:
        erros.append("fichaCuradoriaVersion: versão não suportada")
    pid = obj.get("id")
    if "id" in obj and not (isinstance(pid, str) and _ID.match(pid)):
        erros.append("id: inválido (letras, dígitos, '.', '_' e '-'; até 64)")
    for campo, lim in (("title", 240), ("store", 120)):
        v = obj.get(campo)
        if campo in obj and not (isinstance(v, str) and v.strip() and len(v) <= lim):
            erros.append(f"{campo}: esperado texto não vazio de até {lim} caracteres")
    cat = obj.get("category")
    if cat is not None and not (isinstance(cat, str) and cat.strip() and len(cat) <= 200):
        erros.append("category: esperado texto não vazio de até 200 caracteres (ou ausente)")
    _checar_dominio(erros, "officialUrl", obj.get("officialUrl"))

    fatos = obj.get("fatos")
    if "fatos" in obj:
        if not isinstance(fatos, list) or not 1 <= len(fatos) <= MAX_FATOS:
            erros.append(f"fatos: esperada lista de 1 a {MAX_FATOS} itens")
        else:
            for i, f in enumerate(fatos):
                c = f"fatos[{i}]"
                if not isinstance(f, dict):
                    erros.append(f"{c}: esperado objeto")
                    continue
                for k in f:
                    if k not in CAMPOS_FATO:
                        erros.append(f"{c}.{str(k)[:40]}: campo desconhecido")
                for k in CAMPOS_FATO:
                    if k not in f:
                        erros.append(f"{c}.{k}: campo obrigatório ausente")
                dt = parse_data(f.get("verifiedAt"))
                if "verifiedAt" in f and dt is None:
                    erros.append(f"{c}.verifiedAt: data UTC inválida (AAAA-MM-DDTHH:MM:SSZ)")
                elif dt is not None and dt > agora:
                    erros.append(f"{c}.verifiedAt: data no futuro")
                _checar_dominio(erros, f"{c}.sourceRef", f.get("sourceRef"))
    refs = obj.get("referencias")
    if "referencias" in obj:
        if not isinstance(refs, list) or len(refs) > MAX_REFERENCIAS:
            erros.append(f"referencias: esperada lista de até {MAX_REFERENCIAS} itens")
        else:
            for i, r in enumerate(refs):
                c = f"referencias[{i}]"
                if not isinstance(r, dict):
                    erros.append(f"{c}: esperado objeto")
                    continue
                for k in r:
                    if k not in CAMPOS_REFERENCIA:
                        erros.append(f"{c}.{str(k)[:40]}: campo desconhecido")
                for k in CAMPOS_REFERENCIA:
                    if k not in r:
                        erros.append(f"{c}.{k}: campo obrigatório ausente")
                _checar_dominio(erros, f"{c}.url", r.get("url"))
    if erros:
        raise ErroFicha(erros)
    return obj


def para_exportacao(ficha: dict, export_id: str, agora: datetime) -> dict:
    """Objeto de exportação B (contrato 1.1): preço nulo, disponibilidade desconhecida, nada publicado nem elegível."""
    return {
        "schemaVersion": "1.0.0", "exportId": export_id, "exportedAt": formatar(agora),
        "source": {"kind": FONTE_CURADORIA, "system": SISTEMA_CURADORIA},
        "product": {"id": ficha["id"], "provider": PROVIDER_CURADORIA, "store": ficha["store"], "title": ficha["title"],
                    "category": ficha.get("category"), "categoryOrigin": "derivada_revisada" if ficha.get("category") else None,
                    "officialUrl": ficha["officialUrl"], "affiliateUrl": None},
        "price": {"amountCents": None, "currency": "BRL", "originalAmountCents": None, "verifiedAt": None, "validUntil": None,
                  "verification": "desconhecida"},
        "availability": "unknown",
        "verifiedFacts": [{"text": f["text"], "sourceRef": f["sourceRef"], "verifiedAt": f["verifiedAt"]} for f in ficha["fatos"]],
        "publication": {"state": "nao_publicada", "publishedAt": None, "channel": None},
        "references": [{"label": r["label"], "url": r["url"]} for r in ficha["referencias"]],
        "eligibility": {"agentPublicationEligible": False, "blockReason": BLOCK_REASON_CURADORIA},
    }


def validar_exportacao(obj: dict, agora: datetime) -> list[str]:
    """Erros do receptor 1.1 para o objeto convertido (lista vazia = aceito)."""
    r = validar_produto(obj, agora, contrato="1.1")
    return [] if r.ok else list(r.erros)
