"""Exceções internas do portão. Toda exceção deste pacote (e qualquer outra) resulta em RECUSA (fail-closed)."""
from __future__ import annotations


class ErroEntrada(Exception):
    """Base: carrega um ``codigo`` estável para o relatório."""

    codigo = "erro_interno"

    def __init__(self, codigo: str | None = None, detalhe: str = ""):
        self.codigo = codigo or self.codigo
        self.detalhe = detalhe
        super().__init__(f"{self.codigo}: {detalhe}" if detalhe else self.codigo)


class NaoCanonico(ErroEntrada):
    codigo = "nao_canonico"


class ErroIntegridade(ErroEntrada):
    codigo = "integridade"


class ErroAssinatura(ErroEntrada):
    codigo = "assinatura_invalida"


class ErroAutorizacao(ErroEntrada):
    """Falha de atestado; ``resultado`` ∈ {invalida, expirada, revogada, revogacao_nao_comprovada_atual}."""

    codigo = "autorizacao_invalida"

    def __init__(self, codigo: str, detalhe: str = "", resultado: str = "invalida"):
        super().__init__(codigo, detalhe)
        self.resultado = resultado


class ErroRevogacao(ErroEntrada):
    codigo = "revogacao_nao_comprovada_atual"


class FalhaPersistencia(ErroEntrada):
    codigo = "falha_persistencia"
