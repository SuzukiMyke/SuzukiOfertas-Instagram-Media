"""Linha de comando.

  python -m reel_gen build    <config.json> [--out DIR]   renderiza + valida + relatório
  python -m reel_gen cta      <config.json> [--out DIR]   renderiza e valida só o CTA
  python -m reel_gen validate <config.json> [--video MP4] [--out DIR]
  python -m reel_gen check    <config.json>               esquema + regras + tempos + camadas (sem FFmpeg)
  python -m reel_gen probe    <video.mp4>                 resumo ffprobe
  python -m reel_gen synth    [<spec.json>]               gera os fundos sintéticos de demonstração

Execute a partir da pasta ``reels/``. Caminhos dentro das configs são relativos à raiz do repositório.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import REELS_ROOT, ConfigError, load_config


def _print_checks(rep: dict) -> None:
    for c in rep.get("checks", []):
        mark = "OK " if c["ok"] else ("ERRO" if c["blocking"] else "AVISO")
        print(f"  [{mark}] {c['check']}: {c['detail']}")
    for w in rep.get("warnings", []):
        print(f"  [AVISO] {w}")
    for e in rep.get("errors", []):
        print(f"  [ERRO] {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reel_gen", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "cta", "validate", "check"):
        p = sub.add_parser(name)
        p.add_argument("config")
        p.add_argument("--out", default=None)
        if name == "validate":
            p.add_argument("--video", default=None)
    p = sub.add_parser("probe")
    p.add_argument("video")
    p = sub.add_parser("synth")
    p.add_argument("spec", nargs="?", default=str(REELS_ROOT / "configs" / "synth_assets.json"))
    a = ap.parse_args(argv)

    try:
        if a.cmd == "probe":
            from .validate import moov_before_mdat, probe
            info = probe(a.video)
            info["faststart"] = moov_before_mdat(a.video)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0
        if a.cmd == "synth":
            from .synth import generate_all
            for p in generate_all(a.spec):
                print(p)
            return 0
        if a.cmd == "check":
            from .pipeline import prepare
            cfg = load_config(a.config)
            plan = prepare(cfg, work_root=Path(a.out) / "work" if a.out else None)
            print(f"{cfg['id']}: duração planejada {plan['timeline'].total:.2f} s, "
                  f"{sum(len(s['layers']) for s in plan['segments'])} camadas")
            _print_checks(plan)
            return 1 if plan["errors"] else 0
        from . import pipeline
        out = Path(a.out) if a.out else None
        if a.cmd == "validate":
            rep = pipeline.validate_existing(a.config, a.video, out)
        elif a.cmd == "cta":
            rep = pipeline.render_cta_only(a.config, out)
        else:
            rep = pipeline.build(a.config, out)
        print(f"{rep['id']}: {'APROVADO (técnico)' if rep['approved_technical'] else 'REPROVADO'}"
              f" — {rep.get('video_path')}")
        if "render" in rep:
            print(f"  render {rep['render']['wall_s']} s · pico {rep['render']['peak_rss_mb']} MB · "
                  f"duração {rep['duration_s']:.3f} s · sha256 {rep['sha256'][:16]}…")
        _print_checks(rep)
        return 0 if rep["approved_technical"] else 1
    except ConfigError as e:
        print("Config/conteúdo inválido:", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        return 2
