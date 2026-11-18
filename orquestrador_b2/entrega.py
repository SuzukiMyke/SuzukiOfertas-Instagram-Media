"""Entrega visual B2R: gera os três carrosséis fictícios, a folha geral e o relatório consolidado (tudo FORA do repositório).

``python3 -m orquestrador_b2.entrega --saida DIR [--agora ISO]``. Usa a aprovação de TESTE das fixtures reconhecidas (sem valor de
homologação humana). Nada é publicado, agendado nem enviado; sem rede.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from produtos.tempo import formatar, parse_data, relogio_sistema

from .estilo_v2 import FIXTURES_B2R
from .fluxo import executar
from .folha import gerar_folha_geral

PASTA_FIXTURES = Path(__file__).resolve().parent / "exemplos_ficticios"


def entregar(saida, agora) -> dict:
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    carrosseis, resumo = {}, []
    for info in sorted(FIXTURES_B2R.values(), key=lambda i: i["id"]):
        nome = Path(info["arquivo"]).stem.replace("ficha_", "")
        rel = executar(PASTA_FIXTURES / info["arquivo"], saida / nome, agora, aprovar_fundo_ficticio=True, estilo="v2")
        pngs = [saida / nome / "slides_png" / s["png"] for s in rel.get("slides", [])]
        if rel["status"] == "concluido":
            carrosseis[nome] = pngs
        resumo.append({"carrossel": nome, "ficha": info["id"], "status": rel["status"], "slides": len(pngs),
                       "contrasteMin": min((m["contraste_min"] for m in rel.get("validacaoV2", [])), default=None),
                       "bloqueios": [b["codigo"] for b in rel["bloqueios"]]})
    geral = gerar_folha_geral(carrosseis, saida / "folha_geral.png") if carrosseis else None
    out = {"geradoEm": formatar(agora), "carrosseis": resumo, "folhaGeral": geral,
           "restricoes": {"rede": "nao_utilizada", "publicacao": "nao_realizada", "agendamento": "nao_realizado"}}
    (saida / "relatorio_consolidado.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    L = ["# Relatório consolidado — entrega visual B2R", "", "> RASCUNHO FICTÍCIO — NÃO PUBLICAR. Verificações automáticas; a aprovação visual definitiva é humana.", "",
         "| Carrossel | Ficha | Status | Slides | Contraste mín. |", "|---|---|---|---|---|"]
    L += [f"| {r['carrossel']} | {r['ficha']} | {r['status']} | {r['slides']} | {r['contrasteMin']}:1 |" for r in resumo]
    if geral:
        L += ["", f"Folha geral: `{geral['arquivo']}` ({geral['largura']}×{geral['altura']}, {geral['slides']} slides)."]
    L += ["", "Aprovação das imagens: aprovação de TESTE das fixtures fictícias, sem valor de homologação humana.", ""]
    (saida / "relatorio_consolidado.md").write_text("\n".join(L), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="orquestrador_b2.entrega")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--agora", default=None)
    a = ap.parse_args(argv)
    agora = parse_data(a.agora) if a.agora else relogio_sistema()
    if agora is None:
        print("erro: --agora inválido", file=sys.stderr)
        return 2
    out = entregar(a.saida, agora)
    print(json.dumps([{k: r[k] for k in ("carrossel", "status", "slides")} for r in out["carrosseis"]], ensure_ascii=False))
    return 0 if all(r["status"] == "concluido" for r in out["carrosseis"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
