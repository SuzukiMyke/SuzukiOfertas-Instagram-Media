"""Portão de pré-publicação e agendamento (contrato v1.1 §6). Função pura: sem rede, sem publicar, sem relógio próprio.

O relógio e o horário de publicação efetivo são PARÂMETROS. **Não existe** reverificação do preço no instante em que
a plataforma publica (capacidade reservada, futura, com autorização própria): a janela declarada
``min(validUntil, verifiedAt + 24 h)`` é a única garantia. Este módulo só devolve uma recomendação; nunca agenda.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .tempo import formatar, parse_data

LIBERAR, OMITIR, BLOQUEAR = "liberar", "omitir_alegacao", "bloquear"
FUNCOES = ("essencial", "acessoria")
TIPOS_ALEGACAO = ("preco", "desconto", "disponibilidade", "oferta", "urgencia", "menor_preco")
TETO_HORAS = 24


def janela_comercial(preco: dict) -> datetime | None:
    """Fim da janela: ``min(validUntil, verifiedAt + 24 h)``; ``None`` se faltar dado."""
    ate, ver = parse_data(preco.get("validUntil")), parse_data(preco.get("verifiedAt"))
    if ate is None or ver is None:
        return None
    return min(ate, ver + timedelta(hours=TETO_HORAS))


def condicao_comercial(ficha: dict, preco_aprovado_centavos: int | None, t_publicacao: datetime,
                       margem_min: int = 30) -> tuple[bool, list[str], datetime | None]:
    """§6.1: devolve (ok, motivos, fim_da_janela)."""
    m: list[str] = []
    if ficha.get("origem") != "A":
        m.append("exportação não é do tipo A (fonte B nunca sustenta alegação comercial)")
    pr = ficha.get("preco") or {}
    if pr.get("verification") != "ao_vivo":
        m.append("verificação do preço não é ao_vivo")
    if preco_aprovado_centavos is None:
        m.append("não há preço aprovado por humano para comparar")
    elif pr.get("amountCents") != preco_aprovado_centavos:
        m.append("preço exportado difere do preço aprovado")
    if ficha.get("availability") == "out_of_stock":
        m.append("produto indisponível")
    fim = janela_comercial(pr)
    if fim is None:
        m.append("sem janela de validade verificável")
    elif t_publicacao + timedelta(minutes=margem_min) > fim:
        m.append("publicação efetiva (mais a margem) ultrapassa a validade do preço")
    return (not m), m, fim


def avaliar_portao(ficha: dict, *, preco_aprovado_centavos: int | None, t_publicacao: datetime,
                   alegacoes: list[dict], margem_min: int = 30, prova_menor_preco: bool = False) -> dict:
    """``alegacoes``: [{"id", "tipo", "funcao": essencial|acessoria, "tem_variante_sem": bool}].

    Devolve ``{"acao", "motivos", "alegacoes_comerciais", "avaliado_para", "valido_ate", "margem_min"}``.
    Reavalie sempre que ``t_publicacao`` mudar.
    """
    if not isinstance(t_publicacao, datetime) or t_publicacao.tzinfo is None:
        raise ValueError("t_publicacao deve ser datetime com fuso (UTC)")
    for a in alegacoes:
        if a.get("funcao") not in FUNCOES or a.get("tipo") not in TIPOS_ALEGACAO or not a.get("id"):
            raise ValueError("alegação inválida (id, tipo e função essencial|acessoria são obrigatórios)")
    ok, motivos, fim = condicao_comercial(ficha, preco_aprovado_centavos, t_publicacao, margem_min)
    permitidas, omitir, bloquear = [], [], []
    for a in alegacoes:
        falha = (not ok) or (a["tipo"] == "menor_preco" and not prova_menor_preco)
        if not falha:
            permitidas.append(a["id"])
        elif a["funcao"] == "essencial" or not a.get("tem_variante_sem"):
            bloquear.append(a["id"])
        else:
            omitir.append(a["id"])
    mot = list(motivos)
    if any(a["tipo"] == "menor_preco" for a in alegacoes) and not prova_menor_preco:
        mot.append("'menor preço' exige prova explícita")
    if bloquear:
        acao, permitidas = BLOQUEAR, []
        mot.append("alegação essencial ou sem variante de texto limpa: bloquear (ids: " + ", ".join(bloquear) + ")")
    elif omitir:
        acao = OMITIR
        mot.append("alegação acessória omitida com variante sem a alegação (ids: " + ", ".join(omitir) + ")")
    else:
        acao = LIBERAR
    return {"acao": acao, "motivos": mot, "alegacoes_comerciais": permitidas,
            "avaliado_para": formatar(t_publicacao), "valido_ate": formatar(fim) if fim else None,
            "margem_min": margem_min}
