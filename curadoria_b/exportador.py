"""Exportador da curadoria B: ficha humana -> ``B/produto_CURADORIA_<id>_<AAAAMMDDTHHMMSSZ>.json`` + ``manifest.json`` estrito.

O lote é montado numa pasta de preparo (``.staging_*``) criada por esta execução, validado com o receptor 1.1
(``leitor_v11.ler_lote`` e ``pipeline_v11.processar_v11``) e só então publicado com um único ``rename`` para ``B/``.
Se qualquer passo falhar, nada fica em ``B/`` e só a pasta de preparo (criada aqui) é removida. Uma ``B/`` já existente nunca é
sobrescrita. Sem rede, sem relógio implícito além de ``--agora`` (padrão: UTC do sistema, só na CLI), sem publicação.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from produtos.leitor import TAMANHO_MAX, decodificar_json
from produtos.leitor_v11 import ler_lote
from produtos.manifesto_v11 import MAX_ARQUIVOS
from produtos.pipeline_v11 import processar_v11
from produtos.tempo import formatar

from .ficha import ErroFicha, ler_ficha, para_exportacao, validar_exportacao


class ErroExportacao(Exception):
    """Falha de exportação (arquivo ilegível, destino ocupado ou lote que o receptor não aceitou)."""


def _bytes_json(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def construir_lote(ficha: dict, export_id: str, agora: datetime) -> tuple[str, bytes, bytes]:
    """``(nome, bytes do produto, bytes do manifesto)``; determinístico para a mesma entrada."""
    produto = para_exportacao(ficha, export_id, agora)
    erros = validar_exportacao(produto, agora)
    if erros:
        raise ErroFicha(["receptor 1.1 recusou a ficha convertida: " + e for e in erros])
    dados = _bytes_json(produto)
    if len(dados) > TAMANHO_MAX:
        raise ErroFicha([f"produto maior que {TAMANHO_MAX} bytes"])
    nome = f"produto_CURADORIA_{ficha['id']}_{agora.strftime('%Y%m%dT%H%M%SZ')}.json"
    manifesto = {"manifestVersion": "1.0", "generatedAt": formatar(agora), "count": 1,
                 "files": [{"name": nome, "sha256": hashlib.sha256(dados).hexdigest(), "bytes": len(dados)}]}
    if manifesto["count"] > MAX_ARQUIVOS:
        raise ErroFicha(["lote acima do limite de arquivos"])
    return nome, dados, _bytes_json(manifesto)


def exportar(ficha_arquivo, saida, agora: datetime, *, export_id: str | None = None) -> dict:
    """Gera ``saida/B/``. Levanta ``ErroFicha`` (ficha inválida) ou ``ErroExportacao`` (lote não disponibilizado)."""
    ficha_arquivo, saida = Path(ficha_arquivo), Path(saida)
    try:
        if ficha_arquivo.stat().st_size > TAMANHO_MAX:
            raise ErroFicha([f"ficha maior que {TAMANHO_MAX} bytes"])
        obj = decodificar_json(ficha_arquivo.read_bytes())
    except OSError as e:
        raise ErroExportacao(f"ficha ilegível: {e.__class__.__name__}") from None
    except ValueError as e:
        raise ErroFicha([f"ficha: {e}"]) from None
    ficha = ler_ficha(obj, agora)
    export_id = export_id or str(uuid.uuid4())
    try:
        uuid.UUID(export_id)
    except ValueError:
        raise ErroExportacao("export_id deve ser um UUID") from None
    nome, dados, manifesto = construir_lote(ficha, export_id, agora)

    destino = saida / "B"
    if destino.exists() or destino.is_symlink():
        raise ErroExportacao("a pasta B/ de destino já existe: nada foi sobrescrito")
    saida.mkdir(parents=True, exist_ok=True)
    preparo = saida / f".staging_{export_id[:8]}"
    preparo.mkdir()                                     # falha se já existir: nunca limpa o que não criou
    saida_teste = Path(tempfile.mkdtemp(prefix="curadoria_b_val_"))
    try:
        lote = preparo / "B"
        lote.mkdir()
        (lote / nome).write_bytes(dados)
        (lote / "manifest.json").write_bytes(manifesto)          # manifesto por último
        _validar_com_receptor(preparo, lote, saida_teste, agora, nome)
        lote.rename(destino)                                       # publicação atômica do lote íntegro
    except BaseException:
        shutil.rmtree(preparo, ignore_errors=True)
        raise
    else:
        preparo.rmdir()
    finally:
        shutil.rmtree(saida_teste, ignore_errors=True)
    return {"pasta": str(destino), "arquivo": nome, "sha256": hashlib.sha256(dados).hexdigest(), "bytes": len(dados),
            "exportId": export_id, "manifest": "manifest.json", "estado": "candidato_nao_verificado", "validacao": "ok"}


def _validar_com_receptor(raiz_preparo: Path, lote: Path, saida_teste: Path, agora: datetime, nome: str) -> None:
    l = ler_lote(lote, agora, "B")
    if l.status != "ok" or len(l.leitura.lidos) != 1 or l.leitura.rejeitados or l.leitura.lidos[0].arquivo != nome:
        raise ErroExportacao("o receptor 1.1 não aceitou o lote gerado (" + "; ".join(l.motivos or ["arquivo rejeitado"]) + ")")
    resumo = processar_v11(raiz_preparo, saida_teste, agora)
    if resumo["fichas"] != 1 or resumo["fichasPorEstado"] != {"candidato_nao_verificado": 1}:
        raise ErroExportacao("o receptor 1.1 não classificou a curadoria como candidato_nao_verificado")
