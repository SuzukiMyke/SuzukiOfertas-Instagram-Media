"""Leitura segura ÚNICA do lote (§4.8), com níveis de garantia por plataforma.

Garantia exigida: leitura única, sem seguir links em NENHUM componente do caminho (nem na raiz), sem hardlinks, só arquivos regulares, lista
fechada e detecção de troca durante a leitura. Se a plataforma não puder aplicar a garantia, o resultado é RECUSA
(``garantia_plataforma_insuficiente``): nada é prometido onde a garantia não foi demonstrada. No Windows ela NÃO é demonstrada
(a biblioteca padrão não oferece abertura sem seguir links por componente, ``dir_fd`` nem ``O_NOFOLLOW``): o portão recusa lá.

Limites honestos: não é um *snapshot* atômico; os ancestrais da raiz informada pelo operador são confiáveis (a raiz, em si, não pode ser um
link simbólico e, uma vez aberta, fica congelada pelo descritor); o consumidor recebe os BYTES já lidos e verificados, nunca um caminho.
"""
from __future__ import annotations

import errno
import hashlib
import os
import stat
import sys
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from .erros import ErroIntegridade

PROFUNDIDADE_MAXIMA = 8
COMPRIMENTO_MAXIMO = 240
ATRIBUTO_REPARSE = 0x400          # FILE_ATTRIBUTE_REPARSE_POINT (Windows): usado só nas simulações de teste


class NivelGarantia(str, Enum):
    FORTE = "FORTE"
    INSUFICIENTE = "INSUFICIENTE"


def nivel_de_garantia(_os=os, _sys=sys) -> NivelGarantia:
    """``FORTE`` somente em POSIX com ``O_NOFOLLOW``, ``O_DIRECTORY``, ``dir_fd``, ``scandir(fd)`` e ``stat`` sem seguir links; senão
    ``INSUFICIENTE`` (inclusive Windows). Os parâmetros permitem SIMULAR outras plataformas nos testes."""
    try:
        if getattr(_os, "name", None) != "posix" or str(getattr(_sys, "platform", "")).startswith(("win", "cygwin")):
            return NivelGarantia.INSUFICIENTE
        for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC", "O_NONBLOCK", "O_NOCTTY", "O_RDONLY"):
            if not hasattr(_os, flag):
                return NivelGarantia.INSUFICIENTE
        if _os.open not in _os.supports_dir_fd or _os.stat not in _os.supports_dir_fd or _os.stat not in _os.supports_follow_symlinks:
            return NivelGarantia.INSUFICIENTE
        if _os.scandir not in _os.supports_fd or not hasattr(_os, "fstat"):
            return NivelGarantia.INSUFICIENTE
        return NivelGarantia.FORTE
    except Exception:
        return NivelGarantia.INSUFICIENTE


def e_ponto_de_reparse(st) -> bool:
    """Detector de ponto de reparse do Windows (junções/links) por atributos; só exercitado por simulação (o Windows é recusado antes)."""
    return bool(getattr(st, "st_file_attributes", 0) & ATRIBUTO_REPARSE)


@dataclass(frozen=True)
class LoteLido:
    raiz_resolvida: str
    arquivos: dict                     # caminho relativo → bytes (únicos bytes que o consumidor recebe)
    hashes: tuple                      # ({"caminhoRelativo","sha256","bytes"}, …) ordenado por caminho
    total_bytes: int


_CODIGOS_ERRNO = {errno.ELOOP: "link_simbolico", errno.ENOENT: "arquivo_ausente", errno.ENOTDIR: "componente_nao_diretorio", errno.EACCES: "acesso_negado",
                  errno.EPERM: "acesso_negado", errno.EMFILE: "limite_de_descritores", errno.ENFILE: "limite_de_descritores",
                  errno.ENXIO: "arquivo_especial", errno.EISDIR: "e_diretorio"}


def _erro_so(e: OSError) -> ErroIntegridade:
    return ErroIntegridade(_CODIGOS_ERRNO.get(e.errno, "erro_de_so"), os.strerror(e.errno) if e.errno else type(e).__name__)


def validar_caminho_relativo(p) -> str:
    """Caminho solicitado: relativo, ``/``, sem segmento vazio/``.``/``..``, sem ``\\``/NUL/controle/``:``, ≤ 240, ≤ 8 níveis, NFC."""
    if not isinstance(p, str) or not p:
        raise ErroIntegridade("caminho_invalido", "caminho vazio ou não textual")
    if p.startswith("/") or "\\" in p or ":" in p or any(ord(c) < 32 or ord(c) == 127 for c in p):
        raise ErroIntegridade("caminho_invalido", "caminho absoluto ou com caractere proibido")
    if len(p) > COMPRIMENTO_MAXIMO:
        raise ErroIntegridade("caminho_invalido", "caminho longo demais")
    seg = p.split("/")
    if any(s in ("", ".", "..") for s in seg):
        raise ErroIntegridade("caminho_invalido", "segmento vazio, '.' ou '..'")
    if len(seg) > PROFUNDIDADE_MAXIMA:
        raise ErroIntegridade("caminho_invalido", "profundidade acima do limite")
    if unicodedata.normalize("NFC", p) != p:
        raise ErroIntegridade("caminho_invalido", "caminho não está em NFC")
    return p


def _validar_lista(arquivos, config) -> list[str]:
    if not isinstance(arquivos, (list, tuple)) or not arquivos:
        raise ErroIntegridade("lista_de_arquivos_invalida", "a lista fechada de arquivos é obrigatória e não pode ser vazia")
    if len(arquivos) > config.max_arquivos:
        raise ErroIntegridade("excesso_de_arquivos", f"mais de {config.max_arquivos} arquivos")
    vistos: dict[str, str] = {}
    for p in arquivos:
        validar_caminho_relativo(p)
        chave = unicodedata.normalize("NFC", p).casefold()
        if chave in vistos:
            raise ErroIntegridade("caminho_duplicado", "duplicata (inclusive por caixa ou normalização)")
        vistos[chave] = p
    return list(arquivos)


_FLAGS_DIR = lambda: os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FLAGS_ARQ = lambda: os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC


class _Fds:
    def __init__(self):
        self.abertos: list[int] = []

    def abrir(self, nome, flags, dir_fd=None) -> int:
        fd = os.open(nome, flags, dir_fd=dir_fd)
        self.abertos.append(fd)
        return fd

    def fechar(self, fd):
        if fd in self.abertos:
            self.abertos.remove(fd)
            os.close(fd)

    def fechar_tudo(self):
        for fd in reversed(self.abertos):
            try:
                os.close(fd)
            except OSError:
                pass
        self.abertos.clear()


def _abrir_pai(fds: _Fds, raiz_fd: int, partes: list[str]) -> int:
    """Abre os diretórios intermediários, UM componente por vez, com ``O_NOFOLLOW`` e ``dir_fd`` (link em qualquer componente ⇒ ELOOP)."""
    atual = raiz_fd
    for nome in partes:
        novo = fds.abrir(nome, _FLAGS_DIR(), dir_fd=atual)
        if atual != raiz_fd:
            fds.fechar(atual)
        atual = novo
    return atual


def _assinatura_arquivo(st) -> tuple:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


def _listar(fds: _Fds, dir_fd: int, prefixo: str, dev_raiz: int, saida: dict, nivel: int, config) -> None:
    """Lista recursivamente SEM seguir links; tudo que não for arquivo regular ou diretório recusa o lote."""
    if nivel > PROFUNDIDADE_MAXIMA:
        raise ErroIntegridade("profundidade_excedida", "diretórios aninhados demais")
    with os.scandir(dir_fd) as it:
        entradas = sorted(it, key=lambda e: e.name)
        for e in entradas:
            st = e.stat(follow_symlinks=False)
            rel = f"{prefixo}{e.name}"
            if stat.S_ISLNK(st.st_mode):
                raise ErroIntegridade("link_simbolico", "link simbólico no lote")
            if stat.S_ISDIR(st.st_mode):
                if st.st_dev != dev_raiz:
                    raise ErroIntegridade("ponto_de_montagem", "o lote atravessa um ponto de montagem")
                sub = fds.abrir(e.name, _FLAGS_DIR(), dir_fd=dir_fd)
                try:
                    _listar(fds, sub, rel + "/", dev_raiz, saida, nivel + 1, config)
                finally:
                    fds.fechar(sub)
            elif stat.S_ISREG(st.st_mode):
                saida[rel] = _assinatura_arquivo(st)
                if len(saida) > config.max_arquivos:
                    raise ErroIntegridade("excesso_de_arquivos", f"mais de {config.max_arquivos} arquivos")
            else:
                raise ErroIntegridade("arquivo_especial", "FIFO, socket ou dispositivo no lote")


def _abrir_raiz(fds: _Fds, raiz, gancho=None) -> tuple[int, str, int]:
    bruto = os.fspath(raiz)
    if not isinstance(bruto, str) or not bruto or "\x00" in bruto:
        raise ErroIntegridade("raiz_invalida", "raiz vazia ou com NUL")
    try:
        lst = os.lstat(bruto)                                    # ANTES de qualquer realpath: a raiz recebida não pode ser link simbólico
    except OSError as e:
        raise _erro_so(e) from None
    if stat.S_ISLNK(lst.st_mode):
        raise ErroIntegridade("raiz_simbolica", "a raiz informada é um link simbólico")
    if not stat.S_ISDIR(lst.st_mode):
        raise ErroIntegridade("raiz_nao_diretorio", "a raiz informada não é um diretório")
    real = os.path.realpath(bruto)                               # uma única vez (ancestrais são confiáveis)
    fd = fds.abrir(real, _FLAGS_DIR())
    st = os.fstat(fd)
    if gancho:
        gancho("apos_abrir_raiz", None)
    depois = os.lstat(bruto)                                     # a raiz não pode ter sido trocada por um link entre a checagem e a abertura
    if stat.S_ISLNK(depois.st_mode) or (depois.st_dev, depois.st_ino) != (st.st_dev, st.st_ino) or (lst.st_dev, lst.st_ino) != (st.st_dev, st.st_ino):
        raise ErroIntegridade("raiz_alterada", "a raiz mudou durante a abertura")
    return fd, real, st.st_dev


def ler_lote(raiz, arquivos, config, *, _gancho=None) -> LoteLido:
    """Lê EXATAMENTE ``arquivos`` (lista fechada) sob ``raiz``, uma única vez, e devolve os bytes. Levanta ``ErroIntegridade`` em qualquer desvio.

    ``_gancho(evento, caminho)`` existe só para os testes simularem troca de arquivo (eventos: ``apos_abrir_raiz``, ``apos_listagem``, ``apos_stat``, ``apos_leitura``)."""
    if nivel_de_garantia() is not NivelGarantia.FORTE:
        raise ErroIntegridade("garantia_plataforma_insuficiente", "a plataforma não oferece a garantia exigida")
    pedidos = _validar_lista(arquivos, config)
    fds = _Fds()
    try:
        raiz_fd, real, dev_raiz = _abrir_raiz(fds, raiz, _gancho)
        # lista fechada: o conjunto presente deve ser IGUAL ao solicitado
        presentes: dict = {}
        _listar(fds, raiz_fd, "", dev_raiz, presentes, 0, config)
        if _gancho:
            _gancho("apos_listagem", None)
        extras, ausentes = sorted(set(presentes) - set(pedidos)), sorted(set(pedidos) - set(presentes))
        if extras:
            raise ErroIntegridade("arquivo_extra", f"{len(extras)} arquivo(s) fora da lista fechada")
        if ausentes:
            raise ErroIntegridade("arquivo_ausente", f"{len(ausentes)} arquivo(s) da lista ausente(s)")
        lidos: dict = {}
        snapshots: dict = {}
        total = 0
        for rel in sorted(pedidos):
            partes = rel.split("/")
            pai = _abrir_pai(fds, raiz_fd, partes[:-1])
            nome = partes[-1]
            antes = os.stat(nome, dir_fd=pai, follow_symlinks=False)
            if stat.S_ISLNK(antes.st_mode):
                raise ErroIntegridade("link_simbolico", "link simbólico")
            if not stat.S_ISREG(antes.st_mode):
                raise ErroIntegridade("arquivo_especial", "o item não é um arquivo regular")
            if _gancho:
                _gancho("apos_stat", rel)
            fd = fds.abrir(nome, _FLAGS_ARQ(), dir_fd=pai)
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise ErroIntegridade("arquivo_especial", "o item aberto não é um arquivo regular")
            if st.st_nlink != 1:
                raise ErroIntegridade("hardlink", "arquivo com mais de um nome (hardlink)")
            if st.st_dev != dev_raiz:
                raise ErroIntegridade("ponto_de_montagem", "o arquivo está em outro dispositivo")
            if (st.st_dev, st.st_ino) != (antes.st_dev, antes.st_ino):
                raise ErroIntegridade("lote_alterado_durante_leitura", "o arquivo foi trocado entre o stat e a abertura")
            if st.st_size > config.max_bytes_arquivo:
                raise ErroIntegridade("arquivo_grande", f"arquivo acima de {config.max_bytes_arquivo} bytes")
            partes_lidas, restante = [], config.max_bytes_arquivo + 1
            while restante > 0:
                bloco = os.read(fd, min(65536, restante))
                if not bloco:
                    break
                partes_lidas.append(bloco)
                restante -= len(bloco)
            dados = b"".join(partes_lidas)
            if len(dados) > config.max_bytes_arquivo:
                raise ErroIntegridade("arquivo_grande", f"arquivo acima de {config.max_bytes_arquivo} bytes")
            if len(dados) != st.st_size:
                raise ErroIntegridade("lote_alterado_durante_leitura", "o tamanho lido difere do tamanho do arquivo")
            fds.fechar(fd)
            if pai != raiz_fd:
                fds.fechar(pai)
            total += len(dados)
            if total > config.max_bytes_total:
                raise ErroIntegridade("excesso_de_bytes", f"lote acima de {config.max_bytes_total} bytes")
            lidos[rel], snapshots[rel] = dados, _assinatura_arquivo(st)
            if _gancho:
                _gancho("apos_leitura", rel)
        # nova listagem e novo stat de cada arquivo: nada pode ter mudado durante a leitura
        de_novo: dict = {}
        _listar(fds, raiz_fd, "", dev_raiz, de_novo, 0, config)
        if set(de_novo) != set(snapshots) or any(de_novo[k] != snapshots[k] for k in snapshots):
            raise ErroIntegridade("lote_alterado_durante_leitura", "o conteúdo ou o conjunto de arquivos mudou durante a leitura")
        hashes = tuple({"caminhoRelativo": k, "sha256": hashlib.sha256(lidos[k]).hexdigest(), "bytes": len(lidos[k])} for k in sorted(lidos))
        return LoteLido(real, lidos, hashes, total)
    except ErroIntegridade:
        raise
    except OSError as e:
        raise _erro_so(e) from None
    finally:
        fds.fechar_tudo()
