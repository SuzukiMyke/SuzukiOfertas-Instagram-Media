"""Impressões digitais MATERIAIS para a invalidação seletiva de aprovações (contrato v1.1 §17.4, DT-20, P-08). Módulo novo.

Uma aprovação humana é ligada a uma versão (``exportId``) e NÃO é invalidada porque surgiu uma nova exportação: só quando
algo **material para aquele tipo de decisão** mudou entre a versão revisada e a versão vigente da mesma fonte.

Componentes materiais por tipo de decisão (cada um com o seu código de invalidação):

| componente          | campos                                                    | código                    | rascunho | publicação |
|---------------------|-----------------------------------------------------------|---------------------------|:--------:|:----------:|
| identidade          | ``title``, ``store``, ``officialUrl``                     | ``identidade_mudou``      | sim      | sim        |
| fonte               | ``source.kind`` (agente_publicada, catalogo_candidato…)   | ``fonte_mudou``           | sim      | sim        |
| fatos               | conjunto dos textos de ``verifiedFacts`` (normalizados)   | ``fatos_mudaram``         | sim      | sim        |
| fonte_comprovacao   | ``sourceRef`` de cada fato (normalizado)                  | ``fonte_comprovacao_mudou`` | sim    | sim        |
| preco               | ``amountCents``, ``currency``, ``originalAmountCents``    | ``preco_mudou``           | não      | sim (A)    |
| disponibilidade     | ``availability``                                          | ``disponibilidade_mudou`` | não      | sim (A)    |

A divergência A × B (``divergencia_ab_alterada``) é tratada à parte: a aprovação continua válida se o conjunto atual de
campos divergentes for IGUAL ou SUBCONJUNTO do que existia na revisão; um campo novo divergente a invalida.

**Não entram** na impressão: ``exportId``, ``exportedAt``, ``verifiedAt`` (de preço e de fatos), ``validUntil``, ``checkedAt``,
referências, publicação e demais metadados que mudam a cada reexportação sem mudança material. O prazo de 30 dias dos fatos e a
janela de 24 h do preço seguem regras próprias (§5/§6) e **não** são estendidos por uma aprovação.
Aprovação editorial NÃO é validade comercial: mudança de preço/disponibilidade não invalida rascunho e, em publicação, continua
sujeita ao portão de pré-publicação.

A impressão é determinística: JSON canônico (chaves ordenadas), conjuntos ordenados, texto normalizado (NFKC, espaços
colapsados, caixa baixa); a ordem dos campos e das listas do arquivo exportado não altera o resultado. Decisões NÃO guardam
impressão (``decisoes.json`` não muda): ela é recalculada da versão revisada na leitura. Sem a versão revisada nas fontes
lidas não há impressão comparável → a decisão fica inaplicável de forma conservadora e registrada (``versao_desconhecida``).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from . import estados
from .registro import Versao

IMPRESSAO_VERSAO = "1.0"
COMPONENTES_EDITORIAL = ("identidade", "fonte", "fatos", "fonte_comprovacao")
COMPONENTES_PUBLICACAO = COMPONENTES_EDITORIAL + ("preco", "disponibilidade")
CODIGO = {"identidade": "identidade_mudou", "fonte": "fonte_mudou", "fatos": "fatos_mudaram",
          "fonte_comprovacao": "fonte_comprovacao_mudou", "preco": "preco_mudou", "disponibilidade": "disponibilidade_mudou"}
CODIGOS_IMPRESSAO = tuple(CODIGO.values()) + ("divergencia_ab_alterada",)
_ESPACOS = re.compile(r"\s+")


def _n(txt) -> str:
    return _ESPACOS.sub(" ", unicodedata.normalize("NFKC", str(txt)).strip()).casefold()


def componentes_do_tipo(tipo: str) -> tuple[str, ...]:
    if tipo == estados.APROVADO_RASCUNHO:
        return COMPONENTES_EDITORIAL
    if tipo == estados.APROVADO_PUBLICACAO:
        return COMPONENTES_PUBLICACAO
    raise ValueError("somente aprovações têm impressão material (rejeição não depende de versão)")


def valores(v: Versao, tipo: str) -> dict:
    """Valores materiais normalizados (já em forma canônica: listas ordenadas, textos normalizados)."""
    d = v.dados
    p, preco = d["product"], d["price"]
    out = {
        "identidade": {"title": _n(p["title"]), "store": _n(p["store"]), "officialUrl": str(p["officialUrl"]).strip()},
        "fonte": d["source"]["kind"],
        "fatos": sorted({_n(f["text"]) for f in d["verifiedFacts"]}),
        "fonte_comprovacao": sorted({(_n(f["text"]), _n(f["sourceRef"])) for f in d["verifiedFacts"]}),
        "preco": {"amountCents": preco["amountCents"], "currency": preco["currency"],
                  "originalAmountCents": preco["originalAmountCents"]},
        "disponibilidade": d["availability"],
    }
    return {k: out[k] for k in componentes_do_tipo(tipo)}


def impressao(v: Versao, tipo: str) -> str:
    """SHA-256 do JSON canônico dos componentes materiais do tipo de decisão."""
    corpo = {"v": IMPRESSAO_VERSAO, "tipo": tipo, "componentes": valores(v, tipo)}
    return hashlib.sha256(json.dumps(corpo, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def diferencas(revisada: Versao, atual: Versao, tipo: str) -> list[dict]:
    """Componentes materiais que mudaram: ``[{"codigo", "componente", "campos"}]`` na ordem fixa dos componentes."""
    a, b = valores(revisada, tipo), valores(atual, tipo)
    out = []
    for c in componentes_do_tipo(tipo):
        if a[c] == b[c]:
            continue
        if isinstance(a[c], dict):
            campos = sorted(k for k in a[c] if a[c][k] != b[c][k])
        elif c == "fonte_comprovacao":
            campos = ["sourceRef"]
        else:
            campos = [c]
        out.append({"codigo": CODIGO[c], "componente": c, "campos": campos})
    # fatos e fonte de comprovação: se o texto do fato mudou, a fonte do par também difere; só reporta a de comprovação
    # separadamente quando o conjunto de textos é o mesmo (a fonte de um fato existente mudou).
    if any(x["componente"] == "fatos" for x in out):
        out = [x for x in out if x["componente"] != "fonte_comprovacao"]
    return out


def divergencias_campos(va: Versao, vb: Versao) -> list[str]:
    """Campos divergentes entre uma versão de A e uma de B (identidade e conjunto de fatos; DT-19: sem ``modelo``)."""
    ia = {"title": va.dados["product"]["title"], "store": va.dados["product"]["store"],
          "officialUrl": va.dados["product"]["officialUrl"]}
    ib = {"title": vb.dados["product"]["title"], "store": vb.dados["product"]["store"],
          "officialUrl": vb.dados["product"]["officialUrl"]}
    campos = [k for k in ("title", "store", "officialUrl") if ia[k] != ib[k]]
    fa = sorted({f["text"].strip().lower() for f in va.dados["verifiedFacts"]})
    fb = sorted({f["text"].strip().lower() for f in vb.dados["verifiedFacts"]})
    if (fa or fb) and fa != fb:
        campos.append("verifiedFacts")
    return campos


def _url(u) -> str:
    """URL normalizada só para comparar (formatação não é mudança): esquema/host em caixa baixa, porta padrão, barra final e
    fragmento ignorados. O caminho e a consulta continuam sensíveis a maiúsculas."""
    try:
        x = urlsplit(str(u).strip())
        host = (x.hostname or "").lower()
        if x.port and not ((x.scheme == "https" and x.port == 443) or (x.scheme == "http" and x.port == 80)):
            host += f":{x.port}"
        return urlunsplit((x.scheme.lower(), host, x.path.rstrip("/") or "/", x.query, ""))
    except ValueError:
        return str(u).strip()


def divergencias_itens(va: Versao, vb: Versao) -> dict[str, tuple]:
    """Itens divergentes entre A e B no MESMO critério de ``divergencias_campos`` (comparação textual exata, DT-19), mas cada item
    carrega o par de VALORES já normalizado (NFKC, espaços, caixa; URL sem formatação). Serve para reconhecer mudança
    material do valor divergente sem reagir a formatação."""
    pa, pb = va.dados["product"], vb.dados["product"]
    itens: dict[str, tuple] = {}
    for campo in divergencias_campos(va, vb):
        if campo == "verifiedFacts":
            itens[campo] = (tuple(sorted({_n(f["text"]) for f in va.dados["verifiedFacts"]})),
                            tuple(sorted({_n(f["text"]) for f in vb.dados["verifiedFacts"]})))
        elif campo == "officialUrl":
            itens[campo] = (_url(pa[campo]), _url(pb[campo]))
        else:
            itens[campo] = (_n(pa[campo]), _n(pb[campo]))
    return itens


def divergencia_alterada_itens(na_revisao: dict[str, tuple], atuais: dict[str, tuple]) -> dict[str, str]:
    """Campos cuja divergência atual NÃO estava revisada: ``{"campo": "novo" | "valor_alterado"}``.
    Igual ou subconjunto (redução) continua válido; mesmo campo com par de valores materialmente diferente é ``valor_alterado``."""
    out = {}
    for campo, par in atuais.items():
        if campo not in na_revisao:
            out[campo] = "novo"
        elif na_revisao[campo] != par:
            out[campo] = "valor_alterado"
    return out


def divergencia_alterada(campos_na_revisao: list[str], campos_atuais: list[str]) -> list[str]:
    """Campos divergentes NOVOS (atuais que não existiam na revisão); vazio = igual ou subconjunto = continua válida."""
    return sorted(set(campos_atuais) - set(campos_na_revisao))


def versao_na_data(produto, quando) -> Versao | None:
    """Versão mais recente do produto exportada até ``quando`` (inclusive); ``None`` se ainda não existia."""
    cand = [v for v in produto.versoes if v.exportada_em <= quando]
    return max(cand, key=lambda v: (v.exportada_em, v.export_id)) if cand else None
