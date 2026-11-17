"""Utilitários de teste: fábrica de produtos fictícios, relógio fixo e trava de rede."""
from __future__ import annotations

import copy
import json
import shutil
import socket
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from produtos.tempo import parse_data

AGORA = datetime(2026, 11, 17, 15, 0, 0, tzinfo=timezone.utc)
RAIZ = Path(__file__).resolve().parents[2]
EXEMPLOS = RAIZ / "produtos" / "exemplos_ficticios"


def uid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def produto_a(n: int = 1, pid: str = "A001", **over) -> dict:
    d = {
        "schemaVersion": "1.0.0", "exportId": uid(n), "exportedAt": "2026-11-17T13:05:00Z",
        "source": {"kind": "agente_publicada", "system": "SuzukiOfertas-AgenteAutomatico"},
        "product": {"id": pid, "provider": "EXEMPLO_A", "store": "Loja Fictícia", "advertiserId": "99999",
                    "title": f"Produto Fictício {pid}", "category": "Casa e Cozinha > Utensílios",
                    "categoryOrigin": "fonte",
                    "officialUrl": f"https://www.lojaficticia.example/produto/{pid.lower()}",
                    "affiliateUrl": f"https://afiliado.lojaficticia.example/ir/{pid.lower()}"},
        "price": {"amountCents": 12990, "currency": "BRL", "originalAmountCents": None,
                  "verifiedAt": "2026-11-17T13:00:00Z", "validUntil": "2026-11-17T19:00:00Z",
                  "verification": "ao_vivo"},
        "availability": "in_stock",
        "photo": {"url": f"https://cdn.lojaficticia.example/img/{pid.lower()}.jpg", "origin": "api_oficial",
                  "usePermission": "confirmada", "permissionRef": "termo-ficticio-001 (2026-11-01)",
                  "checkedAt": "2026-11-17T12:50:00Z"},
        "verifiedFacts": [],
        "publication": {"state": "publicada", "publishedAt": "2026-11-17T13:05:00Z", "channel": "Canal Fictício"},
        "references": [{"label": "Página oficial fictícia", "url": "https://www.lojaficticia.example/produto/a001"}],
        "eligibility": {"agentPublicationEligible": True, "blockReason": None},
    }
    exp = parse_data(over.get("exportedAt"))
    if exp is not None:                            # mantém as datas coerentes com a exportação deslocada
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        over.setdefault("publication__publishedAt", over["exportedAt"])
        over.setdefault("price__verifiedAt", (exp - timedelta(minutes=5)).strftime(fmt))
        over.setdefault("price__validUntil", (exp + timedelta(hours=6)).strftime(fmt))
    return mod(d, **over)


def produto_b(n: int = 4, pid: str = "B001", **over) -> dict:
    d = produto_a(n, pid)
    d["source"]["kind"] = "catalogo_candidato"
    d["product"]["provider"] = "EXEMPLO_B"
    d["product"]["affiliateUrl"] = None
    d["price"].update(verifiedAt=None, validUntil=None, verification="catalogo_sem_verificacao")
    d["publication"] = {"state": "nao_publicada", "publishedAt": None, "channel": None}
    d["eligibility"] = {"agentPublicationEligible": False, "blockReason": "catalogo_sem_verificacao_ao_vivo"}
    del d["photo"]
    return mod(d, **over)


def mod(d: dict, **over) -> dict:
    """Aplica alterações por caminho (``price__amountCents=0``); valor ``DEL`` remove a chave."""
    d = copy.deepcopy(d)
    for caminho, valor in over.items():
        partes = caminho.split("__")
        alvo = d
        for p in partes[:-1]:
            alvo = alvo[int(p)] if isinstance(alvo, list) else alvo[p]
        if valor is DEL:
            alvo.pop(partes[-1], None)
        else:
            alvo[partes[-1]] = valor
    return d


DEL = object()


def escrever(pasta: Path, nome: str, obj) -> Path:
    p = Path(pasta) / nome
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def t(valor: str) -> datetime:
    return parse_data(valor)


class Base(unittest.TestCase):
    """Todos os testes rodam com a rede bloqueada: qualquer tentativa de conexão falha o teste."""

    def setUp(self):
        def _bloqueado(*a, **k):
            raise AssertionError("tentativa de acesso à rede durante o teste")
        for alvo in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                     "socket.getaddrinfo", "socket.gethostbyname"):
            p = mock.patch(alvo, side_effect=_bloqueado)
            p.start()
            self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.troca = self.tmp / "troca"
        self.troca.mkdir()
        self.saida = self.tmp / "saida"
