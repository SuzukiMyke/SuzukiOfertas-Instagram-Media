"""Análise ESTRITA de URLs/hosts (§4.7). Sem rede, sem ``urllib``: o texto é analisado à mão, por rótulos.

Identificar um host NÃO autoriza nada. ``http`` tem o host extraído e avaliado normalmente e recebe o motivo ``esquema_nao_https``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TLDS_RESERVADOS = frozenset({"example", "invalid", "test"})
DOMINIOS_RESERVADOS = (("example", "com"), ("example", "net"), ("example", "org"))
ESQUEMAS_PERIGOSOS = ("file", "data", "javascript", "ftp", "mailto")
EXTENSOES_DE_ARQUIVO = frozenset({"json", "txt", "md", "jpg", "jpeg", "png", "gif", "webp", "csv", "tmp", "sig", "pdf", "xml", "html", "yaml", "yml", "log"})
CAMPOS_DE_URL = re.compile(r"^(url|link|href|sourceref|referencia|.*url)$", re.I)
_ESQUEMA = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://")
_PERIGOSO = re.compile(r"^(" + "|".join(ESQUEMAS_PERIGOSOS) + r"):", re.I)
_ROTULO = re.compile(r"^[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?$")
_PARECE_DOMINIO = re.compile(r"^[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.([A-Za-z]{2,})(?::\d+)?(?:[/?#]\S*)?$")
_URL_EM_TEXTO = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.\-]*://|\bwww\.)[^\s<>\"'`\)\]]+", re.I)


@dataclass(frozen=True)
class AnaliseUrl:
    host: str | None            # normalizado (minúsculas, sem ponto final) ou None
    valido: bool
    reservado: bool
    esquema: str | None
    http: bool
    motivo_invalido: str | None = None


def _invalido(esquema, motivo, http=False) -> AnaliseUrl:
    return AnaliseUrl(None, False, False, esquema, http, motivo)


def host_reservado(host: str) -> bool:
    """Comparação por RÓTULOS (nunca substring): TLD reservado ou ``example.com|net|org`` exatos/subdomínio legítimo."""
    rot = host.split(".")
    return rot[-1] in TLDS_RESERVADOS or tuple(rot[-2:]) in DOMINIOS_RESERVADOS


def analisar_url(texto: str) -> AnaliseUrl:
    s = texto.strip() if isinstance(texto, str) else ""
    if not s or s != texto or any(ord(c) < 32 or ord(c) == 127 or c.isspace() for c in s):
        return _invalido(None, "vazio_ou_controle")
    if _PERIGOSO.match(s):
        return _invalido(s.split(":", 1)[0].lower(), "esquema_perigoso")
    m = _ESQUEMA.match(s)
    esquema = m.group(1).lower() if m else None
    resto = s[m.end():] if m else s
    if esquema is not None and esquema not in ("http", "https"):
        return _invalido(esquema, "esquema_nao_permitido")
    autoridade = re.split(r"[/?#]", resto, maxsplit=1)[0]
    if "@" in autoridade:
        return _invalido(esquema, "userinfo", esquema == "http")
    if autoridade.startswith("[") or autoridade.count(":") > 1:
        return _invalido(esquema, "ip_literal", esquema == "http")
    host, _, porta = autoridade.partition(":")
    if porta and (not porta.isdigit() or int(porta) not in (80, 443)):
        return _invalido(esquema, "porta", esquema == "http")
    if not host:
        return _invalido(esquema, "host_ausente", esquema == "http")
    if not host.isascii():
        return _invalido(esquema, "nao_ascii", esquema == "http")
    host = host.lower()
    if host.endswith("."):
        host = host[:-1]
    rot = host.split(".")
    if host == "localhost" or any(r == "" for r in rot) or len(rot) < 2:
        return _invalido(esquema, "host_nao_reconhecivel", esquema == "http")
    if any(r.startswith("xn--") for r in rot):
        return _invalido(esquema, "punycode", esquema == "http")
    if all(r.isdigit() for r in rot):
        return _invalido(esquema, "ip_literal", esquema == "http")
    if not all(_ROTULO.match(r) for r in rot):
        return _invalido(esquema, "rotulo_invalido", esquema == "http")
    return AnaliseUrl(host, True, host_reservado(host), esquema, esquema == "http")


def e_candidato_textual(valor: str, campo: str | None = None) -> bool:
    """Valor string de JSON que deve ser avaliado como URL/host: contém ``://``, começa com ``www.``, tem forma ``domínio.tld`` (TLD que não
    seja extensão de arquivo), ou está em campo de nome ``url``/``*Url``/``sourceRef``/``referencia``/``link``/``href``."""
    if not isinstance(valor, str) or not valor:
        return False
    if campo is not None and CAMPOS_DE_URL.match(campo):
        return True
    baixo = valor.lower()
    if "://" in valor or baixo.startswith("www.") or _PERIGOSO.match(valor):
        return True
    m = _PARECE_DOMINIO.match(valor)
    return bool(m) and m.group(1).lower() not in EXTENSOES_DE_ARQUIVO


def urls_em_texto(texto: str) -> list[str]:
    """URLs (``esquema://…`` ou ``www.…``) em texto livre (.md/.txt). Pontuação final de frase é removida."""
    return [t.rstrip(".,;:!?") for t in _URL_EM_TEXTO.findall(texto)]
