"""Leitor da pasta de troca (GOAL 5.3): somente leitura, sem rede.

- ignora arquivos ocultos, ``*.tmp``, sem extensão ``.json``, links simbólicos e subpastas;
- ``manifest.json`` opcional (contagem + SHA-256 por arquivo): hash divergente, arquivo não
  listado ou manifesto inválido -> quarentena (gravação possivelmente incompleta);
- JSON truncado/inválido, chaves duplicadas e constantes NaN/Infinity -> quarentena;
- nunca grava, move, renomeia ou apaga nada na pasta de troca. A quarentena é um *relatório*
  (``rejeitados.json`` na pasta de saída), não uma movimentação do arquivo original.
"""
from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .esquema import Resultado, validar_produto

MANIFESTO = "manifest.json"
TAMANHO_MAX = 256 * 1024


@dataclass
class Lido:
    """Arquivo válido já normalizado."""
    arquivo: str
    sha256: str
    dados: dict


@dataclass
class Rejeitado:
    arquivo: str
    sha256: str | None
    destino: str                      # "rejeitado" | "quarentena" | "ignorado"
    motivos: list[str]
    faltantes: list[str] = field(default_factory=list)

    @property
    def dados_insuficientes(self) -> bool:
        return bool(self.faltantes) and len(self.faltantes) == len(self.motivos)

    def como_dict(self) -> dict:
        d = {"arquivo": self.arquivo, "sha256": self.sha256, "destino": self.destino, "motivos": self.motivos}
        if self.dados_insuficientes:
            d["categoria"] = "dados_insuficientes"
            d["camposFaltantes"] = self.faltantes
        return d


@dataclass
class Leitura:
    lidos: list[Lido] = field(default_factory=list)
    rejeitados: list[Rejeitado] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)   # nomes ignorados em silêncio (tmp, ocultos...)
    avisos: list[str] = field(default_factory=list)
    manifesto_presente: bool = False


class _ChaveDuplicada(ValueError):
    pass


def _sem_duplicatas(pares):
    d = {}
    for k, v in pares:
        if k in d:
            raise _ChaveDuplicada(k)
        d[k] = v
    return d


def _constante_invalida(nome):
    raise ValueError(f"constante {nome} não permitida")


def decodificar_json(dados: bytes):
    """Decodifica JSON estrito. Levanta ValueError com mensagem sem eco do conteúdo."""
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError("arquivo não é UTF-8 válido") from e
    try:
        return json.loads(texto, object_pairs_hook=_sem_duplicatas, parse_constant=_constante_invalida)
    except _ChaveDuplicada as e:
        raise ValueError("JSON com chave duplicada") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido ou truncado (linha {e.lineno}, coluna {e.colno})") from e
    except RecursionError as e:
        raise ValueError("JSON aninhado demais") from e


def _ler_manifesto(caminho: Path) -> tuple[dict | None, str | None]:
    """Devolve ({nome: sha256}, None) ou (None, motivo)."""
    try:
        m = decodificar_json(caminho.read_bytes())
    except (OSError, ValueError) as e:
        return None, f"manifesto ilegível: {e}"
    if not isinstance(m, dict) or not isinstance(m.get("files"), list) or not isinstance(m.get("count"), int):
        return None, "manifesto inválido (esperado {count, files[]})"
    mapa = {}
    for item in m["files"]:
        if not (isinstance(item, dict) and isinstance(item.get("name"), str)
                and isinstance(item.get("sha256"), str) and len(item["sha256"]) == 64):
            return None, "manifesto inválido (item de files sem name/sha256)"
        mapa[item["name"]] = item["sha256"].lower()
    return {"mapa": mapa, "count": m["count"]}, None


def _candidato(p: Path) -> bool:
    n = p.name
    if n.startswith(".") or not n.endswith(".json") or n == MANIFESTO:
        return False
    return True


def ler_pasta(troca: Path | str, agora: datetime, *, tolerancia_futuro_min: int = 5) -> Leitura:
    """Lê e valida todos os JSON de ``troca``. Ordem determinística (nome do arquivo)."""
    troca = Path(troca)
    if not troca.is_dir():
        raise FileNotFoundError("pasta de troca inexistente")
    out = Leitura()
    arquivos: list[Path] = []
    for p in sorted(troca.iterdir(), key=lambda x: x.name):
        st = p.lstat()
        if not stat.S_ISREG(st.st_mode) or not _candidato(p):
            if p.name != MANIFESTO:
                out.ignorados.append(p.name)
            continue
        arquivos.append(p)

    manifesto = None
    motivo_manifesto = None
    mpath = troca / MANIFESTO
    if mpath.is_file() and not mpath.is_symlink():
        out.manifesto_presente = True
        manifesto, motivo_manifesto = _ler_manifesto(mpath)
        if manifesto is None:
            out.avisos.append(motivo_manifesto)
        else:
            nomes = {p.name for p in arquivos}
            for nome in sorted(set(manifesto["mapa"]) - nomes):
                out.avisos.append(f"arquivo listado no manifesto não encontrado: {nome[:80]}")
            if manifesto["count"] != len(manifesto["mapa"]):
                out.avisos.append("manifesto: contagem diverge da lista de arquivos")

    for p in arquivos:
        st = p.stat()
        if st.st_size > TAMANHO_MAX:
            out.rejeitados.append(Rejeitado(p.name, None, "quarentena",
                                            [f"arquivo maior que {TAMANHO_MAX} bytes"]))
            continue
        dados = p.read_bytes()
        sha = hashlib.sha256(dados).hexdigest()
        if out.manifesto_presente:
            if manifesto is None:
                out.rejeitados.append(Rejeitado(p.name, sha, "quarentena", [motivo_manifesto]))
                continue
            esperado = manifesto["mapa"].get(p.name)
            if esperado is None:
                out.rejeitados.append(Rejeitado(p.name, sha, "quarentena",
                                                ["arquivo não listado no manifesto (possível gravação em andamento)"]))
                continue
            if esperado != sha:
                out.rejeitados.append(Rejeitado(p.name, sha, "quarentena",
                                                ["SHA-256 diverge do manifesto (arquivo incompleto ou alterado)"]))
                continue
        try:
            obj = decodificar_json(dados)
        except ValueError as e:
            out.rejeitados.append(Rejeitado(p.name, sha, "quarentena", [str(e)]))
            continue
        res: Resultado = validar_produto(obj, agora, tolerancia_futuro_min=tolerancia_futuro_min)
        if res.ok:
            out.lidos.append(Lido(p.name, sha, res.dados))
        else:
            out.rejeitados.append(Rejeitado(p.name, sha, res.destino, res.erros, res.faltantes))
    return out
