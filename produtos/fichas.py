"""Fichas de produto (GOAL 5.6): JSON + Markdown a partir do dado JÁ VALIDADO.

A ficha é montada campo a campo (lista de permissão); o objeto bruto nunca é copiado, de modo que
nada proibido pode vazar para a ficha.
"""
from __future__ import annotations

import re
from datetime import datetime

from . import FICHA_VERSION, estados
from .avaliacao import Avaliacao
from .esquema import FONTE_A
from .fotos import situacao_foto
from .registro import Produto

AVISO_PRECO = "O preço pode mudar; confira a oferta no momento da publicação."
AVISO_PRECO_VIDEO = "Preço fora do vídeo; se citado, apenas na legenda, com o aviso de que pode mudar."
_MD_ESPECIAIS = re.compile(r"([\\`*_{}\[\]<>()#+!|~])")


def reais(centavos: int) -> str:
    inteiro, frac = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{frac:02d}"


def _md(txt) -> str:
    return _MD_ESPECIAIS.sub(r"\\\1", str(txt)).replace("\n", " ")


def nome_arquivo(provider: str, product_id: str) -> str:
    return f"{provider}__{product_id}"


def montar(produto: Produto, av: Avaliacao, agora: datetime) -> dict:
    v = produto.vigente
    d = v.dados
    origem = "A" if d["source"]["kind"] == FONTE_A else "B"
    foto = situacao_foto(d["photo"])
    avisos = [AVISO_PRECO, AVISO_PRECO_VIDEO]
    if foto["aviso"]:
        avisos.append(foto["aviso"])
    if origem == "B":
        avisos.append("Origem B: candidato de catálogo/API, sem verificação ao vivo, sem aprovação e não publicado pelo agente.")
    if d["availability"] == "unknown":
        avisos.append("Disponibilidade desconhecida na fonte.")
    if d["product"]["category"] is None:
        avisos.append("Categoria ausente: classificação manual ou derivada necessária (marcar como derivada_revisada).")
    if av.mudanca_de_preco:
        avisos.append(f"Preço mudou em relação à versão anterior ({reais(av.mudanca_de_preco['de'])} -> {reais(av.mudanca_de_preco['para'])}).")
    if av.aprovacao_invalidada_por_preco:
        avisos.append("Aprovação anterior INVALIDADA por mudança de preço; nova revisão humana necessária.")
    if av.estado == estados.APROVADO_PUBLICACAO:
        avisos.append("aprovado_para_publicacao apenas registra a autorização; publicar/agendar exige autorização própria, fora deste fluxo.")

    ficha = {
        "fichaVersion": FICHA_VERSION,
        "geradoEm": agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "produto": {
            "provider": d["product"]["provider"], "id": d["product"]["id"], "store": d["product"]["store"],
            "title": d["product"]["title"], "category": d["product"]["category"],
            "categoryOrigin": d["product"]["categoryOrigin"], "officialUrl": d["product"]["officialUrl"],
            "affiliateUrl": d["product"]["affiliateUrl"],
        },
        "origem": origem,
        "fonte": d["source"]["kind"],
        "preco": {
            "amountCents": d["price"]["amountCents"], "currency": d["price"]["currency"],
            "exibicao": reais(d["price"]["amountCents"]),
            "originalAmountCents": d["price"]["originalAmountCents"],
            "verifiedAt": d["price"]["verifiedAt"], "validUntil": d["price"]["validUntil"],
            "verification": d["price"]["verification"],
        },
        "availability": d["availability"],
        "foto": foto,
        "verifiedFacts": d["verifiedFacts"],
        "publicacaoNoAgente": d["publication"],
        "references": d["references"],
        "elegibilidadeAgente": d["eligibility"],
        "estado": av.estado,
        "estadoAutomatico": av.estado_automatico,
        "motivoEstadoAutomatico": av.motivo_automatico,
        "pendencias": av.pendencias,
        "avisos": avisos,
        "decisaoHumana": av.decisao_aplicada.como_dict() if av.decisao_aplicada else None,
        "decisoesIgnoradas": av.decisoes_ignoradas,
        "aprovacaoInvalidadaPorPreco": av.aprovacao_invalidada_por_preco,
        "eventos": av.eventos,
        "versao": {"exportId": v.export_id, "exportedAt": d["exportedAt"], "arquivo": v.arquivo, "sha256": v.sha256,
                   "versoesConhecidas": len(produto.versoes)},
    }
    if not foto["utilizavel"]:
        ficha["dadosInsuficientes"] = ["foto autorizada"]
    return ficha


def para_markdown(f: dict) -> str:
    p, pr, foto = f["produto"], f["preco"], f["foto"]
    L = [f"# {_md(p['title'])}", "",
         f"**Estado:** `{f['estado']}` · **Origem:** {f['origem']} (`{f['fonte']}`) · **Loja:** {_md(p['store'])}", "",
         "## Dados verificados",
         f"- Preço informado: {pr['exibicao']} ({pr['currency']}) — verificação: `{pr['verification']}`"
         + (f", verificado em {pr['verifiedAt']}, válido até {pr['validUntil']}" if pr["verifiedAt"] else " (sem verificação)"),
         f"- Disponibilidade: `{f['availability']}`",
         f"- Categoria: {_md(p['category']) if p['category'] else '(ausente)'}"
         + (f" (`{p['categoryOrigin']}`)" if p["categoryOrigin"] else ""),
         f"- Link oficial: {p['officialUrl']}",
         f"- Link de afiliado: {p['affiliateUrl'] or '(não há)'}"]
    if f["verifiedFacts"]:
        L += ["", "### Características comprovadas"]
        L += [f"- {_md(x['text'])} (fonte: {_md(x['sourceRef'])}, em {x['verifiedAt']})" for x in f["verifiedFacts"]]
    L += ["", "## Foto",
          f"- Permissão de uso: `{foto['usePermission']}` · utilizável: **{'sim' if foto['utilizavel'] else 'não'}**",
          f"- Origem: `{foto['origin']}` · URL: {foto['url'] or '(nenhuma)'}",
          f"- Referência da permissão: {_md(foto['permissionRef']) if foto['permissionRef'] else '(nenhuma)'}"]
    if f["references"]:
        L += ["", "## Referências"] + [f"- {_md(r['label'])}: {r['url']}" for r in f["references"]]
    L += ["", "## Avisos"] + [f"- {_md(a)}" for a in f["avisos"]]
    if f["pendencias"]:
        L += ["", "## Pendências"] + [f"- {_md(x)}" for x in f["pendencias"]]
    L += ["", "## Estado e decisões", f"- Estado automático: `{f['estadoAutomatico']}` — {_md(f['motivoEstadoAutomatico'])}"]
    h = f["decisaoHumana"]
    L.append(f"- Decisão humana aplicada: " + (f"`{h['decisao']}` por {_md(h['autor'])} em {h['data']} — {_md(h['motivo'])}" if h else "nenhuma"))
    for i in f["decisoesIgnoradas"]:
        L.append(f"- Decisão ignorada (`{i['decisao']}`): {_md(i['ignoradaPorque'])}")
    L += ["", "## Versão", f"- exportId `{f['versao']['exportId']}` · exportado em {f['versao']['exportedAt']} · arquivo `{_md(f['versao']['arquivo'])}`",
          f"- Versões conhecidas do produto: {f['versao']['versoesConhecidas']}", ""]
    return "\n".join(L)
