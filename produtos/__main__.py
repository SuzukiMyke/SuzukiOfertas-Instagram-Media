"""CLI: ``python3 -m produtos --troca PASTA --saida PASTA [--decisoes ARQ] [--agora ISO]``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .avaliacao import Configuracao
from .pipeline import processar
from .tempo import parse_data, relogio_sistema

RAIZ = Path(__file__).resolve().parent
PADRAO_TROCA = RAIZ / "exemplos_ficticios" / "troca"
PADRAO_SAIDA = RAIZ / "saida"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="produtos", description="Lê a pasta de troca, valida o contrato v1 e gera fichas.")
    ap.add_argument("--troca", default=str(PADRAO_TROCA), help="pasta de troca (somente leitura)")
    ap.add_argument("--saida", default=str(PADRAO_SAIDA), help="pasta de saída (fichas e relatórios)")
    ap.add_argument("--decisoes", default=None, help="arquivo de decisões humanas (somente leitura)")
    ap.add_argument("--agora", default=None, help="relógio fixo AAAA-MM-DDTHH:MM:SSZ (padrão: UTC do sistema)")
    ap.add_argument("--revalidacao-horas", type=float, default=24.0, help="janela de revalidação do tipo A (padrão 24)")
    ap.add_argument("--arquivo-dias", type=int, default=30, help="arquivar exportações mais antigas que N dias (padrão 30)")
    a = ap.parse_args(argv)
    agora = parse_data(a.agora) if a.agora else relogio_sistema()
    if agora is None:
        print("--agora inválido", file=sys.stderr)
        return 2
    resumo = processar(a.troca, a.saida, agora, decisoes_arquivo=a.decisoes,
                       cfg=Configuracao(revalidacao_horas=a.revalidacao_horas, arquivo_dias=a.arquivo_dias))
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
