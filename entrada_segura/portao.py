"""Orquestração do portão e decisão final (§4.12). ``avaliar_producao`` é o ÚNICO ponto de entrada de produção.

Precedência: erro interno → plataforma sem garantia → integridade → ``desconhecido`` (recusa) → ``ficticio_reconhecido`` (aceita, mesmo com flags
``False``) → ``potencialmente_real`` (flags globais, depois atestado). Atestado válido NÃO supera flag desabilitada. Qualquer exceção ⇒ recusa.
``Portao`` (camada de biblioteca, configuração sintética) NÃO é ponto de entrada operacional.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from . import atestado, relatorio as rel
from .classificacao import DESCONHECIDO, FICTICIO, REAL, classificar
from .erros import ErroEntrada, ErroIntegridade, FalhaPersistencia
from .integridade import NivelGarantia, ler_lote, nivel_de_garantia
from .politica import PRODUCAO, VERSAO_REGRAS, ConfigVerificacao, formatar_utc
from .relatorio import Comprovante, Decisao, Relatorio


@dataclass(frozen=True)
class ResultadoEntrada:
    relatorio: Relatorio
    decisao: Decisao
    comprovante: Comprovante | None
    bytes_verificados: dict = field(default_factory=dict, repr=False)
    erro_persistencia: str | None = None

    @property
    def consumo_permitido(self) -> bool:
        """Verdadeiro SOMENTE com decisão ``aceita`` E relatório persistido com comprovante."""
        return self.decisao.aceita and self.comprovante is not None


_EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _flags(cfg: ConfigVerificacao) -> dict:
    return {"dados": cfg.dados_reais_habilitado, "produtos": cfg.produtos_reais_habilitado}


_MAPA_AUTORIZACAO = {"invalida": "recusada_autorizacao_invalida", "expirada": "recusada_autorizacao_expirada", "revogada": "recusada_revogada",
                     "revogacao_nao_comprovada_atual": "recusada_revogacao_nao_comprovada_atual"}


def _autorizacao_dict(a: atestado.ResultadoAutorizacao) -> dict:
    return {"resultado": a.resultado, "codigo": a.codigo, "aplicavel": a.aplicavel, "fingerprint": a.fingerprint, "nonce": a.nonce,
            "validoAte": a.valido_ate, "revogacao": dict(a.revogacao)}


def _relatorio_erro_interno(agora, nivel: str, flags: dict) -> Relatorio:
    """Relatório mínimo de recusa montado SEM depender de nenhuma outra etapa (usado quando a própria montagem falha)."""
    return Relatorio({
        "schemaVersion": "1", "versaoRegras": VERSAO_REGRAS, "avaliadoEm": formatar_utc(agora or _EPOCA), "plataforma": {"sistema": sys.platform, "nivelDeGarantia": nivel},
        "lote": {"quantidadeArquivos": None, "totalBytes": None, "manifestoSha256": None, "hashes": []},
        "classificacao": {"classe": None, "motivos": [], "hostsAvaliados": [], "totalHosts": 0, "conjunto": None},
        "autorizacao": {"resultado": "nao_aplicavel", "codigo": "recusa_anterior", "aplicavel": False, "fingerprint": None, "nonce": None, "validoAte": None,
                        "revogacao": {"estado": "nao_consultada", "sequencia": None, "frescorAte": None}},
        "decisao": {"resultado": "recusada", "codigos": ["recusada_erro_interno"]},
        "flags": {"dadosReaisHabilitado": bool(flags["dados"]), "produtosReaisHabilitado": bool(flags["produtos"])}})


class Portao:
    """Camada de biblioteca: configuração injetada (os testes usam configuração SINTÉTICA). Não é ponto de entrada operacional."""

    def __init__(self, config: ConfigVerificacao):
        self.config = config

    def avaliar(self, raiz_lote, arquivos, *, pasta_autorizacao=None, pasta_revogacao=None, _gancho=None) -> Relatorio:
        flags = _flags(self.config)
        nivel = NivelGarantia.INSUFICIENTE.value
        agora = None
        try:
            agora = self.config.relogio()                      # lido UMA vez; as etapas seguintes usam este instante
            if not isinstance(agora, datetime) or agora.tzinfo is None:
                raise ErroEntrada("relogio_invalido", "o relógio precisa devolver datetime com fuso")
            cfg = replace(self.config, relogio=lambda: agora)
            nivel = nivel_de_garantia().value
            if nivel != NivelGarantia.FORTE.value:
                return rel.montar(avaliado_em=agora, nivel=nivel, lote=None, classificacao=None, autorizacao=_autorizacao_dict(atestado.nao_aplicavel("recusa_anterior")),
                                  decisao=Decisao("recusada", ("recusada_garantia_plataforma_insuficiente", "garantia_plataforma_insuficiente")), flags=flags)
            try:
                lote = ler_lote(raiz_lote, arquivos, cfg, _gancho=_gancho)
            except ErroIntegridade as e:
                return rel.montar(avaliado_em=agora, nivel=nivel, lote=None, classificacao=None, autorizacao=_autorizacao_dict(atestado.nao_aplicavel("recusa_anterior")),
                                  decisao=Decisao("recusada", ("recusada_integridade", e.codigo)), flags=flags)
            manifesto = lote.arquivos.get("manifest.json")
            info_lote = {"quantidade": len(lote.arquivos), "total_bytes": lote.total_bytes, "hashes": lote.hashes,
                         "manifesto_sha256": hashlib.sha256(manifesto).hexdigest() if manifesto is not None else None}
            c = classificar(lote.arquivos, cfg)
            cdict = {"classe": c.classe, "motivos": list(c.motivos), "hostsAvaliados": list(c.hosts), "totalHosts": c.total_hosts, "conjunto": c.conjunto}

            def pronto(decisao: Decisao, autorizacao: dict, bytes_ok=None):
                return rel.montar(avaliado_em=agora, nivel=nivel, lote=info_lote, classificacao=cdict, autorizacao=autorizacao, decisao=decisao,
                                  flags=flags, bytes_verificados=bytes_ok)
            if c.classe == DESCONHECIDO:
                return pronto(Decisao("recusada", ("recusada_desconhecido",)), _autorizacao_dict(atestado.nao_aplicavel("desconhecido_sempre_recusado")))
            if c.classe == FICTICIO:
                codigo = "atestado_ignorado_ficticio" if pasta_autorizacao is not None else "ficticio_nao_exige_autorizacao"
                return pronto(Decisao("aceita", ("aceita_ficticio_reconhecido",)), _autorizacao_dict(atestado.nao_aplicavel(codigo)), lote.arquivos)
            if c.classe != REAL:
                raise ErroEntrada("classe_desconhecida", "classe inesperada")
            aut = atestado.avaliar(pasta_autorizacao, pasta_revogacao, lote, cfg, agora)          # sempre avaliada e registrada como evidência
            adict = _autorizacao_dict(aut)
            if not (cfg.dados_reais_habilitado and cfg.produtos_reais_habilitado):
                return pronto(Decisao("recusada", ("recusada_flag_global_desabilitada",)), adict)  # atestado válido NÃO supera flag desabilitada
            if aut.resultado == "valida":
                return pronto(Decisao("aceita", ("aceita_potencialmente_real_autorizado",)), adict, lote.arquivos)
            if aut.codigo == "erro_interno":
                codigo = "recusada_erro_interno"
            elif aut.codigo == "autorizacao_ausente":
                codigo = "recusada_sem_autorizacao"
            elif aut.codigo == "escopo_invalido":
                codigo = "recusada_escopo"
            else:
                codigo = _MAPA_AUTORIZACAO.get(aut.resultado, "recusada_autorizacao_invalida")
            return pronto(Decisao("recusada", (codigo, aut.codigo)), adict)
        except Exception:                                      # fail-closed: nenhuma exceção vira aceitação
            return _relatorio_erro_interno(agora, nivel, flags)


def avaliar_producao(raiz_lote, arquivos, *, base_evidencia=None, pasta_autorizacao=None, pasta_revogacao=None) -> ResultadoEntrada:
    """ÚNICO ponto de entrada de produção. SEM parâmetros de configuração: usa só ``politica.PRODUCAO`` (âncora vazia, flags ``False``).

    Lê o relógio UMA vez. Sem ``base_evidencia`` o relatório fica só em memória e ``consumo_permitido`` é ``False``."""
    try:
        agora = PRODUCAO.relogio()
        portao = Portao(replace(PRODUCAO, relogio=lambda: agora))
        relatorio = portao.avaliar(raiz_lote, arquivos, pasta_autorizacao=pasta_autorizacao, pasta_revogacao=pasta_revogacao)
    except Exception:
        agora = None
        relatorio = _relatorio_erro_interno(None, NivelGarantia.INSUFICIENTE.value, _flags(PRODUCAO))
    decisao = relatorio.decisao
    comprovante, erro = None, None
    if base_evidencia is not None:
        try:
            diretorio = rel.criar_diretorio_evidencia(base_evidencia, relogio=lambda: agora or _EPOCA)
            comprovante = rel.persistir(relatorio, diretorio)
        except FalhaPersistencia as e:
            comprovante, erro = None, e.codigo
        except Exception:
            comprovante, erro = None, "falha_persistencia"
    return ResultadoEntrada(relatorio, decisao, comprovante, dict(relatorio.bytes_verificados) if decisao.aceita else {}, erro)
