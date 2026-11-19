"""Classificação do lote (§4.7): classe + motivos. NÃO consulta autorização, assinatura, flags nem relógio.

Entrada: os arquivos JÁ LIDOS (bytes) e a configuração (só para os conjuntos de fixtures). Metadados autodeclarados (``system``, ``provider``,
``exportId``, ``source``, ``photo.usePermission``, autor, nomes de arquivo) nunca são prova: só hosts e procedência exata contam.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from . import hosts as hs
from .canonico import MAX_PROFUNDIDADE

FICTICIO, REAL, DESCONHECIDO = "ficticio_reconhecido", "potencialmente_real", "desconhecido"
ORDEM_MOTIVOS = ("host_reservado", "host_nao_reservado", "host_invalido", "esquema_nao_https", "sem_urls_avaliaveis", "procedencia_registrada",
                 "procedencia_ausente", "conjunto_nao_reconhecido", "json_invalido", "conteudo_nao_textual")
MAX_HOSTS_NO_RELATORIO = 50
BINARIOS_ESPERADOS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


@dataclass(frozen=True)
class Classificacao:
    classe: str
    motivos: tuple
    hosts: tuple                 # hosts avaliados (únicos, ordenados, ≤ 50); só hosts, nunca URL completa
    total_hosts: int
    conjunto: str | None


def _percorrer(obj, campo, saida, prof=0):
    if prof > MAX_PROFUNDIDADE + 4:
        return False
    if isinstance(obj, str):
        saida.append((obj, campo))
    elif isinstance(obj, list):
        for x in obj:
            _percorrer(x, campo, saida, prof + 1)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _percorrer(v, k if isinstance(k, str) else None, saida, prof + 1)
    return True


def _candidatos_do_arquivo(caminho: str, dados: bytes, motivos: set) -> list[str]:
    baixo = caminho.lower()
    if baixo.endswith(BINARIOS_ESPERADOS):
        return []
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        motivos.add("conteudo_nao_textual")
        return []
    if "\x00" in texto:
        motivos.add("conteudo_nao_textual")
        return []
    if baixo.endswith(".json") or texto.lstrip().startswith(("{", "[")):
        try:
            obj = json.loads(texto)
        except (ValueError, RecursionError):
            if baixo.endswith(".json"):
                motivos.add("json_invalido")
            return hs.urls_em_texto(texto)
        valores: list = []
        _percorrer(obj, None, valores)
        return [v for v, campo in valores if hs.e_candidato_textual(v, campo)]
    return hs.urls_em_texto(texto)


def _procedencia(arquivos: dict, hashes: dict, config) -> tuple[str | None, bool]:
    """``(id do conjunto exato | None, algum arquivo pertence a algum conjunto)``: o conjunto precisa coincidir EXATAMENTE (caminhos e hashes)."""
    reconhecido = False
    exato = None
    conhecidos = {h for c in config.conjuntos for h in c.arquivos.values()}
    for c in config.conjuntos:
        if dict(c.arquivos) == hashes:
            exato = exato or c.id
    reconhecido = any(h in conhecidos for h in hashes.values())
    return exato, reconhecido


def classificar(arquivos: dict, config) -> Classificacao:
    hashes = {caminho: hashlib.sha256(dados).hexdigest() for caminho, dados in arquivos.items()}
    motivos: set = set()
    analises: list = []
    for caminho in sorted(arquivos):
        for cand in _candidatos_do_arquivo(caminho, arquivos[caminho], motivos):
            analises.append(hs.analisar_url(cand))
    validos = [a for a in analises if a.valido]
    reais = [a for a in validos if not a.reservado]
    invalidos = [a for a in analises if not a.valido]
    if any(a.http for a in analises):
        motivos.add("esquema_nao_https")
    if validos and not reais:
        motivos.add("host_reservado")
    if reais:
        motivos.add("host_nao_reservado")
    if invalidos:
        motivos.add("host_invalido")
    hosts_unicos = sorted({a.host for a in validos})
    exato, reconhecido = _procedencia(arquivos, hashes, config)
    if exato:
        motivos.add("procedencia_registrada")
    if reais:
        classe = REAL                                      # host real vence qualquer procedência (hash registrado com host real = erro de registro)
    elif not analises:
        motivos.add("sem_urls_avaliaveis")
        classe = DESCONHECIDO
    elif invalidos or motivos & {"json_invalido", "conteudo_nao_textual"}:
        classe = DESCONHECIDO                              # host inválido, JSON ilegível ou binário inesperado: nunca reconhecido
    elif exato:
        classe = FICTICIO
    else:
        motivos.add("procedencia_ausente")
        if reconhecido:
            motivos.add("conjunto_nao_reconhecido")
        classe = DESCONHECIDO
    return Classificacao(classe, tuple(m for m in ORDEM_MOTIVOS if m in motivos), tuple(hosts_unicos[:MAX_HOSTS_NO_RELATORIO]),
                         len(hosts_unicos), exato if classe == FICTICIO else None)
