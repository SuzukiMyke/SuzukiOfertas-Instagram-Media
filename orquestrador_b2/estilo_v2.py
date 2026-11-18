"""Estilo editorial v2 (B2R): títulos derivados dos fatos, CTA de captação, escolha de layouts e verificações de texto.

Pós-processa SOMENTE o que a ponte (``ficha_para_carrossel_v11``) permitiu: os fatos vêm dos slides de característica que a ponte
gerou (fatos fora do prazo, com termo comercial ou de risco ALTA já foram omitidos por ela) e os bloqueios dela nunca são contornados.
Nunca inventa característica: o texto explicativo é sempre o fato original, sem alteração. Números e unidades são EXTRAÍDOS do fato.
Todo texto novo passa pela avaliação de risco existente (``politica_titulos``) e pelas regras de alegação comercial da curadoria; se
reprovar, o slide é descartado e registrado, e se sobrarem menos de 3 slides o carrossel é BLOQUEADO (nunca entregue incompleto).
Sem reticências para esconder conteúdo e sem texto abaixo dos tamanhos mínimos (isso é garantido pelos layouts).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field

from produtos.curadoria_regras_v11 import alegacoes_comerciais
from produtos.politica_titulos import ALTA, avaliar_titulo

from . import ilustracoes

ESTILOS = ("auto", "v1", "v2")
MIN_SLIDES, MAX_SLIDES = 3, 5
TITULO_MAX = 22
TITULO_NEUTRO = "NA PRÁTICA"
TITULO_CTA = "ACHADOS TODO DIA NO SEU CELULAR"
CORPO_CTA_COM_LINKS = "Siga o Suzuki Ofertas no WhatsApp e no Telegram."
CORPO_CTA_NEUTRO = "Acompanhe o Suzuki Ofertas no WhatsApp e no Telegram."            # sem links validados fornecidos
COMPLEMENTO_CTA = "Ative as notificações e compartilhe com quem gosta de ofertas."
FOCO = [0.5, 0.45]
# Fixtures fictícias aprovadas para a aprovação de TESTE do fundo (identificadas pelo hash do conteúdo CANÔNICO: JSON ordenado, sem espaços).
FIXTURES_B2R = {
    "803a3a2de1edf095cb4c7639678104da160ff698dc7635f22e36a905de022c6c": {"arquivo": "ficha_tecnologia_fone.json", "id": "C101", "categoria": "tecnologia"},
    "7d813cb9a2323e7f729921680d4083d967656e89be3f2ec29c32b4ec568e5e10": {"arquivo": "ficha_casa_cozinha_panela.json", "id": "C102", "categoria": "casa_cozinha"},
    "64fd0bc927fe5dc6cbfb6aebd75fd4bf18dfbd9107cdbcb02aa5b37e11d1ffd1": {"arquivo": "ficha_ferramentas_furadeira.json", "id": "C103", "categoria": "ferramentas"},
}
# Termos comerciais proibidos nos textos e legendas deste fluxo fictício ("oficial" NÃO está na lista: pode identificar canais confirmados).
TERMOS_PROIBIDOS = re.compile(
    r"R\$|%|\bOFF\b|estoque|últimas?\s+unidades?|comprovad\w*|garantid\w*|melhor\s+preço|menor\s+preço|imperd\w*|"
    r"desconto|promoç\w*|frete|corra\b|só\s+hoje|urgente", re.I)
_STOP = {"de", "do", "da", "dos", "das", "com", "em", "para", "por", "a", "o", "e", "até", "no", "na", "sem", "ao"}
_UNIDADES = {"l": "L", "litro": "L", "litros": "L", "kg": "kg", "quilo": "kg", "quilos": "kg", "g": "g", "grama": "g", "gramas": "g",
             "v": "V", "volt": "V", "volts": "V", "h": "h", "hora": "h", "horas": "h", "w": "W", "watt": "W", "watts": "W", "mah": "mAh",
             "cm": "cm", "mm": "mm", "gb": "GB", "tb": "TB", "min": "min", "minuto": "min", "minutos": "min", "dia": "dias", "dias": "dias",
             "ano": "anos", "anos": "anos"}
_NUM = re.compile(r"(?<![\w,.])(\d+(?:[.,]\d+)?)\s*(" + "|".join(sorted(map(re.escape, _UNIDADES), key=len, reverse=True)) + r")(?![\wÀ-ÿ])", re.I)


def hash_canonico(obj) -> str:
    """SHA-256 do conteúdo canônico (JSON com chaves ordenadas, sem espaços, UTF-8): independe de formatação do arquivo."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def identificar_fixture(sha_bytes: str, obj, legadas) -> dict | None:
    """Fixture fictícia reconhecida por CONTEÚDO: a fixture original da B2 (hash dos bytes, em ``legadas``) ou uma das três da B2R
    (hash canônico). Nunca por domínio ``.example`` nem por estrutura. ``None`` se desconhecida."""
    if sha_bytes in legadas:
        return {"id": "legada_b2", "arquivo": str(legadas[sha_bytes]), "estilo_padrao": "v1"}
    h = hash_canonico(obj) if isinstance(obj, dict) else None
    if h in FIXTURES_B2R:
        return {**FIXTURES_B2R[h], "estilo_padrao": "v2"}
    return None


def _sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii").lower()


def extrair_destaque(fato: str) -> dict | None:
    """Primeiro número com unidade do fato (``{"numero", "unidade", "antes"}``) ou ``None``. Nada é calculado nem convertido."""
    m = _NUM.search(fato or "")
    if not m:
        return None
    return {"numero": m.group(1), "unidade": _UNIDADES[m.group(2).lower()], "antes": fato[:m.start()].strip()}


def _palavras_uteis(texto: str) -> list[str]:
    return [p for p in re.split(r"\s+", texto.strip()) if p and _sem_acento(p) not in _STOP]


def titulo_do_fato(fato: str) -> str:
    """Título curto (≤ 22 caracteres, palavra inteira) derivado do próprio fato: a primeira palavra útil antes do número (ex.:
    CAPACIDADE, AUTONOMIA, PESO) ou, sem número, a primeira palavra útil do fato; sem palavra útil → ``NA PRÁTICA``."""
    d = extrair_destaque(fato)
    uteis = _palavras_uteis(d["antes"] if d else fato)
    cand = uteis[0].upper() if uteis else ""
    return cand if cand and len(cand) <= TITULO_MAX and cand.isalpha() else TITULO_NEUTRO


def avaliar_texto(texto: str) -> list[str]:
    """Motivos de reprovação do texto (lista vazia = aceito): risco ALTA, alegação comercial da curadoria ou termo proibido do fluxo."""
    motivos = []
    if avaliar_titulo(texto)["nivel"] == ALTA:
        motivos.append("risco ALTA")
    com = alegacoes_comerciais(texto)
    if com:
        motivos.append("alegação comercial (" + ", ".join(com) + ")")
    if TERMOS_PROIBIDOS.search(texto):
        motivos.append("termo comercial proibido")
    return motivos


def _link_curto(url: str) -> str:
    return re.sub(r"^https://", "", url).rstrip("/")


def cta_textos(links: dict | None) -> dict:
    """Textos do CTA de captação. Com links VALIDADOS pela ponte, mostra-os; sem links, usa o texto neutro e não cita legenda, bio ou link."""
    links = {k: v for k, v in (links or {}).items() if v}
    destaque = " · ".join(f"{'WhatsApp' if k == 'whatsapp' else 'Telegram'}: {_link_curto(v)}" for k, v in sorted(links.items(), reverse=True))
    return {"titulo": TITULO_CTA, "texto": f"{CORPO_CTA_COM_LINKS if links else CORPO_CTA_NEUTRO}\n{COMPLEMENTO_CTA}",
            **({"destaque": destaque} if destaque else {})}


@dataclass
class Montagem:
    slides: list[dict] = field(default_factory=list)
    descartes: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    bloqueios: list[dict] = field(default_factory=list)


def dividir_nome(titulo: str) -> tuple[str, str]:
    """Nome do produto em (título branco, destaque amarelo) por palavras inteiras, sem abreviar."""
    pal = titulo.upper().split()
    if len(pal) <= 1:
        return " ".join(pal), ""
    corte = max(1, round(len(pal) * 0.6))
    return " ".join(pal[:corte]), " ".join(pal[corte:])


def montar_slides(ficha: dict, ponte_config: dict, ids: dict, links: dict | None) -> Montagem:
    """Slides do estilo v2 a partir da ficha e dos slides PERMITIDOS pela ponte.

    ``ids``: ``{"ilustracao": id, "fundos": [id, id, id]}`` (imagens já registradas no catálogo temporário).
    Sequência: capa (ilustração) → [destaque numérico] → [lista] → CTA. 1 fato: capa, destaque, CTA · 2 fatos: capa, lista, CTA ·
    3 fatos: capa, destaque, lista (2 fatos restantes), CTA. Layouts vizinhos nunca se repetem e cada fundo é usado uma vez."""
    m = Montagem()
    fatos = [s["texto"] for s in ponte_config["slides"] if s.get("titulo") == "CARACTERÍSTICA"]
    if not fatos:
        m.bloqueios.append({"codigo": "sem_caracteristicas", "motivo": "a ponte não liberou nenhuma característica verificável para os slides"})
        return m
    t_nome, d_nome = dividir_nome(ficha["produto"]["title"])
    fundos = iter(ids["fundos"])

    def adicionar(layout, foto, **campos):
        m.slides.append({"layout": layout, "foto": foto, "foco": list(FOCO), **{k: v for k, v in campos.items() if v}})

    adicionar("ilustracao_capa", ids["ilustracao"], titulo=t_nome, destaque=d_nome, texto=ficha["produto"]["store"])
    corpo = list(fatos)
    idx = next((i for i, f in enumerate(corpo) if extrair_destaque(f)), None)
    if len(corpo) in (1, 3) and idx is not None:                    # destaque numérico: só com número e unidade reais no fato
        f0 = corpo.pop(idx)
        d = extrair_destaque(f0)
        titulo, numero = titulo_do_fato(f0), f"{d['numero']} {d['unidade']}"
        motivos = [x for t in (titulo, numero) for x in avaliar_texto(t)]
        if motivos:                                                 # nunca contornado: o slide é descartado e registrado
            m.descartes.append({"slide": "destaque_numerico", "texto": f"{titulo} / {numero}", "motivo": "; ".join(motivos)})
            corpo.insert(idx, f0)
        else:
            adicionar("destaque_numerico", next(fundos), titulo=titulo, destaque=numero, texto=f0)
    if 2 <= len(corpo) <= 3:
        adicionar("lista_caracteristicas", next(fundos), titulo=TITULO_NEUTRO, texto="\n".join(corpo))
    adicionar("cta_seguir", next(fundos), **cta_textos(links))
    for s in m.slides:                                              # termos proibidos em TODO texto de slide (fatos e CTA incluídos)
        for campo in ("titulo", "destaque", "texto"):
            achado = TERMOS_PROIBIDOS.search(str(s.get(campo, "")))
            if achado:
                m.bloqueios.append({"codigo": "termo_proibido", "motivo": f"{s['layout']}.{campo}: termo comercial proibido ('{achado.group(0)}')"})
    if not MIN_SLIDES <= len(m.slides) <= MAX_SLIDES:
        m.bloqueios.append({"codigo": "numero_de_slides",
                            "motivo": f"{len(m.slides)} slides válidos; o carrossel exige de {MIN_SLIDES} a {MAX_SLIDES} (nada é entregue incompleto)"})
    return m


def verificar_variedade(slides: list[dict], variantes_por_foto: dict[str, str]) -> list[str]:
    """Regras de diversidade: layouts vizinhos diferentes, ≥ 3 layouts distintos com 4+ slides, fundo repetido em no máximo 2 slides."""
    erros = []
    lay = [s["layout"] for s in slides]
    for a, b in zip(lay, lay[1:]):
        if a == b:
            erros.append(f"layouts vizinhos iguais: {a}")
    if len(slides) >= 4 and len(set(lay)) < 3:
        erros.append("menos de 3 layouts distintos em carrossel com 4 ou mais slides")
    usos: dict[str, int] = {}
    for s in slides:
        v = variantes_por_foto.get(s["foto"], s["foto"])
        usos[v] = usos.get(v, 0) + 1
    erros += [f"fundo '{v}' usado em {n} slides (máximo 2)" for v, n in usos.items() if n > 2]
    return erros


def categoria_da_ficha(ficha: dict) -> str:
    return ilustracoes.categoria_de(ficha["produto"].get("category"), ficha["produto"].get("title"))
