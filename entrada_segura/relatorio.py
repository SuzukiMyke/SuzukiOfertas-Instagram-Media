"""Relatório (três registros separados), serialização determinística e diretório de evidência por execução (§4.11).

O relatório existe SEMPRE em memória, inclusive na recusa. A persistência usa um diretório novo por execução (``os.mkdir`` exclusivo), nunca
sobrescreve nada e confere o hash depois de gravar; qualquer falha deixa ``consumo_permitido`` em ``False``. Sem segredos, sem caminhos
absolutos e sem URLs completas (só hosts).
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import canonico
from .erros import ErroEntrada, FalhaPersistencia
from .politica import VERSAO_REGRAS, formatar_utc

NOME_RELATORIO = "relatorio_entrada.json"
_SUFIXO = re.compile(r"^[0-9a-f]{8}$")


@dataclass(frozen=True)
class Decisao:
    resultado: str                 # aceita | recusada
    codigos: tuple

    @property
    def aceita(self) -> bool:
        return self.resultado == "aceita"


@dataclass(frozen=True)
class Comprovante:
    caminho_relativo: str          # <diretório de evidência>/relatorio_entrada.json (relativo à base)
    sha256: str
    bytes: int


@dataclass
class Relatorio:
    dados: dict
    bytes_verificados: dict = field(default_factory=dict, repr=False)      # NÃO é serializado; só preenchido quando a decisão é ``aceita``

    @property
    def decisao(self) -> Decisao:
        d = self.dados["decisao"]
        return Decisao(d["resultado"], tuple(d["codigos"]))

    @property
    def classificacao(self) -> dict:
        return self.dados["classificacao"]

    @property
    def autorizacao(self) -> dict:
        return self.dados["autorizacao"]


def montar(*, avaliado_em, nivel: str, lote: dict | None, classificacao: dict | None, autorizacao: dict, decisao: Decisao, flags: dict,
           bytes_verificados: dict | None = None) -> Relatorio:
    lote = lote or {}
    dados = {
        "schemaVersion": "1", "versaoRegras": VERSAO_REGRAS, "avaliadoEm": formatar_utc(avaliado_em),
        "plataforma": {"sistema": sys.platform, "nivelDeGarantia": nivel},
        "lote": {"quantidadeArquivos": lote.get("quantidade"), "totalBytes": lote.get("total_bytes"), "manifestoSha256": lote.get("manifesto_sha256"),
                 "hashes": list(lote.get("hashes", ()))},
        "classificacao": classificacao or {"classe": None, "motivos": [], "hostsAvaliados": [], "totalHosts": 0, "conjunto": None},
        "autorizacao": autorizacao,
        "decisao": {"resultado": decisao.resultado, "codigos": list(decisao.codigos)},
        "flags": {"dadosReaisHabilitado": bool(flags["dados"]), "produtosReaisHabilitado": bool(flags["produtos"])},
    }
    return Relatorio(dados, dict(bytes_verificados or {}) if decisao.aceita else {})


def serializar(relatorio: Relatorio) -> bytes:
    """Bytes canônicos e DETERMINÍSTICOS do relatório (mesmas entradas e relógio ⇒ mesmos bytes; o nome do diretório de evidência não entra)."""
    return canonico.serializar(relatorio.dados)


def criar_diretorio_evidencia(base, *, relogio, sufixo: str | None = None) -> Path:
    """Cria ``execucao-<AAAAMMDDTHHMMSSZ>-<8 hex>`` dentro de ``base`` (que precisa existir, ser diretório e NÃO ser link simbólico).
    ``os.mkdir`` exclusivo: falha se já existir. Nunca reutiliza nem sobrescreve. (``sufixo`` fixo só para testes.)"""
    try:
        base = Path(base)
        lst = os.lstat(base)
    except (OSError, TypeError, ValueError):
        raise FalhaPersistencia("base_inexistente", "a base de evidências não existe") from None
    if stat.S_ISLNK(lst.st_mode) or not stat.S_ISDIR(lst.st_mode):
        raise FalhaPersistencia("base_invalida", "a base de evidências não é um diretório (ou é link simbólico)")
    sufixo = sufixo if sufixo is not None else secrets.token_hex(4)
    if not _SUFIXO.match(sufixo):
        raise FalhaPersistencia("sufixo_invalido", "sufixo fora de 8 hex")
    carimbo = formatar_utc(relogio()).replace("-", "").replace(":", "")
    destino = base / f"execucao-{carimbo}-{sufixo}"
    try:
        os.mkdir(destino, 0o700)
    except FileExistsError:
        raise FalhaPersistencia("diretorio_ja_existe", "o diretório de evidência já existe (nunca é reutilizado)") from None
    except OSError as e:
        raise FalhaPersistencia("erro_ao_criar_diretorio", e.__class__.__name__) from None
    return destino


def persistir(relatorio: Relatorio, diretorio) -> Comprovante:
    """Grava ``relatorio_entrada.json`` com ``O_CREAT|O_EXCL|O_NOFOLLOW``, ``fsync`` (melhor esforço no diretório), relê e confere o SHA-256."""
    dados = serializar(relatorio)
    esperado = hashlib.sha256(dados).hexdigest()
    diretorio = Path(diretorio)
    fd_dir = fd = fd2 = None
    try:
        lst = os.lstat(diretorio)
        if stat.S_ISLNK(lst.st_mode) or not stat.S_ISDIR(lst.st_mode):
            raise FalhaPersistencia("diretorio_invalido", "o diretório de evidência não é um diretório (ou é link simbólico)")
        fd_dir = os.open(diretorio, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        fd = os.open(NOME_RELATORIO, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd_dir)
        restante = memoryview(dados)
        while restante:
            n = os.write(fd, restante)
            if n <= 0:
                raise FalhaPersistencia("escrita_incompleta", "escrita sem progresso")
            restante = restante[n:]
        os.fsync(fd)
        os.close(fd)
        fd = None
        try:
            os.fsync(fd_dir)
        except OSError:
            pass                                                           # melhor esforço
        fd2 = os.open(NOME_RELATORIO, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd_dir)
        lido = b""
        while len(lido) <= len(dados):                                     # teto: um byte além do esperado já basta para reprovar
            bloco = os.read(fd2, 65536)
            if not bloco:
                break
            lido += bloco
        if hashlib.sha256(lido).hexdigest() != esperado or len(lido) != len(dados):
            raise FalhaPersistencia("hash_divergente", "o arquivo gravado não confere com o relatório")
    except FalhaPersistencia:
        raise
    except FileExistsError:
        raise FalhaPersistencia("relatorio_ja_existe", "nunca sobrescreve um relatório existente") from None
    except (OSError, AttributeError) as e:
        raise FalhaPersistencia("erro_ao_gravar", e.__class__.__name__) from None
    finally:
        for f in (fd, fd2, fd_dir):
            if f is not None:
                try:
                    os.close(f)
                except OSError:
                    pass
    return Comprovante(f"{diretorio.name}/{NOME_RELATORIO}", esperado, len(dados))
