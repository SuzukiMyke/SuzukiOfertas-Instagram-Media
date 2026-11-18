"""Hashes de REFERÊNCIA do comportamento anterior à B2R (capturados no commit-base ef25672 antes de qualquer alteração).

``calcular()`` recalcula, no código atual, os mesmos valores com os parâmetros PADRÃO; ``b2r_referencia.json`` guarda os valores do
commit-base. Os dois devem ser idênticos no mesmo ambiente (mesma versão do Pillow/libjpeg). Regerar só com decisão explícita:
``python3 -m tests.b2r_referencia --gravar`` (nunca para "consertar" uma regressão).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from gerador import fundo_marca
from gerador.layouts import LAYOUTS

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = Path(__file__).resolve().parent / "b2r_referencia.json"
COMMIT_BASE = "ef256724578d87b7aa60b457b991f447dd671963"
FIXTURE = RAIZ / "curadoria_b" / "exemplos_ficticios" / "ficha_valida.json"
SLIDES_ANTIGOS = {
    "curto": {"titulo": "OLÁ", "destaque": "MUNDO", "texto": "Texto curto."},
    "medio": {"titulo": "PANELA DE PRESSÃO", "destaque": "FICTÍCIA 5 LITROS", "texto": "Loja Fictícia · Arte ilustrativa"},
    "longo": {"titulo": "CARACTERÍSTICA", "destaque": "COMPROVADA", "texto": "Capacidade de cinco litros para toda a família"},
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def hashes_layouts_antigos() -> dict:
    foto = fundo_marca.gerar_fundo(0)
    out = {}
    for layout in ("foto_topo", "foto_cheia", "cartao"):
        for nome, base in SLIDES_ANTIGOS.items():
            img, areas = LAYOUTS[layout](foto, {"layout": layout, **base}, 2, 4)
            out[f"{layout}/{nome}"] = {"pixels": _sha(img.convert("RGB").tobytes()), "areas": {k: list(v) for k, v in sorted(areas.items())}}
    return out


def hashes_b2_antigo() -> dict:
    from orquestrador_b2.fluxo import executar
    from produtos.tempo import parse_data
    tmp = Path(tempfile.mkdtemp(prefix="b2ref_"))
    try:
        rel = executar(FIXTURE, tmp / "s", parse_data("2026-11-17T15:00:00Z"), aprovar_fundo_ficticio=True)
        return {"status": rel["status"], "fundo": rel["fundo"]["sha256"],
                "slides": [(s["arquivo"], s["sha256"], s["pngSha256"]) for s in rel["slides"]],
                "folha": rel["arquivos"]["folha"]["sha256"], "carrossel": json.loads(json.dumps(rel["carrossel"], sort_keys=True))}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def calcular() -> dict:
    return {
        "fundos": {str(v): _sha(fundo_marca.fundo_bytes(v)) for v in range(fundo_marca.VARIANTES)},
        "layouts": hashes_layouts_antigos(),
        "b2": hashes_b2_antigo(),
    }


def main() -> int:
    if "--gravar" in sys.argv:
        ARQUIVO.write_text(json.dumps({"commitBase": COMMIT_BASE, **calcular()}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        print("referência gravada em", ARQUIVO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
