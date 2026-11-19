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


# ---------------------------------------------------------------------------------------------------------------- lotes, atestados, listas
from dataclasses import replace  # noqa: E402

from entrada_segura.fixtures_registro import ConjuntoFixture  # noqa: E402,F811
from entrada_segura.politica import PRODUCAO, ConfigVerificacao  # noqa: E402

NONCE = "ab" * 16
LOTE_ID = "LOTE-SINTETICO-001"


def config_sintetica(**kw) -> ConfigVerificacao:
    """Configuração SINTÉTICA de biblioteca (nunca a de produção): âncora sintética, flags e relógio injetados."""
    base = dict(ancoras=ANCORAS_SINTETICAS, conjuntos=(), dados_reais_habilitado=False, produtos_reais_habilitado=False, relogio=lambda: AGORA)
    base.update(kw)
    return ConfigVerificacao(**base)


def lote_ficticio(pasta: Path, urls=("https://www.lojaficticia.example/produto/a001",), *, manifesto=True, extra=None) -> list[str]:
    """Cria um lote de teste (hosts ``.example`` por padrão) e devolve a lista fechada de arquivos."""
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "produto_A001.json").write_bytes(canonico.serializar({"id": "A001", "titulo": "Produto Fictício", "urls": list(urls)}))
    arquivos = ["produto_A001.json"]
    for nome, conteudo in (extra or {}).items():
        (pasta / nome).parent.mkdir(parents=True, exist_ok=True)
        (pasta / nome).write_bytes(conteudo)
        arquivos.append(nome)
    if manifesto:
        itens = [{"name": n, "sha256": sha((pasta / n).read_bytes())} for n in sorted(arquivos)]
        (pasta / "manifest.json").write_bytes(canonico.serializar({"manifestVersion": "1.0", "files": itens}))
        arquivos.append("manifest.json")
    return sorted(arquivos)


def hashes_do_lote(pasta: Path, arquivos) -> list[dict]:
    return [{"caminhoRelativo": a, "sha256": sha((pasta / a).read_bytes()), "bytes": len((pasta / a).read_bytes())} for a in sorted(arquivos)]


def dados_atestado(pasta_lote: Path, nomes, **ov) -> dict:
    d = {"schemaVersion": "1", "tipo": "autorizacao_lote", "loteId": LOTE_ID, "arquivos": hashes_do_lote(pasta_lote, nomes),
         "manifestoSha256": sha((pasta_lote / "manifest.json").read_bytes()) if (pasta_lote / "manifest.json").exists() else "0" * 64,
         "escopo": {"contrato": "1.1", "usos": ["carrossel"], "produtosMax": 10, "publicacao": False},
         "emitidoEm": iso(AGORA - timedelta(hours=1)), "validoAte": iso(AGORA + timedelta(days=2)), "nonce": NONCE, "versaoRegras": "20.1",
         "aprovadorFingerprint": ANCORA1.fingerprint,
         "declaracao": "Declaro ter revisado este lote exato de bytes e autorizo o processamento descrito no escopo."}
    for k, v in ov.items():
        if v is REMOVER:
            d.pop(k, None)
        else:
            d[k] = v
    return d


REMOVER = object()


def escrever_atestado(pasta: Path, pasta_lote: Path, nomes, *, chave=None, doc_bytes=None, sig_bytes=None, **ov) -> tuple[bytes, bytes]:
    """Grava ``autorizacao_lote.json`` e ``.sig.json`` em ``pasta`` e devolve ``(doc, sig)``. ``doc_bytes``/``sig_bytes`` substituem os gerados."""
    chave = chave or ANCORA1
    pasta.mkdir(parents=True, exist_ok=True)
    doc = doc_bytes if doc_bytes is not None else canonico.serializar(dados_atestado(pasta_lote, nomes, **ov))
    sig = sig_bytes if sig_bytes is not None else chave.arquivo_assinatura(PREFIXO_ATESTADO, doc)
    (pasta / "autorizacao_lote.json").write_bytes(doc)
    (pasta / "autorizacao_lote.sig.json").write_bytes(sig)
    return doc, sig


def dados_revogacoes(**ov) -> dict:
    d = {"schemaVersion": "1", "tipo": "revogacoes", "sequencia": 5, "emitidoEm": iso(AGORA - timedelta(hours=1)),
         "validoAte": iso(AGORA + timedelta(hours=12)), "revogados": [], "aprovadorFingerprint": ANCORA1.fingerprint}
    for k, v in ov.items():
        if v is REMOVER:
            d.pop(k, None)
        else:
            d[k] = v
    return d


def escrever_revogacoes(pasta: Path, *, chave=None, doc_bytes=None, sig_bytes=None, **ov) -> tuple[bytes, bytes]:
    chave = chave or ANCORA1
    pasta.mkdir(parents=True, exist_ok=True)
    doc = doc_bytes if doc_bytes is not None else canonico.serializar(dados_revogacoes(**ov))
    sig = sig_bytes if sig_bytes is not None else chave.arquivo_assinatura(PREFIXO_REVOGACOES, doc)
    (pasta / "revogacoes.json").write_bytes(doc)
    (pasta / "revogacoes.sig.json").write_bytes(sig)
    return doc, sig


def conjunto_exato(pasta: Path, arquivos, id_="sintetico/lote") -> ConjuntoFixture:
    """Mecanismo isolado de teste: conjunto exato dos arquivos que o teste ACABOU de gerar (só para configuração sintética)."""
    return ConjuntoFixture(id_, "sintetico", {a: sha((pasta / a).read_bytes()) for a in arquivos})
