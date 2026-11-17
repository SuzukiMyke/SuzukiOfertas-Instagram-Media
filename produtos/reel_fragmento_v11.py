"""Ficha 1.1 -> fragmento de Reel (contrato v1.1 §8.8). Envolve ``reel_fragmento`` (1.0) sem alterá-lo; NÃO executa o gerador.

Além das recusas do modo 1.0: exige ficha do contrato 1.1, foto utilizável por **registro humano** e o hash do arquivo
``foto_local`` igual a ``fotoSha256``. ``source.license`` vem do ``termoId`` (registro humano), nunca do arquivo exportado.
O preço continua fora do vídeo; fonte B só gera fragmento se tiver foto autorizada (nunca com ambientação como produto).
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from .reel_fragmento import RAIZ_REPO, FragmentoRecusado, ficha_para_fragmento


def ficha_para_fragmento_v11(ficha: dict, foto_local: str | None, **kw) -> dict:
    if ficha.get("contrato") != "1.1":
        raise FragmentoRecusado("ficha não é do contrato 1.1")
    foto = ficha["foto"]
    if not foto.get("utilizavel") or not foto.get("fotoSha256") or not foto.get("termoId"):
        raise FragmentoRecusado("sem foto autorizada por registro humano (permissoes_fotos.json + termos_programas.json)")
    if not foto_local:
        raise FragmentoRecusado("informe foto_local (arquivo já importado no repositório)")
    p = Path(foto_local)
    if p.is_absolute() or ".." in p.parts or not (RAIZ_REPO / p).is_file():
        raise FragmentoRecusado("foto_local deve ser caminho relativo existente no repositório, sem '..'")
    if hashlib.sha256((RAIZ_REPO / p).read_bytes()).hexdigest() != foto["fotoSha256"]:
        raise FragmentoRecusado("hash de foto_local diverge de fotoSha256 do registro humano")
    c = copy.deepcopy(ficha)
    c["foto"]["permissionRef"] = f"termo {foto['termoId']} (registro humano)"
    return ficha_para_fragmento(c, foto_local, **kw)
