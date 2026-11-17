"""Registros humanos de foto (contrato v1.1 §8 e §10). Este módulo só LÊ; nunca grava.

Arquivos (repositório de decisões, editados somente por pessoa identificada):
- ``termos_programas.json``  {"schemaVersion": "1.0", "termos": [{termoId, programa, tipoEvidencia, escopo,
  referencia, arquivoEvidencia, evidenciaSha256, capturadoEm, autor}]}
- ``permissoes_fotos.json``  {"schemaVersion": "1.0", "permissoes": [{provider, productId, status, termoId,
  fotoSha256, autor, data, motivo}]}

Uma foto real só é utilizável com TODAS as condições (§8.4): status ``confirmada`` (a mais recente do produto),
``termoId`` existente e com escopo do provedor, hash do arquivo local igual a ``fotoSha256`` (arquivo em
``<fotos>/fotos/<sha256>.jpg``, ≤ 2 MB, assinatura JPEG/PNG/WebP), evidência do termo íntegra (hash) e
``autor`` que não seja automação. ``photo.usePermission`` do arquivo exportado é só informativo e **nunca** concede uso.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .decisoes import _AUTOR_RESERVADO
from .leitor import decodificar_json
from .tempo import parse_data

TIPOS_EVIDENCIA = ("termo_programa", "autorizacao_escrita", "imagem_propria", "licenca_banco", "dominio_publico_cc")
STATUS = ("confirmada", "negada")
LIMITE_BYTES = 2 * 1024 * 1024
_SHA = re.compile(r"^[0-9a-f]{64}$")
_CH_TERMO = {"termoId", "programa", "tipoEvidencia", "escopo", "referencia", "arquivoEvidencia", "evidenciaSha256",
             "capturadoEm", "autor"}
_CH_PERM = {"provider", "productId", "status", "termoId", "fotoSha256", "autor", "data", "motivo"}


@dataclass
class Registros:
    termos: dict[str, dict] = field(default_factory=dict)
    permissoes: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


def sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def tipo_imagem(dados: bytes) -> str | None:
    if dados[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    return None


def validar_arquivo_foto(dados: bytes) -> str | None:
    """Política planejada para fotos (§2): devolve o motivo da recusa ou ``None`` se aceita."""
    if len(dados) > LIMITE_BYTES:
        return "arquivo maior que 2 MB"
    if tipo_imagem(dados) is None:
        return "tipo inválido (esperado JPEG, PNG ou WebP por assinatura)"
    return None


def _autor_ok(autor) -> bool:
    return isinstance(autor, str) and len(autor.strip()) >= 2 and not _AUTOR_RESERVADO.search(autor)


def _ler(caminho, out: Registros, chave: str, nome: str):
    if caminho is None:
        return None
    p = Path(caminho)
    if not p.is_file():
        out.avisos.append(f"{nome} não encontrado: nenhum registro humano aplicado")
        return None
    try:
        obj = decodificar_json(p.read_bytes())
    except (OSError, ValueError) as e:
        out.avisos.append(f"{nome} inválido ({e}): nenhum registro humano aplicado")
        return None
    if not isinstance(obj, dict) or obj.get("schemaVersion") != "1.0" or not isinstance(obj.get(chave), list):
        out.avisos.append(f"{nome} inválido (esperado schemaVersion 1.0 e lista '{chave}')")
        return None
    return obj[chave]


def carregar(termos_arquivo=None, permissoes_arquivo=None) -> Registros:
    out = Registros()
    for i, t in enumerate(_ler(termos_arquivo, out, "termos", "termos_programas.json") or []):
        erro = _erro_termo(t)
        if erro:
            out.avisos.append(f"termo #{i + 1} ignorado: {erro}")
        elif t["termoId"] in out.termos:
            out.avisos.append(f"termo #{i + 1} ignorado: termoId duplicado")
        else:
            out.termos[t["termoId"]] = t
    for i, p in enumerate(_ler(permissoes_arquivo, out, "permissoes", "permissoes_fotos.json") or []):
        erro = _erro_perm(p)
        if erro:
            out.avisos.append(f"permissão #{i + 1} ignorada: {erro}")
        else:
            out.permissoes.setdefault((p["provider"], p["productId"]), []).append(p)
    for lista in out.permissoes.values():
        lista.sort(key=lambda x: parse_data(x["data"]))
    return out


def _erro_termo(t) -> str | None:
    if not isinstance(t, dict) or set(t) != _CH_TERMO:
        return "campos ausentes ou desconhecidos"
    if any(not isinstance(t[k], str) or not t[k].strip() for k in _CH_TERMO):
        return "campo vazio ou não textual"
    if t["tipoEvidencia"] not in TIPOS_EVIDENCIA:
        return "tipoEvidencia desconhecido"
    if not _SHA.match(t["evidenciaSha256"]):
        return "evidenciaSha256 inválido"
    if parse_data(t["capturadoEm"]) is None:
        return "capturadoEm inválido"
    if not _autor_ok(t["autor"]):
        return "autor deve ser pessoa identificada (automação não é aceita)"
    return None


def _erro_perm(p) -> str | None:
    if not isinstance(p, dict) or set(p) != _CH_PERM:
        return "campos ausentes ou desconhecidos"
    if any(not isinstance(p[k], str) or not p[k].strip() for k in _CH_PERM):
        return "campo vazio ou não textual"
    if p["status"] not in STATUS:
        return "status deve ser confirmada ou negada"
    if not _SHA.match(p["fotoSha256"]):
        return "fotoSha256 inválido"
    if parse_data(p["data"]) is None:
        return "data inválida"
    if not _autor_ok(p["autor"]):
        return "autor deve ser pessoa identificada (automação não é aceita)"
    return None


def avaliar_foto(provider: str, product_id: str, reg: Registros, fotos_dir, url_exportada: str | None = None) -> dict:
    """Situação da foto no modo 1.1. Sempre devolve ``utilizavel`` e ``motivo``; nunca concede por dados exportados."""
    base = {"utilizavel": False, "fotoSha256": None, "termoId": None, "motivo": None}
    lista = reg.permissoes.get((provider, product_id), [])
    if not lista:
        return {**base, "motivo": "sem registro humano de permissão de foto"}
    p = lista[-1]                                    # vale o registro mais recente (negada posterior revoga)
    base.update(fotoSha256=p["fotoSha256"], termoId=p["termoId"])
    if p["status"] != "confirmada":
        return {**base, "motivo": "permissão NEGADA ou revogada por registro humano"}
    termo = reg.termos.get(p["termoId"])
    if termo is None:
        return {**base, "motivo": "termoId inexistente em termos_programas.json"}
    if termo["escopo"].lower() != f"provider:{provider}".lower():
        return {**base, "motivo": "escopo do termo não cobre o provedor do produto"}
    if url_exportada and termo["referencia"].strip() == url_exportada.strip():
        return {**base, "motivo": "evidência não pode ser a URL da foto exportada pelo agente"}
    if fotos_dir is None:
        return {**base, "motivo": "repositório de fotos não informado: hash do arquivo não verificável"}
    raiz = Path(fotos_dir)
    arq = raiz / "fotos" / f"{p['fotoSha256']}.jpg"
    if arq.is_symlink() or not arq.is_file():
        return {**base, "motivo": "arquivo da foto ausente no repositório de fotos"}
    dados = arq.read_bytes()
    recusa = validar_arquivo_foto(dados)
    if recusa:
        return {**base, "motivo": f"arquivo da foto recusado: {recusa}"}
    if sha256_bytes(dados) != p["fotoSha256"]:
        return {**base, "motivo": "hash do arquivo local diverge de fotoSha256 (arquivo alterado ou renomeado)"}
    ev = raiz / "evidencias" / termo["arquivoEvidencia"]
    if ".." in Path(termo["arquivoEvidencia"]).parts or Path(termo["arquivoEvidencia"]).is_absolute():
        return {**base, "motivo": "arquivoEvidencia com caminho inválido"}
    if ev.is_symlink() or not ev.is_file():
        return {**base, "motivo": "arquivo de evidência ausente no repositório de fotos"}
    if sha256_bytes(ev.read_bytes()) != termo["evidenciaSha256"]:
        return {**base, "motivo": "hash da evidência diverge de evidenciaSha256"}
    return {**base, "utilizavel": True, "motivo": None, "autor": p["autor"], "data": p["data"]}
