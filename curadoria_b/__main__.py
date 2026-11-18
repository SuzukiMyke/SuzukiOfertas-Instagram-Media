"""CLI: ``python3 -m curadoria_b FICHA.json --saida DIR [--agora AAAA-MM-DDTHH:MM:SSZ] [--export-id UUID]``."""
from __future__ import annotations

import argparse
import json
import sys

from produtos.tempo import parse_data, relogio_sistema

from .exportador import ErroExportacao, exportar
from .ficha import ErroFicha


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="curadoria_b", description="Ficha de curadoria manual -> exportação B (contrato 1.1).")
    ap.add_argument("ficha", help="ficha de curadoria (JSON)")
    ap.add_argument("--saida", required=True, help="pasta de saída; cria SAIDA/B/ (nunca sobrescreve)")
    ap.add_argument("--agora", default=None, help="relógio AAAA-MM-DDTHH:MM:SSZ (padrão: UTC do sistema)")
    ap.add_argument("--export-id", default=None, help="UUID da exportação (padrão: aleatório; fixe para reproduzir)")
    a = ap.parse_args(argv)
    agora = parse_data(a.agora) if a.agora else relogio_sistema()
    if agora is None:
        print("erro: --agora inválido", file=sys.stderr)
        return 2
    try:
        resumo = exportar(a.ficha, a.saida, agora, export_id=a.export_id)
    except ErroFicha as e:
        print("erro: ficha inválida", file=sys.stderr)
        for m in e.erros:
            print(f"  - {m}", file=sys.stderr)
        return 2
    except ErroExportacao as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
