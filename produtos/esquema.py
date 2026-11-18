"""Validador rigoroso do contrato JSON v1 (lista de permissão de campos).

Princípios (GOAL 5.2 / contrato §2, §7):
- qualquer campo fora da lista de permissão rejeita o arquivo inteiro (nada é copiado);
- mensagens de erro citam o *caminho* do campo, nunca o valor suspeito;
- fonte A (``agente_publicada``) e fonte B (``catalogo_candidato``/``api_candidato``) têm
  exigências distintas, e B nunca pode se declarar publicada ou elegível;
- ``schemaVersion`` com major desconhecida vai para quarentena.
"""
from __future__ import annotations

import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlsplit

from . import curadoria_regras_v11 as cur
from .tempo import parse_data

MAJOR_SUPORTADA = 1
SISTEMA_AGENTE = "SuzukiOfertas-AgenteAutomatico"
SISTEMA_CURADORIA = "SuzukiOfertas-Instagram-Curadoria"        # só contrato 1.1
PROVIDER_CURADORIA = "CURADORIA"                                # reservado exclusivamente à curadoria manual
BLOCK_REASON_CURADORIA = "curadoria_manual_sem_verificacao_comercial"   # 42 caracteres: o detector de "sequência opaca" a recusaria
FONTE_CURADORIA = "curadoria_manual"                            # só contrato 1.1; só em B/
CONTRATOS = ("1.0", "1.1")

FONTE_A = "agente_publicada"
FONTES_B = ("catalogo_candidato", "api_candidato")
FONTES = (FONTE_A,) + FONTES_B                    # contrato 1.0 (inalterado)
FONTES_V11 = FONTES + (FONTE_CURADORIA,)          # contrato 1.1

VERIFICACOES = ("ao_vivo", "catalogo_sem_verificacao", "desconhecida")
DISPONIBILIDADES = ("in_stock", "unknown", "out_of_stock")
ORIGENS_FOTO = ("api_oficial", "pagina_oficial", "catalogo_afiliado", "desconhecida")
PERMISSOES = ("confirmada", "pendente", "negada")
ESTADOS_PUBLICACAO = ("publicada", "nao_publicada", "incerta", "bloqueada")
ORIGENS_CATEGORIA = ("fonte", "derivada_revisada")

# Lista de permissão (chave -> subchaves). Qualquer outra chave rejeita o arquivo.
TOPO = ("schemaVersion", "exportId", "exportedAt", "source", "product", "price",
        "availability", "photo", "verifiedFacts", "publication", "references", "eligibility")
CAMPOS = {
    "source": ("kind", "system"),
    "product": ("id", "provider", "store", "advertiserId", "title", "category",
                "categoryOrigin", "officialUrl", "affiliateUrl"),
    "price": ("amountCents", "currency", "originalAmountCents", "verifiedAt", "validUntil",
              "verification"),
    "photo": ("url", "origin", "usePermission", "permissionRef", "checkedAt"),
    "fact": ("text", "sourceRef", "verifiedAt"),
    "publication": ("state", "publishedAt", "channel"),
    "reference": ("label", "url"),
    "eligibility": ("agentPublicationEligible", "blockReason"),
}
# Obrigatórios comuns a A e B (as exigências adicionais por fonte são tratadas no código).
OBRIGATORIOS = {
    "": ("schemaVersion", "exportId", "exportedAt", "source", "product", "price",
         "availability", "publication", "eligibility"),
    "source": ("kind", "system"),
    "product": ("id", "provider", "store", "title", "officialUrl"),
    "price": ("amountCents", "currency", "verification"),
    "publication": ("state",),
    "eligibility": ("agentPublicationEligible",),
}

_PROIBIDO = re.compile(
    r"(token|secret|senha|passw|credential|credencial|cofre|vault|api[_-]?key|apikey|telegram|"
    r"chat[_-]?id|operador|operator|cpf|e-?mail|phone|telefone|session)", re.I)
_SEMVER = re.compile(r"^(\d{1,4})\.(\d{1,5})\.(\d{1,5})$")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")
_PROVIDER = re.compile(r"^[A-Z][A-Z0-9_]{1,40}$")
_HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9\-]{0,61}[a-z0-9]$")
_CHAT_ID = re.compile(r"^-?\d{6,}$")

_SEGREDOS = [
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{30,}\b"),                    # token de bot do Telegram
    re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{20,}", re.I),
    re.compile(r"[A-Za-z0-9_\-+/=]{40,}"),                           # sequência opaca longa
]
_PARAM_PROIBIDO = re.compile(
    r"(token|secret|passw|pwd|session|apikey|api_key|signature|bearer|credential|^auth|^key$|^sig$|^sid$)", re.I)
_PARAM_RASTREIO = re.compile(r"^(utm_.*|fbclid|gclid|msclkid|ref|tag|aff|aff_id|clickid|tracking|trk)$", re.I)
_TAM_MAX_URL = 2048


@dataclass
class Resultado:
    """Resultado da validação de um arquivo."""
    destino: str | None = None          # None = válido | "rejeitado" | "quarentena" | "ignorado"
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)
    dados: dict | None = None           # cópia normalizada (somente campos da lista de permissão)

    @property
    def ok(self) -> bool:
        return self.destino is None

    @property
    def dados_insuficientes(self) -> bool:
        """Rejeitado só porque faltam campos obrigatórios (nada proibido ou inválido)."""
        return bool(self.faltantes) and len(self.faltantes) == len(self.erros)


class _Ctx:
    def __init__(self, agora: datetime, tolerancia_futuro: timedelta):
        self.agora = agora
        self.futuro_max = agora + tolerancia_futuro
        self.erros: list[str] = []
        self.avisos: list[str] = []
        self.faltantes: list[str] = []

    def erro(self, caminho: str, msg: str):
        self.erros.append(f"{caminho}: {msg}")

    def falta(self, caminho: str):
        self.faltantes.append(caminho)
        self.erros.append(f"{caminho}: campo obrigatório ausente")


def _nome_seguro(chave) -> str:
    s = str(chave)[:40]
    return "".join(c if (c.isascii() and (c.isalnum() or c in "_.-")) else "?" for c in s)


def _texto_ok(v: str) -> bool:
    return not any(unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co") for c in v)


def _tem_segredo(s: str) -> bool:
    return any(p.search(s) for p in _SEGREDOS)


def _txt(ctx: _Ctx, caminho: str, v, *, max_len: int, obrigatorio=False, vazio_ok=False) -> str | None:
    """Valida texto simples; devolve o valor ou None (erro registrado)."""
    if v is None:
        return None
    if not isinstance(v, str):
        ctx.erro(caminho, f"esperado texto, recebido {type(v).__name__}")
        return None
    if not v.strip() and not vazio_ok:
        ctx.erro(caminho, "não pode ser vazio")
        return None
    if len(v) > max_len:
        ctx.erro(caminho, f"excede {max_len} caracteres")
        return None
    if not _texto_ok(v):
        ctx.erro(caminho, "contém caracteres de controle ou invisíveis")
        return None
    if _tem_segredo(v):
        ctx.erro(caminho, "valor com aparência de segredo/credencial (conteúdo não exibido)")
        return None
    return v


def _enum(ctx: _Ctx, caminho: str, v, opcoes, *, nulo_ok=False):
    if v is None and nulo_ok:
        return None
    if v not in opcoes:
        ctx.erro(caminho, f"valor fora das opções permitidas {list(opcoes)}")
        return None
    return v


def _data(ctx: _Ctx, caminho: str, v, *, nulo_ok=True, futuro_ok=False) -> datetime | None:
    if v is None:
        if not nulo_ok:
            ctx.erro(caminho, "data obrigatória")
        return None
    dt = parse_data(v)
    if dt is None:
        ctx.erro(caminho, "data inválida (use AAAA-MM-DDTHH:MM:SSZ, UTC)")
        return None
    if not futuro_ok and dt > ctx.futuro_max:
        ctx.erro(caminho, "data no futuro")
        return None
    return dt


def _url(ctx: _Ctx, caminho: str, v, *, rastreio_proibido: bool, nulo_ok=False) -> str | None:
    """HTTPS, sem credenciais, porta, parâmetros de sessão/token (nem rastreio quando pedido)."""
    if v is None:
        if not nulo_ok:
            ctx.erro(caminho, "URL obrigatória")
        return None
    if not isinstance(v, str) or not v.strip():
        ctx.erro(caminho, "URL deve ser texto não vazio")
        return None
    if len(v) > _TAM_MAX_URL or not _texto_ok(v) or re.search(r"[\s\\]", v):
        ctx.erro(caminho, "URL com tamanho/caracteres inválidos")
        return None
    try:
        p = urlsplit(v)
        _ = p.port
    except ValueError:
        ctx.erro(caminho, "URL malformada ou com porta inválida")
        return None
    if p.scheme.lower() != "https":
        ctx.erro(caminho, "URL deve usar https://")
        return None
    if p.username is not None or p.password is not None or "@" in p.netloc:
        ctx.erro(caminho, "URL não pode conter credenciais")
        return None
    if p.port is not None or ":" in p.netloc:
        ctx.erro(caminho, "URL não pode conter porta")
        return None
    host = (p.hostname or "").lower()
    if not host.isascii() or not _HOST.match(host) or host == "localhost":
        ctx.erro(caminho, "host da URL inválido")
        return None
    try:
        ipaddress.ip_address(host)
        ctx.erro(caminho, "host da URL não pode ser endereço IP")
        return None
    except ValueError:
        pass
    for nome, _valor in parse_qsl(p.query, keep_blank_values=True):
        if _PARAM_PROIBIDO.search(nome):
            ctx.erro(caminho, "URL com parâmetro de sessão/credencial/token")
            return None
        if rastreio_proibido and _PARAM_RASTREIO.match(nome):
            ctx.erro(caminho, "URL com parâmetro de rastreio")
            return None
    return v


def _objeto(ctx: _Ctx, caminho: str, v, permitidos, *, nulo_ok=False):
    """Confere tipo objeto e lista de permissão; devolve o dict ou None."""
    if v is None and nulo_ok:
        return None
    if not isinstance(v, dict):
        ctx.erro(caminho or "(raiz)", "esperado objeto")
        return None
    for chave in v:
        if chave not in permitidos:
            nome = _nome_seguro(chave)
            tipo = "campo proibido" if _PROIBIDO.search(str(chave)) else "campo desconhecido"
            ctx.erro(f"{caminho + '.' if caminho else ''}{nome}", f"{tipo} (arquivo rejeitado)")
    return v


def _obrigatorios(ctx: _Ctx, caminho: str, obj: dict, chaves):
    for k in chaves:
        if k not in obj:
            ctx.falta(f"{caminho + '.' if caminho else ''}{k}")


def _inteiro_positivo(ctx: _Ctx, caminho: str, v, *, nulo_ok=False):
    if v is None and nulo_ok:
        return None
    if isinstance(v, bool) or not isinstance(v, int):
        ctx.erro(caminho, "esperado inteiro (centavos), não decimal/texto")
        return None
    if v <= 0:
        ctx.erro(caminho, "deve ser maior que zero")
        return None
    if v > 10**9:
        ctx.erro(caminho, "valor implausível")
        return None
    return v


def _host_curadoria(ctx: _Ctx, caminho: str, url) -> None:
    """Encurtadores e origens de procedência não verificável (pelo NOME do host; sem rede nem redirecionamentos)."""
    if not isinstance(url, str):
        return
    motivo = cur.host_nao_verificavel(urlsplit(url).hostname or "")
    if motivo:
        ctx.erro(caminho, f"URL de curadoria rejeitada: {motivo}")


def validar_produto(obj, agora: datetime, *, tolerancia_futuro_min: int = 5, contrato: str = "1.0") -> Resultado:
    """Valida um objeto já decodificado do JSON. Não levanta exceção para entradas inválidas.

    ``contrato="1.0"`` (padrão) é o comportamento de sempre: rejeita a fonte ``curadoria_manual``, o preço nulo e o sistema de
    origem da curadoria. ``contrato="1.1"`` (só ``leitor_v11``) aceita a curadoria manual, e só ela, com preço nulo."""
    if contrato not in CONTRATOS:
        raise ValueError(f"contrato desconhecido: use {' ou '.join(CONTRATOS)}")
    v11 = contrato == "1.1"
    ctx = _Ctx(agora, timedelta(minutes=tolerancia_futuro_min))
    res = Resultado()

    def fim(destino: str) -> Resultado:
        res.destino = destino
        res.erros, res.avisos, res.faltantes = ctx.erros, ctx.avisos, ctx.faltantes
        return res

    if not isinstance(obj, dict):
        ctx.erro("(raiz)", "o arquivo deve conter um objeto JSON")
        return fim("rejeitado")
    if "schemaVersion" not in obj or "exportId" not in obj:
        ctx.erro("(raiz)", "sem schemaVersion/exportId (ignorado conforme contrato §7)")
        return fim("ignorado")

    # --- versão: major desconhecida -> quarentena (antes de qualquer outra regra)
    sv = obj["schemaVersion"]
    m = _SEMVER.match(sv) if isinstance(sv, str) else None
    if not m:
        ctx.erro("schemaVersion", "esperado texto semver 'X.Y.Z'")
        return fim("rejeitado")
    if int(m.group(1)) != MAJOR_SUPORTADA:
        ctx.erro("schemaVersion", f"major {int(m.group(1))} desconhecida (suportada: {MAJOR_SUPORTADA}); quarentena")
        return fim("quarentena")

    _objeto(ctx, "", obj, TOPO)
    _obrigatorios(ctx, "", obj, OBRIGATORIOS[""])

    if not (isinstance(obj["exportId"], str) and _UUID.match(obj["exportId"])):
        ctx.erro("exportId", "esperado UUID")
    exportada = _data(ctx, "exportedAt", obj.get("exportedAt"), nulo_ok=False) if "exportedAt" in obj else None

    # --- source
    src = _objeto(ctx, "source", obj.get("source"), CAMPOS["source"]) if "source" in obj else None
    kind = None
    if src is not None:
        _obrigatorios(ctx, "source", src, OBRIGATORIOS["source"])
        kind = _enum(ctx, "source.kind", src.get("kind"), FONTES_V11 if v11 else FONTES) if "kind" in src else None
        sistema_esperado = SISTEMA_CURADORIA if kind == FONTE_CURADORIA else SISTEMA_AGENTE
        if "system" in src and src["system"] != sistema_esperado:
            ctx.erro("source.system", "sistema de origem não reconhecido pelo contrato"
                     if kind != FONTE_CURADORIA else "curadoria manual exige o sistema de origem da curadoria")
    eh_cur = kind == FONTE_CURADORIA                   # só existe no contrato 1.1 (``_enum`` recusa antes)
    eh_a = kind == FONTE_A
    eh_b = kind in FONTES_B or eh_cur                  # a curadoria manual é uma fonte do tipo B

    # --- product
    prod = _objeto(ctx, "product", obj.get("product"), CAMPOS["product"]) if "product" in obj else None
    dados_prod = {}
    if prod is not None:
        _obrigatorios(ctx, "product", prod, OBRIGATORIOS["product"])
        pid = prod.get("id")
        if "id" in prod and not (isinstance(pid, str) and _ID.match(pid)):
            ctx.erro("product.id", "ID público inválido (use letras, dígitos, '.', '_' e '-'; até 64)")
            pid = None
        prov = prod.get("provider")
        if "provider" in prod and not (isinstance(prov, str) and _PROVIDER.match(prov)):
            ctx.erro("product.provider", "provedor inválido (use MAIÚSCULAS, dígitos e '_')")
            prov = None
        if isinstance(prov, str):                      # reserva exclusiva (vale também no contrato 1.0)
            if eh_cur and prov != PROVIDER_CURADORIA:
                ctx.erro("product.provider", "curadoria manual exige o provedor reservado da curadoria")
            elif not eh_cur and prov == PROVIDER_CURADORIA:
                ctx.erro("product.provider", "provedor reservado exclusivamente à curadoria manual")
        dados_prod = {
            "id": pid, "provider": prov,
            "store": _txt(ctx, "product.store", prod.get("store"), max_len=120),
            "advertiserId": _txt(ctx, "product.advertiserId", prod.get("advertiserId"), max_len=64),
            "title": _txt(ctx, "product.title", prod.get("title"), max_len=240),
            "category": _txt(ctx, "product.category", prod.get("category"), max_len=200),
            "categoryOrigin": _enum(ctx, "product.categoryOrigin", prod.get("categoryOrigin"),
                                    ORIGENS_CATEGORIA, nulo_ok=True),
            "officialUrl": _url(ctx, "product.officialUrl", prod.get("officialUrl"), rastreio_proibido=True)
            if "officialUrl" in prod else None,
            "affiliateUrl": _url(ctx, "product.affiliateUrl", prod.get("affiliateUrl"),
                                 rastreio_proibido=False, nulo_ok=True),
        }
        if dados_prod["category"] is None and dados_prod["categoryOrigin"] is not None:
            ctx.erro("product.categoryOrigin", "informado sem categoria")
        if dados_prod["category"] is not None and dados_prod["categoryOrigin"] is None:
            ctx.avisos.append("product.category sem categoryOrigin: classificação precisa de revisão")
        if dados_prod["category"] is None:
            ctx.avisos.append("categoria ausente: classificação manual ou derivada necessária")
        if eh_a and prod.get("affiliateUrl") is None:
            ctx.falta("product.affiliateUrl")
        if eh_b and prod.get("affiliateUrl") is not None:
            ctx.erro("product.affiliateUrl", "fonte B não pode trazer link de afiliado")

    # --- price
    price = _objeto(ctx, "price", obj.get("price"), CAMPOS["price"]) if "price" in obj else None
    dados_price = {}
    verificada = valida = None
    if price is not None:
        _obrigatorios(ctx, "price", price, OBRIGATORIOS["price"])
        if "currency" in price and price["currency"] != "BRL":
            ctx.erro("price.currency", "moeda deve ser BRL")
        verificada = _data(ctx, "price.verifiedAt", price.get("verifiedAt"))
        valida = _data(ctx, "price.validUntil", price.get("validUntil"), futuro_ok=True)
        verif = _enum(ctx, "price.verification", price.get("verification"), VERIFICACOES) \
            if "verification" in price else None
        preco_nulo = eh_cur and "amountCents" in price and price["amountCents"] is None   # nulo SÓ para curadoria manual (1.1)
        if preco_nulo:
            for campo in ("originalAmountCents", "verifiedAt", "validUntil"):
                if price.get(campo) is not None:
                    ctx.erro(f"price.{campo}", "com preço nulo este campo deve ser nulo")
            if verif is not None and verif != "desconhecida":
                ctx.erro("price.verification", "com preço nulo a verificação deve ser 'desconhecida'")
        dados_price = {
            "amountCents": None if preco_nulo else (_inteiro_positivo(ctx, "price.amountCents", price.get("amountCents"))
                                                     if "amountCents" in price else None),
            "currency": price.get("currency"),
            "originalAmountCents": _inteiro_positivo(ctx, "price.originalAmountCents",
                                                    price.get("originalAmountCents"), nulo_ok=True),
            "verifiedAt": price.get("verifiedAt"), "validUntil": price.get("validUntil"),
            "verification": verif,
        }
        if verificada and valida and valida <= verificada:
            ctx.erro("price.validUntil", "deve ser posterior a price.verifiedAt")
        if eh_a:
            if price.get("verifiedAt") is None:
                ctx.falta("price.verifiedAt")
            if price.get("validUntil") is None:
                ctx.falta("price.validUntil")
            if verif is not None and verif != "ao_vivo":
                ctx.erro("price.verification", "fonte A exige verificação ao vivo")
        if eh_b and verif == "ao_vivo":
            ctx.erro("price.verification", "fonte B não pode declarar verificação ao vivo (isso é uma exportação do tipo A)")

    # --- availability
    disp = _enum(ctx, "availability", obj.get("availability"), DISPONIBILIDADES) if "availability" in obj else None
    if eh_cur and disp is not None and disp != "unknown":
        ctx.erro("availability", "curadoria manual exige availability = unknown")

    # --- photo
    dados_foto = {"url": None, "origin": "desconhecida", "usePermission": "pendente",
                  "permissionRef": None, "checkedAt": None}
    if "photo" in obj:
        foto = _objeto(ctx, "photo", obj["photo"], CAMPOS["photo"])
        if foto is not None:
            if "usePermission" not in foto:
                ctx.falta("photo.usePermission")
            perm = _enum(ctx, "photo.usePermission", foto.get("usePermission", "pendente"), PERMISSOES)
            url = _url(ctx, "photo.url", foto.get("url"), rastreio_proibido=True, nulo_ok=True)
            ref = foto.get("permissionRef")
            if isinstance(ref, str) and ref.lower().startswith("https://"):
                ref = _url(ctx, "photo.permissionRef", ref, rastreio_proibido=True, nulo_ok=True)
            else:
                ref = _txt(ctx, "photo.permissionRef", ref, max_len=300)
            chk = _data(ctx, "photo.checkedAt", foto.get("checkedAt"))
            origem = _enum(ctx, "photo.origin", foto.get("origin", "desconhecida"), ORIGENS_FOTO)
            if perm == "confirmada":
                if url is None:
                    ctx.erro("photo.url", "permissão confirmada exige a URL da foto")
                if not ref:
                    ctx.erro("photo.permissionRef", "permissão confirmada exige referência que a fundamente")
                if chk is None:
                    ctx.erro("photo.checkedAt", "permissão confirmada exige a data da checagem")
            dados_foto = {"url": url, "origin": origem, "usePermission": perm,
                          "permissionRef": ref, "checkedAt": foto.get("checkedAt")}
    elif eh_a:
        ctx.falta("photo.usePermission")

    # --- verifiedFacts
    fatos = []
    vf = obj.get("verifiedFacts", [])
    if not isinstance(vf, list) or len(vf) > 20:
        ctx.erro("verifiedFacts", "esperada lista de até 20 itens")
    else:
        for i, f in enumerate(vf):
            c = f"verifiedFacts[{i}]"
            fo = _objeto(ctx, c, f, CAMPOS["fact"])
            if fo is None:
                continue
            _obrigatorios(ctx, c, fo, CAMPOS["fact"])
            ref = fo.get("sourceRef")
            if eh_cur:                                  # curadoria: origem do fato = URL HTTPS verificável pelo nome (sem rede)
                ref = _url(ctx, f"{c}.sourceRef", ref, rastreio_proibido=True)
                _host_curadoria(ctx, f"{c}.sourceRef", ref)
            elif isinstance(ref, str) and ref.lower().startswith("https://"):
                ref = _url(ctx, f"{c}.sourceRef", ref, rastreio_proibido=True)
            else:
                ref = _txt(ctx, f"{c}.sourceRef", ref, max_len=300)
            _data(ctx, f"{c}.verifiedAt", fo.get("verifiedAt"), nulo_ok=False)
            texto_fato = _txt(ctx, f"{c}.text", fo.get("text"), max_len=500)
            if eh_cur and texto_fato is not None:
                er, av = cur.avaliar_fato_curadoria(texto_fato)
                for m in er:
                    ctx.erro(f"{c}.text", m)
                ctx.avisos += [f"{c}.text: {m}" for m in av]
            fatos.append({"text": texto_fato, "sourceRef": ref, "verifiedAt": fo.get("verifiedAt")})

    # --- publication
    pub = _objeto(ctx, "publication", obj.get("publication"), CAMPOS["publication"]) if "publication" in obj else None
    dados_pub = {}
    if pub is not None:
        _obrigatorios(ctx, "publication", pub, OBRIGATORIOS["publication"])
        estado = _enum(ctx, "publication.state", pub.get("state"), ESTADOS_PUBLICACAO) if "state" in pub else None
        pub_em = _data(ctx, "publication.publishedAt", pub.get("publishedAt"))
        canal = _txt(ctx, "publication.channel", pub.get("channel"), max_len=80)
        if canal and _CHAT_ID.match(canal):
            ctx.erro("publication.channel", "canal deve ser nome público, nunca ID privado")
            canal = None
        dados_pub = {"state": estado, "publishedAt": pub.get("publishedAt"), "channel": canal}
        if eh_a:
            if estado is not None and estado != "publicada":
                ctx.erro("publication.state", "fonte A exige state='publicada'")
            if pub.get("publishedAt") is None:
                ctx.falta("publication.publishedAt")
            elif pub_em and exportada and pub_em > exportada:
                ctx.erro("publication.publishedAt", "posterior à exportação")
        if eh_b:
            if estado is not None and estado != "nao_publicada":
                ctx.erro("publication.state", "fonte B exige state='nao_publicada' (nunca publicada)")
            if pub.get("publishedAt") is not None:
                ctx.erro("publication.publishedAt", "fonte B não pode ter data de publicação")

    # --- references
    refs = []
    rf = obj.get("references", [])
    if not isinstance(rf, list) or len(rf) > 20:
        ctx.erro("references", "esperada lista de até 20 itens")
    else:
        for i, r in enumerate(rf):
            c = f"references[{i}]"
            ro = _objeto(ctx, c, r, CAMPOS["reference"])
            if ro is None:
                continue
            _obrigatorios(ctx, c, ro, CAMPOS["reference"])
            url_ref = _url(ctx, f"{c}.url", ro.get("url"), rastreio_proibido=True)
            if eh_cur:
                _host_curadoria(ctx, f"{c}.url", url_ref)
            refs.append({"label": _txt(ctx, f"{c}.label", ro.get("label"), max_len=120), "url": url_ref})

    # --- eligibility
    el = _objeto(ctx, "eligibility", obj.get("eligibility"), CAMPOS["eligibility"]) if "eligibility" in obj else None
    dados_el = {}
    if el is not None:
        _obrigatorios(ctx, "eligibility", el, OBRIGATORIOS["eligibility"])
        flag = el.get("agentPublicationEligible")
        if "agentPublicationEligible" in el and not isinstance(flag, bool):
            ctx.erro("eligibility.agentPublicationEligible", "esperado true/false")
        if eh_b and flag is not False and "agentPublicationEligible" in el:
            ctx.erro("eligibility.agentPublicationEligible", "fonte B nunca pode ser elegível (deve ser false)")
        if eh_cur:                                       # valor fixo conhecido: comparação exata, sem relaxar o detector de segredos
            motivo_bloqueio = el.get("blockReason")
            if motivo_bloqueio != BLOCK_REASON_CURADORIA:
                ctx.erro("eligibility.blockReason", "curadoria manual exige o motivo de bloqueio padrão da curadoria")
                motivo_bloqueio = None
        else:
            motivo_bloqueio = _txt(ctx, "eligibility.blockReason", el.get("blockReason"), max_len=200)
        dados_el = {"agentPublicationEligible": flag, "blockReason": motivo_bloqueio}

    if eh_cur:                                          # regras adicionais da curadoria manual (contrato 1.1)
        _host_curadoria(ctx, "product.officialUrl", dados_prod.get("officialUrl"))
        if dados_prod.get("title"):
            er, av = cur.avaliar_titulo_curadoria(dados_prod["title"])
            for m in er:
                ctx.erro("product.title", m)
            ctx.avisos += [f"product.title: {m}" for m in av]
        if len(fatos) == 0:
            ctx.avisos.append("curadoria sem fatos verificados: nenhuma característica poderá ser usada")

    if disp == "unknown":
        ctx.avisos.append("disponibilidade desconhecida")

    if ctx.erros:
        return fim("rejeitado")

    res.dados = {
        "schemaVersion": sv, "exportId": obj["exportId"], "exportedAt": obj["exportedAt"],
        "source": {"kind": kind, "system": SISTEMA_CURADORIA if eh_cur else SISTEMA_AGENTE},
        "product": dados_prod, "price": dados_price, "availability": disp, "photo": dados_foto,
        "verifiedFacts": fatos,
        "publication": dados_pub, "references": refs, "eligibility": dados_el,
    }
    res.avisos = ctx.avisos
    return res
