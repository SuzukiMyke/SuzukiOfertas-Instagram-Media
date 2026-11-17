"""Leitura do arquivo de decisões humanas (GOAL 5.6). Este módulo só LÊ.

Nenhuma automação cria ou altera esse arquivo: ele é editado manualmente por uma pessoa.
Formato::

    {"decisoesVersion": "1.0",
     "decisoes": [{"provider": "...", "productId": "...", "exportId": "<uuid da versão revisada>",
                   "decisao": "aprovado_para_rascunho | aprovado_para_publicacao | rejeitado",
                   "autor": "Nome", "data": "AAAA-MM-DDTHH:MM:SSZ", "motivo": "texto"}]}

Entradas inválidas são ignoradas e relatadas (falha segura: nunca viram aprovação).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import estados
from .leitor import decodificar_json
from .tempo import parse_data

_CHAVES = {"provider", "productId", "exportId", "decisao", "autor", "data", "motivo"}
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_AUTOR_RESERVADO = re.compile(r"\b(bot|sistema|system|automa\w*|auto|claude|script|cron|agente|ia|ai)\b", re.I)


@dataclass
class Decisao:
    provider: str
    product_id: str
    export_id: str
    decisao: str
    autor: str
    data: datetime
    data_txt: str
    motivo: str

    def como_dict(self) -> dict:
        return {"exportId": self.export_id, "decisao": self.decisao, "autor": self.autor,
                "data": self.data_txt, "motivo": self.motivo}


@dataclass
class Decisoes:
    por_produto: dict[tuple[str, str], list[Decisao]] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


def carregar(caminho: Path | str | None) -> Decisoes:
    out = Decisoes()
    if caminho is None:
        return out
    p = Path(caminho)
    if not p.is_file():
        out.avisos.append("arquivo de decisões não encontrado: nenhuma aprovação humana aplicada")
        return out
    try:
        obj = decodificar_json(p.read_bytes())
    except (OSError, ValueError) as e:
        out.avisos.append(f"arquivo de decisões inválido ({e}): nenhuma aprovação humana aplicada")
        return out
    if not isinstance(obj, dict) or not isinstance(obj.get("decisoes"), list):
        out.avisos.append("arquivo de decisões inválido (esperado {decisoes: [...]}): nenhuma aprovação aplicada")
        return out
    for i, d in enumerate(obj["decisoes"]):
        erro = _validar(d)
        if erro:
            out.avisos.append(f"decisão #{i + 1} ignorada: {erro}")
            continue
        dec = Decisao(d["provider"], d["productId"], d["exportId"], d["decisao"], d["autor"].strip(),
                      parse_data(d["data"]), d["data"], d["motivo"].strip())
        out.por_produto.setdefault((dec.provider, dec.product_id), []).append(dec)
    for lista in out.por_produto.values():
        lista.sort(key=lambda x: x.data)
    return out


def _validar(d) -> str | None:
    if not isinstance(d, dict):
        return "item não é objeto"
    if set(d) - _CHAVES:
        return "campos desconhecidos"
    for k in _CHAVES:
        if not isinstance(d.get(k), str) or not d[k].strip():
            return f"campo {k} ausente ou vazio"
    if d["decisao"] not in estados.DECISOES_HUMANAS:
        return "decisão não permitida (use aprovado_para_rascunho, aprovado_para_publicacao ou rejeitado)"
    if not _UUID.match(d["exportId"]):
        return "exportId inválido"
    if parse_data(d["data"]) is None:
        return "data inválida"
    if len(d["autor"].strip()) < 2 or _AUTOR_RESERVADO.search(d["autor"]):
        return "autor deve ser uma pessoa identificada (nome de automação não é aceito)"
    return None
