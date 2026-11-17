"""Leitor de lotes do modo 1.1 (contrato v1.1 §2/S4, decisão da etapa 5.11). Módulo novo; o ``leitor`` do modo 1.0 não muda.

Cada pasta de exportação (``A/`` e ``B/``) é um **lote independente** e exige o **seu próprio** ``manifest.json``
(o leitor lê uma pasta por vez, sem recursão). Regras (somente leitura, sem rede):
- sem manifesto, manifesto ilegível/inválido, contagem divergente, arquivo listado ausente, arquivo não listado,
  hash divergente, arquivo grande demais ou manifesto simbólico -> o **lote inteiro** vai para a quarentena
  (nenhum arquivo do lote é usado): gravação possivelmente incompleta (S4);
- lote íntegro: cada arquivo é validado como no modo 1.0; ``A/`` só aceita fonte A e ``B/`` só aceita fonte B
  (arquivo na pasta errada -> quarentena do arquivo);
- nunca grava, move, renomeia ou apaga. A quarentena é um relatório.
"""
from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .esquema import FONTE_A, FONTES_B, validar_produto
from .leitor import (MANIFESTO, TAMANHO_MAX, Leitura, Lido, Rejeitado, _candidato, _ler_manifesto,
                     decodificar_json)

LETRAS = ("A", "B")


@dataclass
class Lote:
    letra: str
    pasta: str
    status: str = "ok"                 # ok | vazio | pasta_ausente | quarentena_de_lote
    motivos: list[str] = field(default_factory=list)
    manifesto_presente: bool = False
    arquivos: int = 0
    leitura: Leitura = field(default_factory=Leitura)

    def resumo(self) -> dict:
        return {"pasta": self.pasta, "status": self.status, "manifestoPresente": self.manifesto_presente,
                "arquivos": self.arquivos, "motivos": self.motivos, "lidos": len(self.leitura.lidos)}


def ler_lote(pasta: Path | str, agora: datetime, letra: str, *, tolerancia_futuro_min: int = 5) -> Lote:
    if letra not in LETRAS:
        raise ValueError("letra do lote deve ser A ou B")
    pasta = Path(pasta)
    lote = Lote(letra, letra)
    if not pasta.is_dir() or pasta.is_symlink():
        lote.status = "pasta_ausente"
        lote.motivos.append(f"pasta {letra}/ inexistente (nenhuma exportação {letra} lida)")
        return lote
    arquivos: list[Path] = []
    for p in sorted(pasta.iterdir(), key=lambda x: x.name):
        st = p.lstat()
        if not stat.S_ISREG(st.st_mode) or not _candidato(p):
            if p.name != MANIFESTO:
                lote.leitura.ignorados.append(p.name)
            continue
        arquivos.append(p)
    lote.arquivos = len(arquivos)
    mpath = pasta / MANIFESTO
    lote.manifesto_presente = mpath.is_file() and not mpath.is_symlink()

    def quarentena(motivos: list[str]):
        lote.status = "quarentena_de_lote"
        lote.motivos = motivos
        for p in arquivos:
            dados = p.read_bytes() if p.stat().st_size <= TAMANHO_MAX else None
            lote.leitura.rejeitados.append(Rejeitado(
                p.name, hashlib.sha256(dados).hexdigest() if dados is not None else None, "quarentena",
                ["lote em quarentena: " + "; ".join(motivos)]))
        if not arquivos:                                        # manifesto isolado (ou pasta só com ele)
            lote.leitura.rejeitados.append(Rejeitado(MANIFESTO, None, "quarentena", motivos))
        return lote

    if not arquivos and not mpath.exists() and not mpath.is_symlink():
        lote.status = "vazio"
        return lote
    if mpath.is_symlink() or not lote.manifesto_presente:
        return quarentena(["manifest.json ausente (obrigatório no modo 1.1 para cada pasta de exportação)"])
    manifesto, motivo = _ler_manifesto(mpath)
    if manifesto is None:
        return quarentena([motivo])
    lote.leitura.manifesto_presente = True
    mapa, nomes = manifesto["mapa"], {p.name for p in arquivos}
    problemas: list[str] = []
    if manifesto["count"] != len(mapa):
        problemas.append("manifesto: contagem diverge da lista de arquivos")
    if manifesto["count"] != len(arquivos):
        problemas.append("manifesto: contagem diverge dos arquivos presentes na pasta")
    for n in sorted(set(mapa) - nomes):
        problemas.append(f"arquivo listado no manifesto não encontrado: {n[:80]}")
    for n in sorted(nomes - set(mapa)):
        problemas.append(f"arquivo não listado no manifesto (gravação em andamento ou manifesto desatualizado): {n[:80]}")
    conteudos: dict[str, bytes] = {}
    for p in arquivos:
        if p.stat().st_size > TAMANHO_MAX:
            problemas.append(f"arquivo maior que {TAMANHO_MAX} bytes: {p.name[:80]}")
            continue
        conteudos[p.name] = p.read_bytes()
        if p.name in mapa and hashlib.sha256(conteudos[p.name]).hexdigest() != mapa[p.name]:
            problemas.append(f"SHA-256 diverge do manifesto: {p.name[:80]}")
    if problemas:
        return quarentena(problemas)

    for p in arquivos:
        dados = conteudos[p.name]
        sha = hashlib.sha256(dados).hexdigest()
        try:
            obj = decodificar_json(dados)
        except ValueError as e:
            lote.leitura.rejeitados.append(Rejeitado(p.name, sha, "quarentena", [str(e)]))
            continue
        res = validar_produto(obj, agora, tolerancia_futuro_min=tolerancia_futuro_min)
        if not res.ok:
            lote.leitura.rejeitados.append(Rejeitado(p.name, sha, res.destino, res.erros, res.faltantes))
            continue
        kind = res.dados["source"]["kind"]
        if (letra == "A") != (kind == FONTE_A) or (letra == "B" and kind not in FONTES_B):
            lote.leitura.rejeitados.append(Rejeitado(
                p.name, sha, "quarentena", [f"fonte '{kind}' não pertence à pasta {letra}/ (A só aceita agente_publicada)"]))
            continue
        lote.leitura.lidos.append(Lido(p.name, sha, res.dados))
    return lote
