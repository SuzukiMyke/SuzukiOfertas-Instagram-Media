"""Verificação Ed25519 (§3) EXCLUSIVAMENTE via ``cryptography``. Sem verificador próprio e sem fallback.

A dependência é importada de forma preguiçosa, só aqui, e apenas ``Ed25519PublicKey`` e ``InvalidSignature``. Se faltar, o resultado é
``dependencia_ausente`` (recusa). A mensagem assinada é ``PREFIXO + bytes_do_documento`` (separação de domínio).
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from . import canonico
from .erros import ErroAssinatura, NaoCanonico

PREFIXO_ATESTADO = b"SuzukiOfertas-Instagram/atestado-lote/v1\n"
PREFIXO_REVOGACOES = b"SuzukiOfertas-Instagram/revogacoes/v1\n"
CAMPOS_ASSINATURA = frozenset({"algoritmo", "assinatura", "chavePublica", "schemaVersion"})


@dataclass(frozen=True)
class ResultadoAssinatura:
    fingerprint: str


def fingerprint(chave_publica: bytes) -> str:
    return "sha256:" + hashlib.sha256(chave_publica).hexdigest()


def _importar_cripto():
    """Único ponto de importação de terceiros (monkeypatch-ável nos testes para simular a ausência)."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    return Ed25519PublicKey, InvalidSignature


def _b64_estrito(texto, tamanho: int, nome: str) -> bytes:
    if not isinstance(texto, str):
        raise ErroAssinatura("base64_invalido", f"{nome} não é texto")
    try:
        bruto = base64.b64decode(texto.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        raise ErroAssinatura("base64_invalido", f"{nome}: base64 inválido") from None
    if base64.b64encode(bruto).decode("ascii") != texto:
        raise ErroAssinatura("base64_invalido", f"{nome}: base64 não canônico")
    if len(bruto) != tamanho:
        raise ErroAssinatura("tamanho_invalido", f"{nome}: esperado {tamanho} bytes, recebido {len(bruto)}")
    return bruto


def ler_arquivo_assinatura(bytes_sig: bytes) -> tuple[bytes, bytes]:
    """``(chave_publica, assinatura)`` do arquivo de assinatura canônico; recusa campos extras/ausentes e algoritmo diferente."""
    try:
        doc = canonico.carregar_canonico(bytes_sig, max_bytes=4096)
    except NaoCanonico as e:
        raise ErroAssinatura("assinatura_nao_canonica", e.codigo) from None
    if not isinstance(doc, dict) or set(doc) != CAMPOS_ASSINATURA:
        raise ErroAssinatura("campos_da_assinatura", "campos ausentes ou extras")
    if doc["schemaVersion"] != "1" or doc["algoritmo"] != "ed25519":
        raise ErroAssinatura("algoritmo_ou_versao", "somente ed25519 / schemaVersion 1")
    return _b64_estrito(doc["chavePublica"], 32, "chavePublica"), _b64_estrito(doc["assinatura"], 64, "assinatura")


def verificar(prefixo: bytes, documento: bytes, bytes_sig: bytes, ancoras: frozenset[str]) -> ResultadoAssinatura:
    """Verifica a assinatura e exige que o fingerprint da chave esteja em ``ancoras``. Levanta ``ErroAssinatura`` (recusa) em qualquer falha."""
    chave, assinatura = ler_arquivo_assinatura(bytes_sig)
    try:
        Ed25519PublicKey, InvalidSignature = _importar_cripto()
    except ImportError:
        raise ErroAssinatura("dependencia_ausente", "biblioteca cryptography indisponível") from None
    try:
        Ed25519PublicKey.from_public_bytes(chave).verify(assinatura, prefixo + documento)
    except InvalidSignature:
        raise ErroAssinatura("assinatura_invalida", "a assinatura não confere") from None
    except ValueError:
        raise ErroAssinatura("chave_invalida", "chave pública inválida") from None
    fp = fingerprint(chave)
    if fp not in ancoras:
        raise ErroAssinatura("ancora_desconhecida", "fingerprint fora das âncoras fixadas")
    return ResultadoAssinatura(fp)
