"""Validade, revisão e estados do modo 1.1 (contrato v1.1 §4, §5, §7.2, §8, §9). Módulo novo; ``avaliacao`` (1.0) não muda.

Diferenças em relação ao modo 1.0:
- teto de 24 h para preço/disponibilidade que **não pode ser desativado nem aumentado** (``ConfiguracaoV11`` recusa
  ``None`` e valores > 24; pode ser menor);
- fonte B -> ``candidato_nao_verificado`` (pode receber ``aprovado_para_rascunho``; nunca ``aprovado_para_publicacao``);
- a foto vem **somente** de registro humano (``permissoes``); ``photo.usePermission`` exportado é informativo;
- mudança de **identidade** (title/store/officialUrl) invalida aprovação (volta ao estado automático/``pendente_revisao``);
  mudança de **preço** invalida aprovação de A; no B o preço é referência não verificada e não invalida aprovação editorial;
- ``verifiedFacts`` separados em frescos (``fatosParaUso``, ≤ ``fatos_dias``) e em revisão. Dormente sem fonte de fatos.
Nada aqui verifica preço em tempo real: só aplica a janela declarada no arquivo exportado.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import estados
from .avaliacao import Avaliacao, _fmt
from .decisoes import Decisao
from .esquema import FONTE_A
from .registro import Produto, Versao
from .tempo import parse_data

TETO_REVALIDACAO_H = 24.0


@dataclass
class ConfiguracaoV11:
    revalidacao_horas: float = TETO_REVALIDACAO_H
    fatos_dias: int = 30
    margem_publicacao_min: int = 30
    arquivo_dias: int | None = 30
    tolerancia_futuro_min: int = 5
    contrato: str = "1.1"

    def __post_init__(self):
        h = self.revalidacao_horas
        if isinstance(h, bool) or not isinstance(h, (int, float)) or not (0 < h <= TETO_REVALIDACAO_H):
            raise ValueError("modo 1.1: revalidacao_horas deve estar entre 0 (exclusivo) e 24; o teto de 24 h não pode ser "
                             "desativado nem aumentado")
        if isinstance(self.fatos_dias, bool) or not isinstance(self.fatos_dias, int) or self.fatos_dias <= 0:
            raise ValueError("fatos_dias deve ser inteiro positivo")
        if isinstance(self.margem_publicacao_min, bool) or not isinstance(self.margem_publicacao_min, int) \
                or self.margem_publicacao_min < 0:
            raise ValueError("margem_publicacao_min deve ser inteiro >= 0")
        if self.contrato != "1.1":
            raise ValueError("ConfiguracaoV11 é exclusiva do modo 1.1")


@dataclass
class AvaliacaoV11(Avaliacao):
    origem: str = "A"
    mudanca_identidade: dict | None = None
    aprovacao_invalidada_por_identidade: bool = False
    fatos_para_uso: list[dict] = field(default_factory=list)
    fatos_em_revisao: list[dict] = field(default_factory=list)
    foto: dict = field(default_factory=dict)


def origem(dados: dict) -> str:
    return "A" if dados["source"]["kind"] == FONTE_A else "B"


def _identidade(v: Versao) -> dict:
    p = v.dados["product"]
    return {"title": p["title"], "store": p["store"], "officialUrl": p["officialUrl"]}


def _canon(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def estado_automatico_v11(dados: dict, agora: datetime, cfg: ConfiguracaoV11, foto_ok: bool) -> tuple[str, str, list[str]]:
    if origem(dados) == "B":
        return (estados.CANDIDATO_NAO_VERIFICADO,
                "fonte B: candidato sem verificação ao vivo; só rascunho editorial, sem alegação comercial",
                ["uso comercial exige exportação A fresca do mesmo provedor e produto"])
    preco = dados["price"]
    valida, verificada = parse_data(preco["validUntil"]), parse_data(preco["verifiedAt"])
    if agora > valida:
        return estados.EXPIRADO, "preço vencido (validUntil)", ["revalidar o preço ao vivo e reexportar"]
    if agora - verificada > timedelta(hours=cfg.revalidacao_horas):
        return (estados.EXPIRADO, f"revalidação necessária (verificação com mais de {cfg.revalidacao_horas:g} h)",
                ["revalidar o preço ao vivo e reexportar"])
    if dados["availability"] == "out_of_stock":
        return estados.INVALIDADO, "produto indisponível", ["produto indisponível na fonte"]
    if not foto_ok:
        return (estados.INCOMPLETO, "sem foto autorizada por registro humano",
                ["foto autorizada ausente (registro humano de permissão com hash do arquivo)"])
    return estados.PENDENTE_REVISAO, "completo e dentro da validade; aguarda revisão humana", []


def classificar_fatos(vigente: Versao, anterior: Versao | None, identidade_mudou: bool, agora: datetime,
                      cfg: ConfiguracaoV11) -> tuple[list[dict], list[dict]]:
    fatos = vigente.dados["verifiedFacts"]
    global_ = None
    if identidade_mudou:
        global_ = "indício de alteração: title/store/officialUrl diferentes entre versões"
    elif anterior is not None and _canon(fatos) != _canon(anterior.dados["verifiedFacts"]):
        global_ = "indício de alteração: conjunto de verifiedFacts mudou entre versões"
    uso, rev = [], []
    for f in fatos:
        ver = parse_data(f["verifiedAt"])
        if global_:
            rev.append({**f, "motivoRevisao": global_})
        elif ver is None or ver > agora:
            rev.append({**f, "motivoRevisao": "data de verificação inválida ou futura"})
        elif agora - ver > timedelta(days=cfg.fatos_dias):
            rev.append({**f, "motivoRevisao": f"verificado há mais de {cfg.fatos_dias} dias"})
        else:
            uso.append(dict(f))
    return uso, rev


def avaliar_v11(produto: Produto, decisoes: list[Decisao], agora: datetime, cfg: ConfiguracaoV11,
                foto: dict) -> AvaliacaoV11:
    vigente = produto.vigente
    orig = origem(vigente.dados)
    auto, motivo, pend = estado_automatico_v11(vigente.dados, agora, cfg, bool(foto.get("utilizavel")))
    av = AvaliacaoV11(estado=auto, estado_automatico=auto, motivo_automatico=motivo, pendencias=list(pend),
                      origem=orig, foto=foto)
    av.eventos.append({"em": vigente.dados["exportedAt"], "de": None, "para": estados.RECEBIDO, "origem": "automatico",
                       "motivo": "arquivo íntegro, lote com manifesto íntegro e esquema válido"})
    av.eventos.append({"em": _fmt(agora), "de": estados.RECEBIDO, "para": auto, "origem": "automatico", "motivo": motivo})

    anterior = produto.versoes[1] if len(produto.versoes) > 1 else None
    if anterior is not None and anterior.centavos != vigente.centavos:
        av.mudanca_de_preco = {"de": anterior.centavos, "para": vigente.centavos, "versaoAnterior": anterior.export_id}
    if anterior is not None and _identidade(anterior) != _identidade(vigente):
        campos = sorted(k for k in _identidade(vigente) if _identidade(vigente)[k] != _identidade(anterior)[k])
        av.mudanca_identidade = {"campos": campos, "versaoAnterior": anterior.export_id}
    av.fatos_para_uso, av.fatos_em_revisao = classificar_fatos(vigente, anterior, av.mudanca_identidade is not None,
                                                               agora, cfg)
    if not decisoes:
        return av

    ultima = decisoes[-1]
    ids = [v.export_id for v in produto.versoes]

    def ignorar(porque):
        av.decisoes_ignoradas.append({**ultima.como_dict(), "ignoradaPorque": porque})
        return av

    if ultima.export_id not in ids:
        return ignorar("exportId não pertence às versões conhecidas do produto")
    idx = ids.index(ultima.export_id)
    if ultima.data > agora:
        return ignorar("data da decisão no futuro")
    if ultima.data < produto.versoes[idx].exportada_em:
        return ignorar("decisão anterior à exportação revisada")
    if ultima.decisao == estados.REJEITADO:
        _aplicar(av, ultima, estados.REJEITADO, "rejeitada por decisão humana")
        return av

    revisada = produto.versoes[idx]
    ate_aqui = produto.versoes[:idx + 1]
    if any(_identidade(v) != _identidade(revisada) for v in ate_aqui):
        av.aprovacao_invalidada_por_identidade = True
        av.eventos.append({"em": _fmt(agora), "de": ultima.decisao, "para": auto, "origem": "automatico",
                           "motivo": "aprovação invalidada por mudança de identidade (title, store ou officialUrl)"})
        return ignorar("identidade do produto mudou depois da aprovação; nova revisão necessária")
    if orig == "A" and any(v.centavos != revisada.centavos or v.dados["price"]["currency"] != revisada.dados["price"]["currency"]
                           for v in ate_aqui):
        av.aprovacao_invalidada_por_preco = True
        av.eventos.append({"em": _fmt(agora), "de": ultima.decisao, "para": auto, "origem": "automatico",
                           "motivo": "aprovação invalidada por mudança de preço"})
        return ignorar("preço mudou depois da aprovação; nova revisão necessária")
    permitido = estados.PENDENTE_REVISAO if orig == "A" else estados.CANDIDATO_NAO_VERIFICADO
    if auto != permitido:
        return ignorar(f"estado automático '{auto}' não permite aprovação")
    if orig == "B" and ultima.decisao == estados.APROVADO_PUBLICACAO:
        return ignorar("fonte B nunca é aprovada para publicação (somente rascunho editorial)")
    _aplicar(av, ultima, ultima.decisao, "aprovação humana registrada")
    return av


def _aplicar(av: AvaliacaoV11, dec: Decisao, estado: str, motivo: str):
    av.eventos.append({"em": dec.data_txt, "de": av.estado, "para": estado, "origem": "humano",
                       "autor": dec.autor, "motivo": dec.motivo or motivo})
    av.estado = estado
    av.decisao_aplicada = dec
