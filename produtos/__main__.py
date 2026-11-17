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
    # --- modo 1.1 (aditivo e explícito); sem --contrato o comportamento é exatamente o do modo 1.0
    ap.add_argument("--contrato", choices=("1.0", "1.1"), default=None,
                    help="1.1 = modo 1.1 (exige --dados); sem este argumento vale o modo 1.0 de sempre")
    ap.add_argument("--dados", default=None, help="[1.1] pasta de exportações com A/ e B/ (cada uma com seu manifest.json)")
    ap.add_argument("--permissoes", default=None, help="[1.1] permissoes_fotos.json (somente leitura)")
    ap.add_argument("--termos", default=None, help="[1.1] termos_programas.json (somente leitura)")
    ap.add_argument("--fotos-dir", default=None, help="[1.1] pasta do repositório de fotos (somente leitura)")
    ap.add_argument("--legado", action="store_true", help="[1.0] confirma o uso do contrato 1.0 (exigido com --dados-reais)")
    ap.add_argument("--dados-reais", action="store_true",
                    help="entrada de dados reais: exige --contrato; 1.0 exige --legado (DESABILITADA nesta etapa)")
    for r in ("dados", "decisoes", "fotos"):
        ap.add_argument(f"--commit-{r}", default=None, help=f"[1.1] commit lido do repositório {r} (registrado no resumo)")
    a = ap.parse_args(argv)
    if a.legado or a.dados_reais:
        from .selecao_contrato import DADOS_REAIS_HABILITADO, SelecaoInvalida, selecionar
        try:
            selecionar(a.contrato, a.legado, a.dados_reais)
        except SelecaoInvalida as e:
            print(f"erro: {e}", file=sys.stderr)
            return 2
        if a.dados_reais and not DADOS_REAIS_HABILITADO:
            print("entrada de dados reais DESABILITADA nesta etapa (exige autorização própria); nada foi lido", file=sys.stderr)
            return 3
    if a.contrato == "1.1":
        if not a.dados:
            print("modo 1.1 exige --dados (pasta com A/ e B/)", file=sys.stderr)
            return 2
        from .avaliacao_v11 import ConfiguracaoV11
        from .pipeline_v11 import processar_v11
        agora = parse_data(a.agora) if a.agora else relogio_sistema()
        if agora is None:
            print("--agora inválido", file=sys.stderr)
            return 2
        try:
            resumo = processar_v11(
                a.dados, a.saida, agora, decisoes_arquivo=a.decisoes, permissoes_arquivo=a.permissoes,
                termos_arquivo=a.termos, fotos_dir=a.fotos_dir,
                cfg=ConfiguracaoV11(revalidacao_horas=a.revalidacao_horas, arquivo_dias=a.arquivo_dias),
                commits_lidos={r: getattr(a, f"commit_{r}") for r in ("dados", "decisoes", "fotos")
                               if getattr(a, f"commit_{r}")})
        except ValueError as e:
            print(f"erro: {e}", file=sys.stderr)
            return 2
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        return 0
    if a.dados or a.permissoes or a.termos or a.fotos_dir:
        print("argumentos do modo 1.1 exigem --contrato 1.1", file=sys.stderr)
        return 2
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
