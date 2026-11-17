"""Ficha aprovada -> fragmento de configuração do gerador de Reels (GOAL 5.7). NÃO executa o gerador.

Formato real conferido na branch-base (``reels/reel_gen/config.py``, ``reels/configs/*.json``):
o fragmento é um objeto parcial com ``scenes`` cujas cenas seguem o esquema ``SCENE`` do gerador
(``source.kind = real_photo``, ``source.path`` local, ``camera``, ``transition_out`` ...).

Divergências em relação ao plano (documentadas em ``produtos/README.md``):
- o gerador precisa de **arquivo de imagem local** (``source.path``), mas a ficha só tem a URL da foto
  e esta etapa não baixa imagens: o chamador informa ``foto_local`` (foto já importada/catalogada);
- ``price``/``discount``/``stock``/``rating`` existem no esquema da cena, mas o preço fica **fora do
  vídeo**: o fragmento nunca os preenche; a ficha traz o aviso para a legenda.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

from . import estados

RAIZ_REPO = Path(__file__).resolve().parent.parent
CATEGORIA_NEUTRA = "Produto selecionado"
TITULO_LONGO = 60

CAMERA_PADRAO = {"zoom_start": 1.0, "zoom_end": 1.1, "pan_start": [0.5, 0.55], "pan_end": [0.5, 0.45],
                 "easing": "ease_out"}
TRANSICAO_PADRAO = {"type": "fade", "duration": 0.4}


class FragmentoRecusado(ValueError):
    """Ficha não pode virar fragmento (estado, foto ou caminho inadequados)."""


def _slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")
    return s[:48] or "produto"


def ficha_para_fragmento(ficha: dict, foto_local: str | None, *, duracao: float = 4.4,
                         camera: dict | None = None, transicao: dict | None = None) -> dict:
    """Devolve ``{"fragmento": {...}, "avisos": [...], "legenda_aviso": str}``.

    Recusa (``FragmentoRecusado``) se a ficha não estiver aprovada por humano, se a foto não estiver
    autorizada ou se ``foto_local`` não for informada. IA nunca substitui a foto do produto.
    """
    if ficha["estado"] not in estados.USAVEL_EM_RASCUNHO:
        raise FragmentoRecusado(f"estado '{ficha['estado']}' não permite rascunho: exige aprovação humana registrada")
    foto = ficha["foto"]
    if not foto["utilizavel"]:
        raise FragmentoRecusado("sem foto autorizada: Reel só com foto de produto autorizada (IA não substitui)")
    if not foto_local:
        raise FragmentoRecusado("informe foto_local (arquivo já importado no repositório); esta etapa não baixa imagens")
    p = Path(foto_local)
    if p.is_absolute() or ".." in p.parts:
        raise FragmentoRecusado("foto_local deve ser caminho relativo à raiz do repositório, sem '..'")
    if not (RAIZ_REPO / p).is_file():
        raise FragmentoRecusado("foto_local não existe no repositório")

    prod = ficha["produto"]
    avisos = []
    if len(prod["title"]) > TITULO_LONGO:
        avisos.append(f"título com mais de {TITULO_LONGO} caracteres: revisar a quebra de linha na tela")
    if prod["category"] is None:
        avisos.append(f"categoria ausente: usada a categoria neutra '{CATEGORIA_NEUTRA}'")
    cena = {
        "id": f"p_{_slug(prod['provider'] + '_' + prod['id'])}",
        "category": prod["category"] or CATEGORIA_NEUTRA,
        "duration": duracao,
        "source": {
            "path": p.as_posix(), "kind": "real_photo",
            "origin": f"{foto['origin']} ({prod['store']})",
            "license": f"permissão de uso confirmada: {foto['permissionRef']}",
            "catalog_id": f"produto:{prod['provider']}:{prod['id']}",
        },
        "title": prod["title"],
        "subtitle": f"Na {prod['store']}",
        "camera": copy.deepcopy(camera or CAMERA_PADRAO),
        "text_animation": "slide_up",
        "transition_out": copy.deepcopy(transicao or TRANSICAO_PADRAO),
    }
    return {
        "fragmento": {"scenes": [cena]},
        "avisos": avisos,
        "legenda_aviso": "Publicidade. Preços e condições podem mudar; confira no link. Preço fora do vídeo.",
    }


def validar_fragmento(fragmento: dict, config_base: str = "reels/configs/pilot_demo_01.json") -> tuple[list[str], list[str]]:
    """Valida o fragmento contra o formato REAL do gerador, sem executá-lo.

    Substitui as cenas da config-base pelas do fragmento, normaliza (esquema) e aplica as regras de
    conteúdo (``check_rules``). Devolve ``(erros, avisos)``.
    """
    reels = str(RAIZ_REPO / "reels")
    if reels not in sys.path:
        sys.path.insert(0, reels)
    from reel_gen.config import ConfigError, load_json, normalize, resolve_path
    from reel_gen.rules import check_rules

    raw = load_json(resolve_path(config_base))
    raw["scenes"] = copy.deepcopy(fragmento["scenes"])
    raw["hook"]["background"] = "brand"            # a base referencia cena 0 por padrão; independe do fragmento
    try:
        cfg = normalize(raw)
    except ConfigError as e:
        return list(e.errors), []
    return check_rules(cfg)
