"""CLI: python3 -m gerador <comando> ...

  listar                          mostra o catálogo
  importar ARQ [opções]           importa foto externa (Nano Banana, foto real)
  aprovar ID --por NOME           registra aprovação visual
  rejeitar ID --por NOME          registra rejeição
  carrossel CONFIG.json           gera, exporta e valida os slides
  flux "PROMPT" --confirmar       gera UMA foto FLUX (respeita cota diária)
"""
from __future__ import annotations

import argparse
import sys

from .catalogo import Catalogo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gerador", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("listar")

    pi = sub.add_parser("importar")
    pi.add_argument("arquivo")
    pi.add_argument("--provedor", default="nano-banana", choices=["nano-banana", "foto-real"])
    pi.add_argument("--origem", default=None, choices=["ia", "fotografia-real"])
    pi.add_argument("--descricao", default="")
    pi.add_argument("--prompt", default=None)
    pi.add_argument("--restricao", action="append", dest="restricoes")
    pi.add_argument("--aprovado-por", default=None, help="registra aprovação na importação")
    pi.add_argument("--nota", default=None)

    for nome in ("aprovar", "rejeitar"):
        pa = sub.add_parser(nome)
        pa.add_argument("id")
        pa.add_argument("--por", required=True)
        pa.add_argument("--nota", default=None)

    pc = sub.add_parser("carrossel")
    pc.add_argument("config")
    pc.add_argument("--saida", default=None)

    pf = sub.add_parser("flux")
    pf.add_argument("prompt")
    pf.add_argument("--descricao", default="")
    pf.add_argument("--confirmar", action="store_true")

    a = p.parse_args(argv)
    cat = Catalogo()

    if a.cmd == "listar":
        for fid, m in cat.fotos.items():
            st = (m.get("aprovacao") or {}).get("status")
            print(f"{fid:10} {m['provedor']:16} {m['largura']}x{m['altura']:<5} {st:9} {m['caminho_github']}")
        return 0

    if a.cmd == "importar":
        from .importar import ErroImportacao, importar
        origem = a.origem or ("fotografia-real" if a.provedor == "foto-real" else "ia")
        try:
            fid, nova = importar(a.arquivo, a.provedor, cat, origem, a.descricao, a.prompt,
                                 a.restricoes, a.aprovado_por, a.nota)
        except ErroImportacao as e:
            print(f"ERRO: {e}", file=sys.stderr)
            return 2
        print(f"{'Importada' if nova else 'Já existia (mesmo SHA-256)'}: {fid}")
        return 0

    if a.cmd in ("aprovar", "rejeitar"):
        cat.definir_aprovacao(a.id, "aprovada" if a.cmd == "aprovar" else "rejeitada", a.por, a.nota)
        cat.salvar()
        print(f"{a.id}: {a.cmd[:-1]}da por {a.por}")
        return 0

    if a.cmd == "carrossel":
        from .carrossel import gerar
        r = gerar(a.config, cat, a.saida)
        print(f"{r['status'].upper()}: {len(r['slides'])} slides em {r['pasta']}")
        for prob in r["problemas"]:
            print(f"  - {prob}", file=sys.stderr)
        return 0 if not r["problemas"] else 3

    if a.cmd == "flux":
        from .flux import gerar as gerar_flux
        fid = gerar_flux(a.prompt, a.confirmar, cat, a.descricao)
        print(f"Gerada: {fid} (status pendente; aprove com: python3 -m gerador aprovar {fid} --por NOME)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
