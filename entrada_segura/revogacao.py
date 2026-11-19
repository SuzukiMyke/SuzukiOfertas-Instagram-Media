"""Lista de revogações assinada e atualidade (§4.10).

Requisito de PROJETO, sem promessa de revogação instantânea: a lista precisa ter integridade comprovada (assinatura Ed25519 de âncora
fixada) e carimbo de atualidade (``emitidoEm ≤ agora ≤ validoAte``, janela máxima de 24 h, tolerância 0 s nos testes desta etapa). Se a
atualidade não puder ser comprovada, o resultado é ``revogacao_nao_comprovada_atual`` ⇒ RECUSA. A B3-A1 não persiste estado: o último valor
de ``sequencia`` visto é só registrado no relatório.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import assinatura, canonico
from .erros import ErroAssinatura, ErroIntegridade, ErroRevogacao, NaoCanonico
from .integridade import ler_lote
from .politica import formatar_utc, parse_utc

NOME_DOC, NOME_SIG = "revogacoes.json", "revogacoes.sig.json"
CAMPOS = frozenset({"schemaVersion", "tipo", "sequencia", "emitidoEm", "validoAte", "revogados", "aprovadorFingerprint"})
CAMPOS_ITEM = frozenset({"tipo", "valor", "revogadoEm", "motivo"})
MOTIVOS = frozenset({"chave_comprometida", "lote_substituido", "erro_de_revisao", "autorizacao_retirada", "outro"})
_HEX64, _NONCE, _FP = re.compile(r"^[0-9a-f]{64}$"), re.compile(r"^[0-9a-f]{32,64}$"), re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ListaRevogacao:
    sequencia: int
    emitido_em: str
    valido_ate: str
    nonces: frozenset
    shas: frozenset


def _data(valor, campo):
    try:
        return parse_utc(valor)
    except ValueError:
        raise ErroRevogacao("data_invalida", campo) from None


def carregar(pasta, config, agora) -> ListaRevogacao:
    """Lê e valida a lista; qualquer falha levanta ``ErroRevogacao`` (⇒ recusa). ``agora`` é lido UMA vez pelo chamador."""
    if pasta is None:
        raise ErroRevogacao("lista_ausente", "pasta de revogações não informada")
    try:
        lido = ler_lote(pasta, [NOME_DOC, NOME_SIG], config)
    except ErroIntegridade as e:
        raise ErroRevogacao("lista_ausente" if e.codigo == "arquivo_ausente" else "lista_ilegivel", e.codigo) from None
    doc, sig = lido.arquivos[NOME_DOC], lido.arquivos[NOME_SIG]
    try:
        d = canonico.carregar_canonico(doc)
    except NaoCanonico as e:
        raise ErroRevogacao("lista_nao_canonica", e.codigo) from None
    if not isinstance(d, dict) or set(d) != CAMPOS or d["schemaVersion"] != "1" or d["tipo"] != "revogacoes":
        raise ErroRevogacao("lista_invalida", "campos, versão ou tipo")
    seq = d["sequencia"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ErroRevogacao("lista_invalida", "sequencia")
    if not isinstance(d["aprovadorFingerprint"], str) or not _FP.match(d["aprovadorFingerprint"]):
        raise ErroRevogacao("lista_invalida", "aprovadorFingerprint")
    emitido, valido = _data(d["emitidoEm"], "emitidoEm"), _data(d["validoAte"], "validoAte")
    if not isinstance(d["revogados"], list):
        raise ErroRevogacao("lista_invalida", "revogados")
    nonces, shas, vistos = set(), set(), set()
    for it in d["revogados"]:
        if not isinstance(it, dict) or set(it) != CAMPOS_ITEM or it["motivo"] not in MOTIVOS or it["tipo"] not in ("nonce", "sha256"):
            raise ErroRevogacao("lista_invalida", "item revogado")
        padrao = _NONCE if it["tipo"] == "nonce" else _HEX64
        if not isinstance(it["valor"], str) or not padrao.match(it["valor"]) or (it["tipo"], it["valor"]) in vistos:
            raise ErroRevogacao("lista_invalida", "valor revogado inválido ou duplicado")
        _data(it["revogadoEm"], "revogadoEm")
        vistos.add((it["tipo"], it["valor"]))
        (nonces if it["tipo"] == "nonce" else shas).add(it["valor"])
    try:
        assinado = assinatura.verificar(assinatura.PREFIXO_REVOGACOES, doc, sig, config.ancoras)
    except ErroAssinatura as e:
        raise ErroRevogacao(e.codigo, "assinatura da lista") from None
    if d["aprovadorFingerprint"] != assinado.fingerprint:
        raise ErroRevogacao("fingerprint_divergente", "aprovadorFingerprint ≠ chave que assinou")
    if not emitido < valido or valido - emitido > config.janela_revogacao:
        raise ErroRevogacao("janela_excedida", f"janela da lista acima de {config.janela_revogacao}")
    if emitido > agora + config.tolerancia_relogio:
        raise ErroRevogacao("relogio_no_futuro", "a lista foi emitida no futuro")
    if agora > valido:
        raise ErroRevogacao("carimbo_vencido", "a atualidade da lista não pôde ser comprovada")
    if seq < config.sequencia_minima_revogacao:
        raise ErroRevogacao("sequencia_regressiva", "sequência abaixo do mínimo aceito")
    return ListaRevogacao(seq, formatar_utc(emitido), formatar_utc(valido), frozenset(nonces), frozenset(shas))
