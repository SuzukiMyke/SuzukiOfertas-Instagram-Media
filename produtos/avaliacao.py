"""Expiração e máquina de estados (GOAL 5.4 e 5.6; contrato §4 e §5).

Estado automático da versão vigente, em ordem de precedência:
  1. B (``catalogo_candidato``/``api_candidato``): sempre ``expirado`` ("sem verificação") — serve só
     para ideação; nunca vira conteúdo sem nova exportação do tipo A.
  2. A: ``expirado`` se ``agora > validUntil`` (o limite é inclusivo) ou se passou a janela de
     revalidação (``agora - verifiedAt > revalidacao_horas``; padrão 24 h, parâmetro).
  3. A com ``availability = out_of_stock``: ``invalidado``.
  4. Sem foto autorizada: ``incompleto``.  5. Caso contrário: ``pendente_revisao``.
Aprovações (``aprovado_*``) só nascem de decisão humana registrada, aplicada à versão revisada e
válida enquanto o preço não mudar; mudança de preço volta a ficha para ``pendente_revisao``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import estados
from .decisoes import Decisao
from .esquema import FONTE_A
from .fotos import foto_utilizavel
from .registro import Produto
from .tempo import parse_data


@dataclass
class Configuracao:
    revalidacao_horas: float | None = 24.0   # proposta do contrato, ajustável; None desativa
    arquivo_dias: int | None = 30
    tolerancia_futuro_min: int = 5


@dataclass
class Avaliacao:
    estado: str
    estado_automatico: str
    motivo_automatico: str
    pendencias: list[str] = field(default_factory=list)
    decisao_aplicada: Decisao | None = None
    decisoes_ignoradas: list[dict] = field(default_factory=list)
    aprovacao_invalidada_por_preco: bool = False
    mudanca_de_preco: dict | None = None
    eventos: list[dict] = field(default_factory=list)


def estado_automatico(dados: dict, agora: datetime, cfg: Configuracao) -> tuple[str, str, list[str]]:
    """(estado, motivo, pendências) da versão, sem considerar decisões humanas."""
    pend: list[str] = []
    if dados["source"]["kind"] != FONTE_A:
        return (estados.EXPIRADO, "fonte B: sem verificação ao vivo; revalidação pelo agente (exportação tipo A) necessária",
                ["nova exportação do tipo A com verificação ao vivo"])
    preco = dados["price"]
    valida = parse_data(preco["validUntil"])
    verificada = parse_data(preco["verifiedAt"])
    if agora > valida:
        return estados.EXPIRADO, "preço vencido (validUntil)", ["revalidar o preço ao vivo e reexportar"]
    if cfg.revalidacao_horas is not None and agora - verificada > timedelta(hours=cfg.revalidacao_horas):
        return (estados.EXPIRADO, f"revalidação necessária (verificação com mais de {cfg.revalidacao_horas:g} h)",
                ["revalidar o preço ao vivo e reexportar"])
    if dados["availability"] == "out_of_stock":
        return estados.INVALIDADO, "produto indisponível", ["produto indisponível na fonte"]
    if not foto_utilizavel(dados["photo"]):
        pend.append("foto autorizada ausente (permissão de uso não confirmada)")
        return estados.INCOMPLETO, "sem foto autorizada", pend
    return estados.PENDENTE_REVISAO, "completo e dentro da validade; aguarda revisão humana", pend


def _preco_inalterado(produto: Produto, desde: int) -> bool:
    """True se todas as versões a partir do índice ``desde`` (mais antigas ao topo) têm o mesmo preço."""
    base = produto.versoes[desde].centavos
    return all(v.centavos == base and v.dados["price"]["currency"] == produto.versoes[desde].dados["price"]["currency"]
               for v in produto.versoes[:desde + 1])


def avaliar(produto: Produto, decisoes: list[Decisao], agora: datetime, cfg: Configuracao) -> Avaliacao:
    vigente = produto.vigente
    auto, motivo, pend = estado_automatico(vigente.dados, agora, cfg)
    av = Avaliacao(estado=auto, estado_automatico=auto, motivo_automatico=motivo, pendencias=list(pend))
    av.eventos.append({"em": vigente.dados["exportedAt"], "de": None, "para": estados.RECEBIDO, "origem": "automatico",
                       "motivo": "arquivo íntegro e com esquema válido"})
    av.eventos.append({"em": _fmt(agora), "de": estados.RECEBIDO, "para": auto, "origem": "automatico", "motivo": motivo})

    ids = [v.export_id for v in produto.versoes]
    # mudança de preço entre a versão vigente e a imediatamente anterior
    if len(produto.versoes) > 1 and produto.versoes[1].centavos != vigente.centavos:
        ant = produto.versoes[1]
        av.mudanca_de_preco = {"de": ant.centavos, "para": vigente.centavos, "versaoAnterior": ant.export_id}

    if not decisoes:
        return av
    ultima = decisoes[-1]                      # decisões já ordenadas por data; vale a mais recente
    if ultima.export_id not in ids:
        av.decisoes_ignoradas.append({**ultima.como_dict(), "ignoradaPorque": "exportId não pertence às versões conhecidas do produto"})
        return av
    idx = ids.index(ultima.export_id)
    versao_rev = produto.versoes[idx]
    if ultima.data > agora:
        av.decisoes_ignoradas.append({**ultima.como_dict(), "ignoradaPorque": "data da decisão no futuro"})
        return av
    if ultima.data < versao_rev.exportada_em:
        av.decisoes_ignoradas.append({**ultima.como_dict(), "ignoradaPorque": "decisão anterior à exportação revisada"})
        return av

    if ultima.decisao == estados.REJEITADO:
        _aplicar(av, ultima, estados.REJEITADO, "rejeitada por decisão humana", agora)
        return av

    # aprovações: valem só para o preço revisado
    if not _preco_inalterado(produto, idx):
        av.aprovacao_invalidada_por_preco = True
        av.decisoes_ignoradas.append({**ultima.como_dict(), "ignoradaPorque": "preço mudou depois da aprovação; nova revisão necessária"})
        av.eventos.append({"em": _fmt(agora), "de": ultima.decisao, "para": estados.PENDENTE_REVISAO if auto == estados.PENDENTE_REVISAO else auto,
                           "origem": "automatico", "motivo": "aprovação invalidada por mudança de preço"})
        return av
    if auto != estados.PENDENTE_REVISAO:
        av.decisoes_ignoradas.append({**ultima.como_dict(), "ignoradaPorque": f"estado automático '{auto}' não permite aprovação"})
        return av
    if ultima.decisao == estados.APROVADO_PUBLICACAO and vigente.dados["source"]["kind"] != FONTE_A:
        av.decisoes_ignoradas.append({**ultima.como_dict(), "ignoradaPorque": "fonte B nunca é aprovada para publicação"})
        return av
    _aplicar(av, ultima, ultima.decisao, "aprovação humana registrada", agora)
    return av


def _aplicar(av: Avaliacao, dec: Decisao, estado: str, motivo: str, agora: datetime):
    av.eventos.append({"em": dec.data_txt, "de": av.estado, "para": estado, "origem": "humano",
                       "autor": dec.autor, "motivo": dec.motivo or motivo})
    av.estado = estado
    av.decisao_aplicada = dec


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
