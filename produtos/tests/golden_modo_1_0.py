"""Hashes golden do modo 1.0 (contrato v1.1 §11): a saída do modo 1.0 deve ser idêntica byte a byte.

Gerados a partir do commit-base ``b317f17`` ANTES de qualquer alteração do modo 1.1. Cenários fixos
(relógio injetado, dados fictícios do pacote). Para regerar (apenas com decisão explícita, nunca para
"consertar" uma regressão): ``python3 -m produtos.tests.golden_modo_1_0 --gravar``.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from produtos.avaliacao import Configuracao
from produtos.pipeline import processar
from produtos.tempo import parse_data

RAIZ = Path(__file__).resolve().parents[1]
EXEMPLOS = RAIZ / "exemplos_ficticios"
ARQUIVO = Path(__file__).resolve().parent / "golden" / "golden_modo_1_0.json"
COMMIT_BASE = "b317f17384f529bdf52abe13fd4fcc9f8680501a"

CENARIOS = {
    "exemplos_com_decisoes_15h": dict(agora="2026-11-17T15:00:00Z", decisoes=True, cfg={}),
    "exemplos_sem_decisoes_15h": dict(agora="2026-11-17T15:00:00Z", decisoes=False, cfg={}),
    "exemplos_com_decisoes_dia_seguinte": dict(agora="2026-11-18T10:00:00Z", decisoes=True, cfg={}),
    "exemplos_revalidacao_desativada": dict(agora="2026-11-17T20:00:00Z", decisoes=True,
                                            cfg=dict(revalidacao_horas=None)),
    "exemplos_arquivamento_7_dias": dict(agora="2026-11-25T15:00:00Z", decisoes=True, cfg=dict(arquivo_dias=7)),
}


def _hash_pasta(pasta: Path) -> dict:
    return {str(p.relative_to(pasta)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(pasta.rglob("*")) if p.is_file()}


def calcular() -> dict:
    saida = {}
    for nome, c in CENARIOS.items():
        with tempfile.TemporaryDirectory() as tmp:
            processar(EXEMPLOS / "troca", Path(tmp) / "saida", parse_data(c["agora"]),
                      decisoes_arquivo=(EXEMPLOS / "decisoes" / "decisoes_exemplo.json") if c["decisoes"] else None,
                      cfg=Configuracao(**c["cfg"]))
            saida[nome] = _hash_pasta(Path(tmp) / "saida")
    return saida


def main() -> int:
    if "--gravar" in sys.argv:
        ARQUIVO.write_text(json.dumps({"commitBase": COMMIT_BASE, "cenarios": calcular()}, indent=2) + "\n", encoding="utf-8")
        print("golden gravado em", ARQUIVO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
