"""Registro de foto (GOAL 5.5): só metadados; nenhuma imagem é baixada nesta etapa.

Uma foto só é considerada utilizável se ``usePermission == "confirmada"`` (e a URL existe).
Foto gerada por IA nunca representa um produto específico.
"""
from __future__ import annotations


def foto_utilizavel(foto: dict | None) -> bool:
    if not foto:
        return False
    return foto.get("usePermission") == "confirmada" and bool(foto.get("url"))


def situacao_foto(foto: dict | None) -> dict:
    """Resumo estável para a ficha: metadados + utilizável + aviso em português."""
    foto = foto or {}
    perm = foto.get("usePermission", "pendente")
    utilizavel = foto_utilizavel(foto)
    if utilizavel:
        aviso = None
    elif perm == "negada":
        aviso = "sem foto autorizada: uso da foto NEGADO pelo programa/fonte"
    else:
        aviso = "sem foto autorizada: permissão de uso pendente de confirmação"
    return {
        "url": foto.get("url"),
        "origin": foto.get("origin", "desconhecida"),
        "usePermission": perm,
        "permissionRef": foto.get("permissionRef"),
        "checkedAt": foto.get("checkedAt"),
        "utilizavel": utilizavel,
        "aviso": aviso,
    }
