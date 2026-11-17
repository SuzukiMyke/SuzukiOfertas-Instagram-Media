"""Seleção de fotografias para os slides de um carrossel.

Regras:
- "foto": "<id>" usa a foto indicada; "foto": "auto" escolhe uma foto aprovada
  ainda não usada no carrossel (opcional: "provedor": "nano-banana" etc.).
- A mesma foto só se repete se o slide disser "reutilizar": true.
- Fotos rejeitadas nunca são usadas. Fotos pendentes só com
  "permitir_fotos_pendentes": true (prévia/rascunho interno).
- Foto ausente no disco é erro: nunca há troca silenciosa por fundo sólido.
"""
from __future__ import annotations

from .catalogo import Catalogo


class ErroSelecao(Exception):
    pass


def _status(meta: dict) -> str:
    return (meta.get("aprovacao") or {}).get("status", "pendente")


def selecionar(slides: list[dict], cat: Catalogo, permitir_pendentes: bool = False) -> list[str]:
    usadas: list[str] = []
    for i, s in enumerate(slides, 1):
        pedido = s.get("foto", "auto")
        if pedido == "auto":
            candidatas = [
                fid for fid, m in cat.fotos.items()
                if fid not in usadas
                and (_status(m) == "aprovada" or (permitir_pendentes and _status(m) == "pendente"))
                and (not s.get("provedor") or m.get("provedor") == s["provedor"])
            ]
            if not candidatas:
                raise ErroSelecao(f"Slide {i}: nenhuma foto disponível para seleção automática.")
            fid = candidatas[0]
        else:
            fid = pedido
            try:
                meta = cat.obter(fid)
            except KeyError as e:
                raise ErroSelecao(f"Slide {i}: {e}") from None
            st = _status(meta)
            if st == "rejeitada":
                raise ErroSelecao(f"Slide {i}: foto {fid} foi rejeitada.")
            if st != "aprovada" and not permitir_pendentes:
                raise ErroSelecao(f"Slide {i}: foto {fid} ainda não foi aprovada (status '{st}').")
            if fid in usadas and not s.get("reutilizar"):
                raise ErroSelecao(f"Slide {i}: foto {fid} já usada; marque \"reutilizar\": true se for intencional.")
        if not cat.caminho(fid).is_file():
            raise ErroSelecao(f"Slide {i}: arquivo da foto {fid} não encontrado. Interrompido.")
        usadas.append(fid)
    return usadas
