"""Dados do carrossel → seleção de fotos → renderização → exportação → validação."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .catalogo import Catalogo, agora_utc, sha256_arquivo
from .layouts import LAYOUTS
from .selecao import selecionar
from .validacao import validar_slide

CAMPOS_SLIDE = {"layout", "foto", "titulo", "destaque", "texto", "foco", "reutilizar", "provedor"}


class ErroCarrossel(Exception):
    pass


def carregar(arquivo: Path) -> dict:
    dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
    if not dados.get("id") or not dados.get("slides"):
        raise ErroCarrossel("Config precisa de 'id' e 'slides'.")
    if not 1 <= len(dados["slides"]) <= 10:
        raise ErroCarrossel("Instagram aceita de 1 a 10 slides.")
    for i, s in enumerate(dados["slides"], 1):
        extras = set(s) - CAMPOS_SLIDE
        if extras:
            raise ErroCarrossel(f"Slide {i}: campos desconhecidos {sorted(extras)}")
        if s.get("layout") not in LAYOUTS:
            raise ErroCarrossel(f"Slide {i}: layout inválido. Use um de {sorted(LAYOUTS)}.")
        if not (s.get("titulo") or s.get("destaque")):
            raise ErroCarrossel(f"Slide {i}: falta 'titulo' ou 'destaque'.")
    return dados


def gerar(config: Path | dict, catalogo: Catalogo | None = None, saida: Path | None = None) -> dict:
    cat = catalogo or Catalogo()
    dados = carregar(config) if not isinstance(config, dict) else config
    slides = dados["slides"]
    pendentes = bool(dados.get("permitir_fotos_pendentes"))
    fotos = selecionar(slides, cat, pendentes)

    pasta = Path(saida) if saida else cat.raiz / "carrosseis" / dados["id"]
    pasta.mkdir(parents=True, exist_ok=True)
    total = len(slides)
    manifest = {"id": dados["id"], "gerado_em": agora_utc(), "resolucao": "1080x1350",
                "status": "rascunho" if pendentes else "pronto", "slides": []}
    problemas = []
    for i, (s, fid) in enumerate(zip(slides, fotos), 1):
        with Image.open(cat.caminho(fid)) as foto:
            img, areas = LAYOUTS[s["layout"]](foto, s, i, total)
        arq = pasta / f"slide_{i:02d}.jpg"
        img.convert("RGB").save(arq, "JPEG", quality=92, optimize=True, progressive=True)
        erros = validar_slide(arq, areas)
        problemas += [f"slide {i}: {e}" for e in erros]
        manifest["slides"].append({
            "arquivo": arq.name, "layout": s["layout"], "foto": fid,
            "status_foto": cat.obter(fid).get("aprovacao", {}).get("status"),
            "sha256": sha256_arquivo(arq), "validacao": erros or "ok",
        })
    if problemas:
        manifest["status"] = "reprovado"
    (pasta / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
    manifest["pasta"] = str(pasta)
    manifest["problemas"] = problemas
    return manifest
