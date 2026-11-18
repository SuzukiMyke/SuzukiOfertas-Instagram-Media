"""Fichas do modo 1.1 (contrato v1.1). Parte da ficha 1.0 e a ajusta; ``fichas`` (1.0) não muda."""
from __future__ import annotations

import copy
from datetime import datetime

from . import FICHA_VERSION_V11, estados
from . import fichas
from .avaliacao_v11 import AvaliacaoV11
from .politica_titulos import identificacao_para_peca
from .registro import Produto

AVISO_B_PRECO = "Origem B: o preço é referência NÃO verificada; não aparece em conteúdo, legenda ou vídeo."
AVISO_SEM_VERIFICACAO = ("Não há verificação do preço no momento da publicação (capacidade reservada, inexistente): "
                         "vale apenas a janela declarada no arquivo exportado.")


def montar_v11(produto: Produto, av: AvaliacaoV11, agora: datetime) -> dict:
    f = fichas.montar(produto, av, agora)
    exportada = f["foto"]
    h = av.foto
    if exportada["aviso"] in f["avisos"]:
        f["avisos"].remove(exportada["aviso"])
    f["foto"] = {
        "url": exportada["url"], "origin": exportada["origin"],
        "usePermission": exportada["usePermission"],
        "usePermissionObservacao": "informativa no contrato 1.1; NÃO concede uso (só registro humano com hash)",
        "permissionRef": h.get("termoId"), "checkedAt": None,
        "utilizavel": bool(h.get("utilizavel")), "fotoSha256": h.get("fotoSha256"), "termoId": h.get("termoId"),
        "motivo": h.get("motivo"),
        "aviso": None if h.get("utilizavel") else "sem foto autorizada: " + (h.get("motivo") or "sem registro humano"),
    }
    if f["foto"]["aviso"]:
        f["avisos"].append(f["foto"]["aviso"])
        f["dadosInsuficientes"] = ["foto autorizada"]
    else:
        f.pop("dadosInsuficientes", None)
    f["fichaVersion"] = FICHA_VERSION_V11
    f["contrato"] = "1.1"
    v1_b = "Origem B: candidato de catálogo/API, sem verificação ao vivo, sem aprovação e não publicado pelo agente."
    if v1_b in f["avisos"]:
        f["avisos"][f["avisos"].index(v1_b)] = ("Origem B: candidato de catálogo/API, sem verificação ao vivo e não publicado "
                                                "pelo agente; só rascunho editorial (nunca publicação).")
    if av.origem == "B":
        f["preco"]["exibicao"] = None
        f["avisos"].append(AVISO_B_PRECO)
        f["alegacaoComercialPermitida"] = False
    elif av.fonte_comercial and av.fonte_comercial["alegacaoComercialPermitida"] is False:
        f["alegacaoComercialPermitida"] = False
    else:
        f["alegacaoComercialPermitida"] = "somente pelo portão de pré-publicação (prepublicacao.avaliar_portao)"
    f["avisos"].append(AVISO_SEM_VERIFICACAO)
    ident = identificacao_para_peca(f["produto"]["title"], f["produto"]["category"], f["produto"]["store"])
    f["avisoTitulo"] = ident["nivel"]
    f["trechosTitulo"] = ident["trechos"]
    f["identificacaoPeca"] = {k: ident[k] for k in ("acao", "texto", "revisaoHumanaObrigatoria")}
    if ident["nivel"] == "alta":
        f["avisos"].append("Título com termo de nível ALTA: não usar o título em texto público (variante genérica ou bloqueio).")
    elif ident["nivel"] == "media":
        f["avisos"].append("Título com termo de nível MÉDIA: não é fato verificado; revisão humana obrigatória.")
    f["fatosParaUso"] = av.fatos_para_uso
    f["fatosEmRevisao"] = av.fatos_em_revisao
    f["regraDeFatosDormente"] = not f["verifiedFacts"]
    f["mudancaDeIdentidade"] = av.mudanca_identidade
    f["aprovacaoInvalidadaPorIdentidade"] = av.aprovacao_invalidada_por_identidade
    if av.aprovacao_invalidada_por_identidade:
        f["avisos"].append("Aprovação anterior INVALIDADA por mudança de identidade; nova revisão humana necessária.")
    f["fonteSelecionada"] = av.fonte_selecionada or av.origem
    f["divergenciasAB"] = av.divergencias_ab
    f["fonteComercial"] = av.fonte_comercial
    f["editorialB"] = av.editorial_b
    f["decisoesInaplicaveis"] = av.decisoes_inaplicaveis
    f["impressaoMaterialDecisao"] = av.impressao_decisao
    f["invalidacoesMateriais"] = av.invalidacoes_materiais
    if av.divergencias_ab:
        f["avisos"].append("Divergência A × B em " + ", ".join(av.divergencias_ab["campos"]) + ": revisão humana obrigatória.")
    if av.fonte_comercial and av.fonte_comercial["estadoAutomatico"] == "expirado":
        f["avisos"].append("Fonte A expirada: nenhuma alegação comercial; ficha sustentada por B apenas como rascunho editorial.")
    for d in av.decisoes_inaplicaveis:
        f["avisos"].append(f"Decisão humana INAPLICÁVEL ({d['codigo']}): {d['motivo']} [exportId {d['exportId'][:8]}…, "
                           f"{d['decisao']}, {d['autor']}, {d['data']}]")
    return f


def para_markdown_v11(f: dict) -> str:
    c = copy.deepcopy(f)
    c["foto"]["usePermission"] = f"{c['foto']['usePermission']} (informativo; não concede uso)"
    if c["preco"]["exibicao"] is None:
        c["preco"]["exibicao"] = "(referência NÃO verificada; não usar em conteúdo)"
    corpo = fichas.para_markdown(c)
    extra = ["", "## Contrato 1.1",
             f"- Aviso de título: `{f['avisoTitulo']}`" + (f" (trechos: {', '.join(f['trechosTitulo'])})" if f["trechosTitulo"] else ""),
             f"- Identificação em peça pública: `{f['identificacaoPeca']['acao']}`",
             f"- Fatos para uso: {len(f['fatosParaUso'])} · fatos em revisão: {len(f['fatosEmRevisao'])}"
             + (" (regra dormente: sem fonte de fatos)" if f["regraDeFatosDormente"] else ""),
             f"- Foto: utilizável **{'sim' if f['foto']['utilizavel'] else 'não'}**"
             + (f" — {f['foto']['motivo']}" if f["foto"]["motivo"] else ""),
             f"- Fonte que sustenta a ficha: `{f['fonteSelecionada']}`"
             + (f" · divergências A × B: {', '.join(f['divergenciasAB']['campos'])}" if f["divergenciasAB"] else "")]
    extra += [f"- Decisão inaplicável (`{d['codigo']}`): {d['motivo']}" for d in f["decisoesInaplicaveis"]]
    extra.append("")
    return "> Ficha do modo 1.1 (especificação aprovada; não validada em serviço real nem aprovada para produção).\n\n" \
        + corpo + "\n".join(extra)
