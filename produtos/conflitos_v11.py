"""Política de conflitos A × B e registro explícito de decisões inaplicáveis (contrato v1.1 §16.3; P-03 e P-04). Módulo novo.

Regras (nenhuma fonte substitui decisão humana nem permissão de foto; nada concede aprovação):
1. **A só prevalece nas informações comerciais enquanto a verificação é válida** (``min(validUntil, verifiedAt + 24 h)``).
   Se a versão vigente de A está **expirada**, a ficha passa a ser sustentada por **B** (``candidato_nao_verificado``,
   rascunho editorial, sem alegação comercial); A não é apagada: aparece em ``fonteComercial`` como não utilizável.
   Se A é inválida por indisponibilidade, a ficha continua em A (``invalidado``): produto indisponível não recai em B.
2. **B continua fornecendo dados editoriais** (título, loja, categoria, URL oficial) ao lado de A em ``editorialB``;
   nada de B sobrescreve dado de A (a categoria de B é apenas sugestão visível).
3. **Divergência de identificação (título, loja, URL oficial) ou de características (conjunto de ``verifiedFacts``)
   entre as versões vigentes de A e B exige revisão**: estado ``pendente_revisao`` com os campos divergentes. A
   aprovação humana feita já com a divergência continua válida se o conjunto atual de campos divergentes for igual ou subconjunto do existente na revisão
   (``divergencia_ab_alterada`` quando surge campo novo; P-08, ``impressao_v11``). Nova exportação sem alteração material NÃO invalida.
   O formato exportado não tem campo de "modelo"; a comparação de modelo fica restrita a título e características.
4. **Decisão humana que deixa de ser aplicável nunca some em silêncio**: cada uma entra em ``decisoesInaplicaveis`` com um
   código (``fonte_nao_selecionada``, ``versao_desconhecida``, ``identidade_mudou``,
   ``preco_mudou``, ``estado_nao_permite``, ``fonte_b_sem_publicacao``, ``data_futura``, ``anterior_a_exportacao``,
   ``superada_por_decisao_mais_recente``) e, desde P-08, ``fatos_mudaram``, ``fonte_comprovacao_mudou``,
   ``disponibilidade_mudou``, ``fonte_mudou`` e ``divergencia_ab_alterada`` e motivo. Rejeição humana vale para o produto mesmo se registrada sobre a outra fonte.
"""
from __future__ import annotations

import json
from datetime import datetime

from . import estados
from . import impressao_v11 as imp
from .avaliacao_v11 import AvaliacaoV11, ConfiguracaoV11, _aplicar, _fmt, avaliar_v11, estado_automatico_v11
from .decisoes import Decisao
from .prepublicacao import janela_comercial
from .registro import Produto, Versao

CODIGOS = ("fonte_nao_selecionada", "versao_desconhecida", "identidade_mudou", "preco_mudou", "fatos_mudaram",
           "fonte_comprovacao_mudou", "disponibilidade_mudou", "fonte_mudou", "divergencia_ab_alterada", "estado_nao_permite",
           "fonte_b_sem_publicacao", "data_futura", "anterior_a_exportacao", "superada_por_decisao_mais_recente",
           "produto_ausente")


def comparar_ab(va: Versao, vb: Versao) -> dict | None:
    campos = imp.divergencias_campos(va, vb)
    return {"campos": campos, "exportIdA": va.export_id, "exportIdB": vb.export_id} if campos else None


def _editorial(v: Versao) -> dict:
    p = v.dados["product"]
    return {"exportId": v.export_id, "title": p["title"], "store": p["store"], "category": p["category"],
            "categoryOrigin": p["categoryOrigin"], "officialUrl": p["officialUrl"]}


def _inaplicaveis(decisoes: list[Decisao], av: AvaliacaoV11, pre: dict) -> list[dict]:
    ign = {(i["exportId"], i["decisao"], i["data"]): i for i in av.decisoes_ignoradas}
    out = []
    for d in decisoes:
        if av.decisao_aplicada is d:
            continue
        k = (d.export_id, d.decisao, d.data_txt)
        extra = {}
        if id(d) in pre:
            cod, mot = pre[id(d)]
        elif k in ign:
            cod, mot = ign[k].get("codigo", "estado_nao_permite"), ign[k]["ignoradaPorque"]
            extra = {x: ign[k][x] for x in ("codigos", "campos", "divergenciasAlteradas", "impressaoComparavel") if x in ign[k]}     # P-08: todos os códigos e campos materiais
        else:
            cod, mot = "superada_por_decisao_mais_recente", "existe decisão humana mais recente para o produto"
        out.append({**d.como_dict(), "codigo": cod, "motivo": mot, **extra})
    return out


def resolver(prod_a: Produto | None, prod_b: Produto | None, decisoes: list[Decisao], agora: datetime,
             cfg: ConfiguracaoV11, foto: dict) -> tuple[Produto, AvaliacaoV11]:
    """Devolve ``(produto que sustenta a ficha, avaliação)``. Pelo menos uma das fontes deve existir."""
    if prod_a is None and prod_b is None:
        raise ValueError("produto sem nenhuma fonte")
    if prod_a is None or prod_b is None:
        base = prod_a or prod_b
        av = avaliar_v11(base, decisoes, agora, cfg, foto)
        av.fonte_selecionada = av.origem
        av.decisoes_inaplicaveis = _inaplicaveis(decisoes, av, {})
        return base, av

    va, vb = prod_a.vigente, prod_b.vigente
    est_a, motivo_a, _ = estado_automatico_v11(va.dados, agora, cfg, bool(foto.get("utilizavel")))
    sel = "B" if est_a == estados.EXPIRADO else "A"
    base = prod_b if sel == "B" else prod_a
    ids_sel = {v.export_id for v in base.versoes}
    ids_outra = {v.export_id for v in (prod_a if sel == "B" else prod_b).versoes}
    div = comparar_ab(va, vb)

    pre: dict = {}
    passar: list[Decisao] = []
    rejeicao_outra = None
    cand = decisoes[-1] if decisoes else None            # só a decisão mais recente do produto pode valer
    if cand is not None:
        if cand.export_id in ids_sel or cand.export_id not in ids_outra:
            passar = [cand]
        elif cand.decisao == estados.REJEITADO:
            rejeicao_outra = cand
        else:
            pre[id(cand)] = ("fonte_nao_selecionada",
                             f"decisão registrada sobre versão da fonte {'A' if sel == 'B' else 'B'}; a ficha é sustentada "
                             f"pela fonte {sel} e nenhuma fonte substitui decisão humana")
    outra = prod_a if sel == "B" else prod_b
    av = avaliar_v11(base, passar, agora, cfg, foto, outra=outra)
    if rejeicao_outra is not None:
        _aplicar(av, rejeicao_outra, estados.REJEITADO, "rejeitada por decisão humana (registrada sobre a outra fonte)")

    av.fonte_selecionada = sel
    av.divergencias_ab = div
    av.fonte_comercial = {
        "fonte": "A", "exportId": va.export_id, "estadoAutomatico": est_a, "motivo": motivo_a,
        "janelaComercialAte": _fmt(janela_comercial(va.dados["price"])),
        "alegacaoComercialPermitida": ("somente pelo portão de pré-publicação"
                                       if est_a in (estados.PENDENTE_REVISAO, estados.INCOMPLETO) else False),
    }
    if sel == "A":
        av.editorial_b = _editorial(vb)
    else:
        av.pendencias.append("fonte A expirada: sem alegação comercial; é preciso nova exportação A com verificação ao vivo")
        av.eventos.append({"em": _fmt(agora), "de": estados.EXPIRADO, "para": av.estado_automatico, "origem": "automatico",
                           "motivo": "A expirada: ficha sustentada por B como rascunho editorial, sem alegação comercial"})
    if div and av.estado in (estados.CANDIDATO_NAO_VERIFICADO, estados.PENDENTE_REVISAO):
        av.eventos.append({"em": _fmt(agora), "de": av.estado, "para": estados.PENDENTE_REVISAO, "origem": "automatico",
                           "motivo": "divergência A × B em: " + ", ".join(div["campos"])})
        av.estado = estados.PENDENTE_REVISAO
        av.pendencias.append("revisão humana: divergência entre A e B em " + ", ".join(div["campos"]))
    av.decisoes_inaplicaveis = _inaplicaveis(decisoes, av, pre)
    return base, av
