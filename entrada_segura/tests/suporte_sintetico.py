"""Suporte de teste SINTÉTICO. Todas as chaves aqui são derivadas de sementes fixas rotuladas SINTETICO e NÃO têm nenhum valor real.

O uso de ``Ed25519PrivateKey`` (assinar) é permitido APENAS neste arquivo. Âncoras sintéticas são diferentes da âncora de produção (vazia).
"""
from __future__ import annotations

import base64
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from entrada_segura import assinatura, canonico
from entrada_segura.assinatura import PREFIXO_ATESTADO, PREFIXO_REVOGACOES
from entrada_segura.fixtures_registro import ConjuntoFixture

AGORA = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
SEMENTES = {"ancora1": b"SINTETICO-TESTE-ANCORA-1", "ancora2": b"SINTETICO-TESTE-ANCORA-2", "intruso": b"SINTETICO-TESTE-INTRUSO"}


class ChaveSintetica:
    def __init__(self, rotulo: str):
        self.rotulo = rotulo
        self.privada = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(SEMENTES[rotulo]).digest())
        self.publica = self.privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.fingerprint = assinatura.fingerprint(self.publica)

    def assinar(self, prefixo: bytes, documento: bytes) -> bytes:
        return self.privada.sign(prefixo + documento)

    def arquivo_assinatura(self, prefixo: bytes, documento: bytes, **troca) -> bytes:
        d = {"algoritmo": "ed25519", "assinatura": base64.b64encode(self.assinar(prefixo, documento)).decode(),
             "chavePublica": base64.b64encode(self.publica).decode(), "schemaVersion": "1"}
        d.update(troca)
        return canonico.serializar(d)


ANCORA1, ANCORA2, INTRUSO = ChaveSintetica("ancora1"), ChaveSintetica("ancora2"), ChaveSintetica("intruso")
ANCORAS_SINTETICAS = frozenset({ANCORA1.fingerprint})


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class SemRede(unittest.TestCase):
    """Trava de rede (mesma técnica de ``produtos.tests.base``, sem importar ``produtos``): qualquer tentativa de conexão falha o teste."""

    def setUp(self):
        def _bloqueado(*a, **k):
            raise AssertionError("tentativa de acesso à rede durante o teste")
        for alvo in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection", "socket.getaddrinfo", "socket.gethostbyname"):
            p = mock.patch(alvo, side_effect=_bloqueado)
            p.start()
            self.addCleanup(p.stop)
