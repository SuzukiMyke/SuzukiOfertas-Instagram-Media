"""Manifesto estrito do modo 1.1 (contrato v1.1 §16.1, P-01). Módulo novo; o parser do modo 1.0 (``leitor._ler_manifesto``) não muda.

Formato obrigatório (nenhum outro campo é aceito, em nenhum nível)::

    {"manifestVersion": "1.0", "generatedAt": "AAAA-MM-DDTHH:MM:SSZ", "count": N,
     "files": [{"name": "arquivo.json", "sha256": "<64 hex>", "bytes": N}, ...]}

Regras: ``manifestVersion`` texto ``MAJOR.MINOR[.PATCH]`` com major 1; ``generatedAt`` data UTC válida e não futura
(tolerância do leitor); ``count`` inteiro igual ao tamanho de ``files``; ``name`` simples (sem caminho, oculto, controle ou
invisível; termina em ``.json``; nunca ``manifest.json``; único); ``sha256`` com 64 hexadecimais; ``bytes`` inteiro não
negativo e dentro do limite do leitor. O leitor 1.1 ainda confere ``count`` × arquivos presentes, ``sha256`` e ``bytes``
contra o conteúdo real. Mensagens citam o caminho do campo, nunca o valor.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .leitor import MANIFESTO, TAMANHO_MAX, decodificar_json
from .tempo import parse_data

MAX_ARQUIVOS = 1000
MAX_NOME = 200
CAMPOS_RAIZ = {"manifestVersion", "generatedAt", "count", "files"}
CAMPOS_ITEM = {"name", "sha256", "bytes"}
_VERSAO = re.compile(r"^(\d{1,3})\.(\d{1,5})(?:\.(\d{1,5}))?$")
_SHA = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass
class Manifesto:
    versao: str
    gerado_em: datetime
    count: int
    itens: dict[str, dict] = field(default_factory=dict)       # name -> {"sha256", "bytes"}


def _inteiro(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _nome_ruim(n) -> str | None:
    if not isinstance(n, str) or not n:
        return "nome ausente ou não textual"
    if len(n) > MAX_NOME:
        return f"nome com mais de {MAX_NOME} caracteres"
    if "/" in n or "\\" in n or n in (".", "..") or n.startswith("."):
        return "nome não pode ter caminho nem ser oculto"
    if any(unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn") for c in n):
        return "nome com caractere de controle ou invisível"
    if not n.endswith(".json") or n == MANIFESTO:
        return "nome deve terminar em .json e não pode ser manifest.json"
    return None


def ler_manifesto_estrito(caminho: Path, agora: datetime, *, tolerancia_futuro_min: int = 5) -> tuple[Manifesto | None, list[str]]:
    """Devolve ``(manifesto, [])`` ou ``(None, motivos)``; todos os problemas de formato são listados."""
    try:
        if caminho.stat().st_size > TAMANHO_MAX:
            return None, [f"manifesto maior que {TAMANHO_MAX} bytes"]
        obj = decodificar_json(caminho.read_bytes())
    except (OSError, ValueError) as e:
        return None, [f"manifesto ilegível: {e}"]
    if not isinstance(obj, dict):
        return None, ["manifesto inválido: esperado objeto JSON"]
    erros: list[str] = []
    for k in sorted(set(obj) - CAMPOS_RAIZ):
        erros.append(f"manifesto: campo desconhecido '{str(k)[:40]}'")
    for k in sorted(CAMPOS_RAIZ - set(obj)):
        erros.append(f"manifesto: campo obrigatório ausente: {k}")
    versao = obj.get("manifestVersion")
    if "manifestVersion" in obj:
        m = _VERSAO.match(versao) if isinstance(versao, str) else None
        if not m:
            erros.append("manifestVersion: esperado texto MAJOR.MINOR[.PATCH]")
        elif m.group(1) != "1":
            erros.append("manifestVersion: versão major desconhecida (aceita: 1.x)")
    gerado = parse_data(obj.get("generatedAt")) if "generatedAt" in obj else None
    if "generatedAt" in obj:
        if gerado is None:
            erros.append("generatedAt: data/hora UTC inválida (AAAA-MM-DDTHH:MM:SSZ)")
        elif gerado > agora + timedelta(minutes=tolerancia_futuro_min):
            erros.append("generatedAt: data no futuro")
    if "count" in obj and (not _inteiro(obj["count"]) or obj["count"] < 0):
        erros.append("count: esperado inteiro não negativo")
    itens: dict[str, dict] = {}
    arquivos = obj.get("files")
    if "files" in obj:
        if not isinstance(arquivos, list):
            erros.append("files: esperada lista")
        elif len(arquivos) > MAX_ARQUIVOS:
            erros.append(f"files: mais de {MAX_ARQUIVOS} itens")
        else:
            for i, it in enumerate(arquivos):
                c = f"files[{i}]"
                if not isinstance(it, dict):
                    erros.append(f"{c}: esperado objeto")
                    continue
                for k in sorted(set(it) - CAMPOS_ITEM):
                    erros.append(f"{c}: campo desconhecido '{str(k)[:40]}'")
                for k in sorted(CAMPOS_ITEM - set(it)):
                    erros.append(f"{c}.{k}: campo obrigatório ausente")
                nome, sha, b = it.get("name"), it.get("sha256"), it.get("bytes")
                if "name" in it:
                    ruim = _nome_ruim(nome)
                    if ruim:
                        erros.append(f"{c}.name: {ruim}")
                    elif nome in itens:
                        erros.append(f"{c}.name: nome duplicado no manifesto")
                if "sha256" in it and not (isinstance(sha, str) and _SHA.match(sha)):
                    erros.append(f"{c}.sha256: esperado 64 caracteres hexadecimais")
                if "bytes" in it and (not _inteiro(b) or b < 0 or b > TAMANHO_MAX):
                    erros.append(f"{c}.bytes: esperado inteiro entre 0 e {TAMANHO_MAX}")
                if not _nome_ruim(nome) and isinstance(sha, str) and _SHA.match(sha) and _inteiro(b) and 0 <= b <= TAMANHO_MAX \
                        and nome not in itens:
                    itens[nome] = {"sha256": sha.lower(), "bytes": b}
            if not erros and obj["count"] != len(arquivos):
                erros.append("count: diverge do tamanho da lista files")
    if erros:
        return None, erros
    return Manifesto(versao, gerado, obj["count"], itens), []
