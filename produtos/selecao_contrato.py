"""Seleção explícita de contrato para o futuro ponto de entrada de DADOS REAIS (contrato v1.1 §11, P-02).

Regras (só valem quando ``--dados-reais`` é informado; sem ele o CLI 1.0 de sempre não muda):
- ``--contrato`` é obrigatório e **não tem padrão**;
- ``--contrato 1.0`` com dados reais exige ``--legado`` explícito (o modo 1.0 aceita ``photo.usePermission`` do agente);
- ``--legado`` só combina com ``--contrato 1.0``.
O processamento de dados reais permanece **DESABILITADO** nesta etapa (``DADOS_REAIS_HABILITADO = False``): a seleção é
validada e depois recusada, sem ler nada. Habilitar exige autorização própria (GOAL de integração de dados reais, fase 2).
"""
from __future__ import annotations

DADOS_REAIS_HABILITADO = False
CONTRATOS = ("1.0", "1.1")


class SelecaoInvalida(ValueError):
    """Combinação de ``--contrato``/``--legado``/``--dados-reais`` recusada."""


def selecionar(contrato: str | None, legado: bool = False, dados_reais: bool = False) -> dict:
    if contrato is not None and contrato not in CONTRATOS:
        raise SelecaoInvalida(f"contrato desconhecido (use {' ou '.join(CONTRATOS)})")
    if legado and contrato not in (None, "1.0"):
        raise SelecaoInvalida("--legado só pode ser usado com --contrato 1.0")
    if dados_reais:
        if contrato is None:
            raise SelecaoInvalida("dados reais exigem --contrato informado (1.1; não há padrão implícito)")
        if contrato == "1.0" and not legado:
            raise SelecaoInvalida("usar o contrato 1.0 com dados reais exige --legado explícito")
    return {"contrato": contrato or "1.0", "legado": bool(legado), "dadosReais": bool(dados_reais)}
