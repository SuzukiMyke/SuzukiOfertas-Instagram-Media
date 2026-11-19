"""Atestado de autorização EXTERNO ao lote (§4.9): assinado, preso aos bytes exatos consumidos, escopo fechado, validade ≤ 7 dias, nonce e
revogação. A assinatura prova controle da chave e integridade — NÃO prova revisão correta nem direito sobre imagem.

Em produção nesta etapa ``ancoras`` é vazia: todo atestado é ``invalida`` (``ancora_desconhecida``).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from . import assinatura, canonico, revogacao
from .erros import ErroAssinatura, ErroAutorizacao, ErroIntegridade, ErroRevogacao, NaoCanonico
from .integridade import ler_lote
from .politica import formatar_utc, parse_utc

NOME_DOC, NOME_SIG = "autorizacao_lote.json", "autorizacao_lote.sig.json"
DECLARACAO = "Declaro ter revisado este lote exato de bytes e autorizo o processamento descrito no escopo."
CAMPOS = frozenset({"schemaVersion", "tipo", "loteId", "manifestoSha256", "arquivos", "escopo", "emitidoEm", "validoAte", "nonce", "versaoRegras",
                    "aprovadorFingerprint", "declaracao"})
CAMPOS_ESCOPO = frozenset({"contrato", "usos", "produtosMax", "publicacao"})
USOS = ("carrossel", "reels", "story")
VERSAO_REGRAS = "20.1"
_LOTE_ID, _HEX64, _NONCE, _FP = (re.compile(r"^[A-Za-z0-9._-]{1,64}$"), re.compile(r"^[0-9a-f]{64}$"), re.compile(r"^[0-9a-f]{32,64}$"),
                                 re.compile(r"^sha256:[0-9a-f]{64}$"))


@dataclass(frozen=True)
class ResultadoAutorizacao:
    resultado: str                 # nao_aplicavel | valida | invalida | expirada | revogada | revogacao_nao_comprovada_atual
    codigo: str
    aplicavel: bool
    fingerprint: str | None = None
    nonce: str | None = None
    valido_ate: str | None = None
    revogacao: dict = None

    def __post_init__(self):
        if self.revogacao is None:
            object.__setattr__(self, "revogacao", {"estado": "nao_consultada", "sequencia": None, "frescorAte": None})


def nao_aplicavel(codigo: str) -> ResultadoAutorizacao:
    return ResultadoAutorizacao("nao_aplicavel", codigo, False)


def _data(valor, campo):
    try:
        return parse_utc(valor)
    except ValueError:
        raise ErroAutorizacao("data_invalida", campo) from None


def _validar_campos(d: dict) -> None:
    if not isinstance(d, dict) or set(d) != CAMPOS:
        raise ErroAutorizacao("campos_invalidos", "campos ausentes ou extras")
    if d["schemaVersion"] != "1" or d["tipo"] != "autorizacao_lote" or d["versaoRegras"] != VERSAO_REGRAS:
        raise ErroAutorizacao("tipo_ou_versao_invalidos", "schemaVersion/tipo/versaoRegras")
    if not isinstance(d["loteId"], str) or not _LOTE_ID.match(d["loteId"]):
        raise ErroAutorizacao("lote_id_invalido", "loteId")
    if not isinstance(d["manifestoSha256"], str) or not _HEX64.match(d["manifestoSha256"]):
        raise ErroAutorizacao("manifesto_sha_invalido", "manifestoSha256")
    if not isinstance(d["nonce"], str) or not _NONCE.match(d["nonce"]):
        raise ErroAutorizacao("nonce_invalido", "nonce ausente, curto ou fora de hex minúsculo")
    if not isinstance(d["aprovadorFingerprint"], str) or not _FP.match(d["aprovadorFingerprint"]):
        raise ErroAutorizacao("fingerprint_invalido", "aprovadorFingerprint")
    if d["declaracao"] != DECLARACAO:
        raise ErroAutorizacao("declaracao_invalida", "frase fixa ausente ou alterada")
    if not isinstance(d["arquivos"], list):
        raise ErroAutorizacao("arquivos_invalidos", "arquivos")
    anterior = None
    for it in d["arquivos"]:
        if (not isinstance(it, dict) or set(it) != {"caminhoRelativo", "sha256", "bytes"} or not isinstance(it["caminhoRelativo"], str)
                or not isinstance(it["sha256"], str) or not _HEX64.match(it["sha256"]) or isinstance(it["bytes"], bool) or not isinstance(it["bytes"], int)
                or it["bytes"] < 0):
            raise ErroAutorizacao("arquivos_invalidos", "item da lista de arquivos")
        if anterior is not None and it["caminhoRelativo"] <= anterior:
            raise ErroAutorizacao("arquivos_invalidos", "lista fora de ordem ou com duplicata")
        anterior = it["caminhoRelativo"]


def _validar_escopo(d: dict) -> None:
    e = d["escopo"]
    if not isinstance(e, dict) or set(e) != CAMPOS_ESCOPO:
        raise ErroAutorizacao("escopo_invalido", "escopo ausente ou com campos extras")
    if e["contrato"] != "1.1":
        raise ErroAutorizacao("escopo_invalido", "contrato diferente de 1.1")
    usos = e["usos"]
    if (not isinstance(usos, list) or not usos or len(set(map(str, usos))) != len(usos) or any(not isinstance(u, str) or u not in USOS for u in usos)):
        raise ErroAutorizacao("escopo_invalido", "usos fora do conjunto fechado")
    if isinstance(e["produtosMax"], bool) or not isinstance(e["produtosMax"], int) or not 1 <= e["produtosMax"] <= 1000:
        raise ErroAutorizacao("escopo_invalido", "produtosMax fora de 1–1000")
    if e["publicacao"] is not False:
        raise ErroAutorizacao("escopo_invalido", "publicacao precisa ser false (publicação está fora do portão)")


def avaliar(pasta_autorizacao, pasta_revogacao, lote, config, agora) -> ResultadoAutorizacao:
    """Avalia o atestado do ``lote`` já lido. NUNCA levanta: toda falha vira resultado ≠ ``valida`` (e, no portão, recusa)."""
    info = {"fingerprint": None, "nonce": None, "valido_ate": None}
    revog = {"estado": "nao_consultada", "sequencia": None, "frescorAte": None}
    try:
        try:
            if pasta_autorizacao is None:
                raise ErroAutorizacao("autorizacao_ausente", "pasta de autorização não informada")
            try:
                lido = ler_lote(pasta_autorizacao, [NOME_DOC, NOME_SIG], config)
            except ErroIntegridade as e:
                raise ErroAutorizacao("autorizacao_ausente" if e.codigo == "arquivo_ausente" else "autorizacao_ilegivel", e.codigo) from None
            doc, sig = lido.arquivos[NOME_DOC], lido.arquivos[NOME_SIG]
            try:
                d = canonico.carregar_canonico(doc)
            except NaoCanonico as e:
                raise ErroAutorizacao("nao_canonico", e.codigo) from None
            _validar_campos(d)
            try:
                assinado = assinatura.verificar(assinatura.PREFIXO_ATESTADO, doc, sig, config.ancoras)
            except ErroAssinatura as e:
                raise ErroAutorizacao(e.codigo, "assinatura do atestado") from None
            info["fingerprint"], info["nonce"], info["valido_ate"] = assinado.fingerprint, d["nonce"], d["validoAte"]   # a partir daqui, autenticados
            if d["aprovadorFingerprint"] != assinado.fingerprint:
                raise ErroAutorizacao("fingerprint_divergente", "aprovadorFingerprint ≠ chave que assinou")
            emitido, valido = _data(d["emitidoEm"], "emitidoEm"), _data(d["validoAte"], "validoAte")
            if emitido > agora + config.tolerancia_relogio:
                raise ErroAutorizacao("relogio_no_futuro", "emitido no futuro")
            if agora > valido:
                raise ErroAutorizacao("atestado_expirado", "validade vencida", resultado="expirada")
            if not emitido < valido or valido - emitido > config.validade_maxima_lote:
                raise ErroAutorizacao("janela_excedida", f"validade acima de {config.validade_maxima_lote}")
            if d["arquivos"] != list(lote.hashes):
                raise ErroAutorizacao("lote_diferente", "a lista de arquivos (caminho, hash, bytes) difere do lote efetivamente lido")
            manifesto = lote.arquivos.get("manifest.json")
            if manifesto is None:
                raise ErroAutorizacao("manifesto_ausente", "o lote não tem manifest.json")
            if d["manifestoSha256"] != hashlib.sha256(manifesto).hexdigest():
                raise ErroAutorizacao("manifesto_divergente", "manifestoSha256 ≠ hash do manifest.json lido")
            _validar_escopo(d)
            try:
                lista = revogacao.carregar(pasta_revogacao, config, agora)
            except ErroRevogacao as e:
                revog = {"estado": "nao_comprovada_atual", "sequencia": None, "frescorAte": None}
                raise ErroAutorizacao(e.codigo, "revogação não comprovada atual", resultado="revogacao_nao_comprovada_atual") from None
            revog = {"estado": "atual", "sequencia": lista.sequencia, "frescorAte": lista.valido_ate}
            alvos = {d["manifestoSha256"]} | {h["sha256"] for h in lote.hashes}
            if d["nonce"] in lista.nonces or alvos & lista.shas:
                raise ErroAutorizacao("revogada", "nonce ou hash do alvo revogado", resultado="revogada")
            return ResultadoAutorizacao("valida", "autorizacao_valida", True, revogacao=revog, **info)
        except ErroAutorizacao as e:
            return ResultadoAutorizacao(e.resultado, e.codigo, True, revogacao=revog, **info)
    except Exception:                                            # fail-closed: nada vaza
        return ResultadoAutorizacao("invalida", "erro_interno", True, revogacao=revog, **info)
