"""Configuração do portão (§4.5). ``PRODUCAO`` usa SÓ literais deste código: âncoras vazias, flags ``False``, relógio UTC do sistema.

Nesta etapa NÃO há chave real: com ``ancoras`` vazia nenhuma autorização é válida em produção. Os limites de tamanho são os desta etapa e
NÃO são definitivos para fotografias comerciais (a B3-B definirá os seus). ``tolerancia_relogio`` = 0 s é o valor dos testes desta etapa e
será reavaliado antes do primeiro dado real.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from .fixtures_registro import CONJUNTOS, ConjuntoFixture

VERSAO_REGRAS = "20.1"
MIB = 1024 * 1024


def relogio_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ConfigVerificacao:
    ancoras: frozenset
    conjuntos: tuple
    dados_reais_habilitado: bool
    produtos_reais_habilitado: bool
    relogio: Callable[[], datetime] = relogio_utc
    validade_maxima_lote: timedelta = timedelta(days=7)
    janela_revogacao: timedelta = timedelta(hours=24)
    tolerancia_relogio: timedelta = timedelta(seconds=0)
    max_arquivos: int = 1000
    max_bytes_arquivo: int = 2 * MIB
    max_bytes_total: int = 64 * MIB
    sequencia_minima_revogacao: int = 0
    exigir_garantia_forte: bool = True


PRODUCAO = ConfigVerificacao(
    ancoras=frozenset(),                       # SEM chave real nesta etapa: nenhuma autorização é válida em produção
    conjuntos=CONJUNTOS,
    dados_reais_habilitado=False,
    produtos_reais_habilitado=False,
    relogio=relogio_utc,
)
