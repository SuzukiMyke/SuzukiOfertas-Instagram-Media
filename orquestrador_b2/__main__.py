"""CLI: ``python3 -m orquestrador_b2 FICHA.json --saida DIR [--agora ISO] [--aprovar-fundo-ficticio] [--estilo auto|v1|v2] [--whatsapp URL] [--telegram URL]``.

Códigos de saída: 0 concluído · 2 ficha rejeitada/bloqueio/uso inválido · 3 aprovação da imagem pendente.
"""
from __future__ import annotations

import argparse
import json
import sys

from produtos.tempo import parse_data, relogio_sistema

from .fluxo import ErroFluxo, executar


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="orquestrador_b2", description="Carrossel editorial FICTÍCIO ponta a ponta (sem publicar).")
    ap.add_argument("ficha", help="ficha de curadoria (JSON; fixture fictícia)")
    ap.add_argument("--saida", required=True, help="pasta de saída FORA do repositório")
    ap.add_argument("--agora", default=None, help="relógio AAAA-MM-DDTHH:MM:SSZ (padrão: UTC do sistema)")
    ap.add_argument("--aprovar-fundo-ficticio", action="store_true",
                    help="aprovação de TESTE do fundo, só para a fixture fictícia reconhecida; sem valor de homologação humana")
    ap.add_argument("--whatsapp", default=None, help="link oficial do canal do WhatsApp (somente se fornecido)")
    ap.add_argument("--telegram", default=None, help="link oficial do canal do Telegram (somente se fornecido)")
    ap.add_argument("--estilo", choices=("auto", "v1", "v2"), default="auto",
                    help="v1 reproduz a B2; v2 = estilo editorial B2R; auto: v1 para a fixture legada da B2 e v2 para as demais")
    ap.add_argument("--variante", type=int, default=0, help="variante do fundo de marca (0 a 11)")
    a = ap.parse_args(argv)
    agora = parse_data(a.agora) if a.agora else relogio_sistema()
    if agora is None:
        print("erro: --agora inválido", file=sys.stderr)
        return 2
    links = {k: v for k, v in (("whatsapp", a.whatsapp), ("telegram", a.telegram)) if v}
    try:
        rel = executar(a.ficha, a.saida, agora, aprovar_fundo_ficticio=a.aprovar_fundo_ficticio, links_oficiais=links or None,
                       variante=a.variante, estilo=a.estilo)
    except (ErroFluxo, ValueError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"status": rel["status"], "slides": len(rel.get("slides", [])), "bloqueios": [b["codigo"] for b in rel["bloqueios"]],
                      "relatorio": "relatorio_b2.json"}, ensure_ascii=False, indent=2))
    return {"concluido": 0, "aprovacao_pendente": 3}.get(rel["status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
