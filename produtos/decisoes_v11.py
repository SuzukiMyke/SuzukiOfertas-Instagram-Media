"""Auditoria do arquivo de decisões humanas no modo 1.1 (P-08, impressão digital e decisões que não valem). Módulo novo, só leitura.

O formato de ``decisoes.json`` NÃO mudou (contrato §10 e DT-20): a decisão não carrega impressão digital material. A impressão é
sempre RECALCULADA pelo receptor a partir da versão revisada (a do ``exportId`` da decisão) e, por isso, tem procedência
verificável. Uma impressão **fornecida pelo próprio arquivo** nunca é aceita: não há como provar quem a calculou nem sobre qual
conteúdo, e aceitá-la deixaria uma aprovação valer para conteúdo que ninguém conferiu. Esta auditoria só torna isso EXPLÍCITO e
estruturado (por produto e no ``resumo.json``), sem alterar o carregador do modo 1.0 (``decisoes.carregar``), que continua
ignorando e avisando.
Nunca ecoa valores do arquivo: só o índice, o produto (se textual) e os NOMES dos campos desconhecidos.
"""
from __future__ import annotations

from pathlib import Path

from .decisoes import _validar
from .leitor import decodificar_json

COD_INVALIDA = "decisao_invalida"
COD_IMPRESSAO = "impressao_fornecida_sem_procedencia"
_NOMES_DE_IMPRESSAO = ("impress", "fingerprint", "digest", "hashmaterial", "hash_material")


def auditar_arquivo(caminho) -> dict:
    """``{"status": nao_informado|ausente|invalido|ok, "invalidas": [{indice, produto, codigos, campos, motivo}]}``."""
    if caminho is None:
        return {"status": "nao_informado", "invalidas": []}
    p = Path(caminho)
    if not p.is_file():
        return {"status": "ausente", "invalidas": []}
    try:
        obj = decodificar_json(p.read_bytes())
    except (OSError, ValueError):
        return {"status": "invalido", "invalidas": []}
    if not isinstance(obj, dict) or not isinstance(obj.get("decisoes"), list):
        return {"status": "invalido", "invalidas": []}
    invalidas = []
    for i, d in enumerate(obj["decisoes"], 1):
        erro = _validar(d)
        if not erro:
            continue
        desconhecidos = sorted(str(k)[:40] for k in d if k not in {"provider", "productId", "exportId", "decisao", "autor",
                                                                   "data", "motivo"}) if isinstance(d, dict) else []
        codigos = [COD_INVALIDA]
        if any(any(n in k.lower() for n in _NOMES_DE_IMPRESSAO) for k in desconhecidos):
            codigos.append(COD_IMPRESSAO)
        produto = None
        if isinstance(d, dict) and isinstance(d.get("provider"), str) and isinstance(d.get("productId"), str):
            produto = (d["provider"], d["productId"])
        invalidas.append({"indice": i, "produto": produto, "codigos": codigos, "campos": desconhecidos,
                          "motivo": ("impressão digital fornecida pelo arquivo não é aceita (sem validação de procedência); "
                                     "o receptor a recalcula da versão revisada: " if COD_IMPRESSAO in codigos else "") + erro})
    return {"status": "ok", "invalidas": invalidas}
