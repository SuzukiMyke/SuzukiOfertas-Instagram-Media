"""JSON canônico estrito (§4.4): UTF-8, chaves ordenadas, sem espaços, ASCII escapado, sem float/NaN/chave duplicada/BOM.

``carregar_canonico(bytes)`` só aceita se ``serializar(parse(bytes)) == bytes``: qualquer diferença é ``NaoCanonico`` (recusa).
"""
from __future__ import annotations

import json

from .erros import NaoCanonico

MAX_PROFUNDIDADE = 16
MAX_BYTES_PADRAO = 2 * 1024 * 1024


def _validar(obj, prof: int = 0) -> None:
    if prof > MAX_PROFUNDIDADE:
        raise NaoCanonico("profundidade", f"profundidade acima de {MAX_PROFUNDIDADE}")
    if obj is None or isinstance(obj, (bool, str)):
        return
    if isinstance(obj, int):
        return
    if isinstance(obj, list):
        for x in obj:
            _validar(x, prof + 1)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise NaoCanonico("chave_nao_textual", "chave que não é texto")
            _validar(v, prof + 1)
        return
    raise NaoCanonico("tipo_nao_permitido", f"tipo {type(obj).__name__} não é permitido (float, NaN e afins são recusados)")


def serializar(obj) -> bytes:
    """Bytes canônicos do objeto (levanta ``NaoCanonico`` para tipos ou profundidade não permitidos)."""
    _validar(obj)
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, RecursionError) as e:
        raise NaoCanonico("serializacao", type(e).__name__) from None


def _profundidade_bruta(dados: bytes) -> int:
    """Maior aninhamento de ``{``/``[`` fora de strings (varredura linear; evita recursão do parser em entradas hostis)."""
    prof = maximo = 0
    em_string = escape = False
    for b in dados:
        if em_string:
            if escape:
                escape = False
            elif b == 0x5C:
                escape = True
            elif b == 0x22:
                em_string = False
        elif b == 0x22:
            em_string = True
        elif b in (0x7B, 0x5B):
            prof += 1
            maximo = max(maximo, prof)
        elif b in (0x7D, 0x5D):
            prof -= 1
    return maximo


def _pares(pares):
    d = {}
    for k, v in pares:
        if k in d:
            raise NaoCanonico("chave_duplicada", "chave duplicada no JSON")
        d[k] = v
    return d


def _recusar_constante(nome):
    raise NaoCanonico("constante_nao_permitida", f"constante {nome} não é permitida")


def _recusar_float(texto):
    raise NaoCanonico("float_nao_permitido", "números não inteiros não são permitidos")


def carregar_canonico(dados: bytes, *, max_bytes: int = MAX_BYTES_PADRAO):
    """Interpreta ``dados`` e exige que sejam EXATAMENTE a forma canônica. Levanta ``NaoCanonico`` em qualquer desvio."""
    if not isinstance(dados, (bytes, bytearray)):
        raise NaoCanonico("tipo_de_entrada", "esperado bytes")
    dados = bytes(dados)
    if len(dados) > max_bytes:
        raise NaoCanonico("tamanho", "documento acima do limite")
    if dados.startswith(b"\xef\xbb\xbf"):
        raise NaoCanonico("bom", "BOM não é permitido")
    if _profundidade_bruta(dados) > MAX_PROFUNDIDADE:
        raise NaoCanonico("profundidade", f"profundidade acima de {MAX_PROFUNDIDADE}")
    try:
        texto = dados.decode("utf-8")
        obj = json.loads(texto, object_pairs_hook=_pares, parse_float=_recusar_float, parse_constant=_recusar_constante)
    except NaoCanonico:
        raise
    except (ValueError, RecursionError, UnicodeDecodeError):
        raise NaoCanonico("json_invalido", "JSON inválido") from None
    if serializar(obj) != dados:
        raise NaoCanonico("forma_nao_canonica", "os bytes diferem da forma canônica")
    return obj
