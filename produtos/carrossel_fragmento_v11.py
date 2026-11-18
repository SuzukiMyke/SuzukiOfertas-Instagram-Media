"""Ficha 1.1 -> carrossel (JSON do gerador híbrido, 1080×1350). Função pura; NÃO executa o gerador.

``ficha_para_carrossel_v11`` (mesmo estilo de ``reel_fragmento_v11.ficha_para_fragmento_v11``) não acessa rede, não lê o
relógio do sistema (o horário efetivo de publicação é PARÂMETRO) e não grava arquivos. Devolve o JSON no formato de
``exemplos/carrossel_exemplo.json`` (``id``, ``permitir_fotos_pendentes``, ``slides[]`` com ``layout``, ``foto``, ``foco``,
``titulo``, ``destaque``, ``texto`` e, quando a foto se repete, ``reutilizar``) mais avisos e bloqueios para a revisão humana.
O contrato do gerador não é alterado. O resultado é SEMPRE um rascunho: ``aprovado_para_publicacao`` nunca é definido aqui.

Elegibilidade (fichas fora disso NÃO geram conteúdo e voltam como relatório ``status: "bloqueado"`` com o bloqueio
``estado_inelegivel`` e os estados aceitos: é uma situação NORMAL de um lote, então não levanta exceção;
``CarrosselRecusado`` fica só para chamada inválida: ficha de outro contrato, horário sem fuso, classe visual ou alegação malformadas):
- fonte A: ``aprovado_para_rascunho`` ou ``aprovado_para_publicacao`` (aprovação humana já registrada);
- fonte B: ``candidato_nao_verificado`` ou ``aprovado_para_rascunho`` → só rascunho EDITORIAL: nunca preço, desconto, estoque,
  urgência, "menor preço" nem qualquer alegação comercial.
Alegações comerciais (fonte A) só entram se o portão de pré-publicação (``prepublicacao``) permitir para o horário efetivo
informado: essencial inválida → bloqueio do conjunto; acessória inválida → omitida e registrada em ``alegacoes_omitidas``.
Títulos: risco ALTA bloqueia; MÉDIA exige revisão humana (aviso). Fatos: só os frescos (``fatosParaUso``), nunca truncados.
Imagens: ``foto_real_autorizada`` exige permissão humana válida e o hash do catálogo do gerador igual a ``fotoSha256``;
``ambientacao_ilustrativa`` e ``composicao_grafica`` são rotuladas e nunca representam o produto específico.
Não há reverificação do preço na hora da publicação (capacidade inexistente): vale só a janela declarada.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

from . import estados
from .politica_titulos import ALTA, MEDIA, avaliar_titulo
from .tempo import formatar
from .prepublicacao import BLOQUEAR, FUNCOES, LIBERAR, TIPOS_ALEGACAO, avaliar_portao

CLASSES_VISUAIS = ("foto_real_autorizada", "ambientacao_ilustrativa", "composicao_grafica")
LAYOUTS = ("foto_topo", "cartao", "foto_cheia")             # os aceitos pelo gerador
LAYOUTS_EMITIDOS = ("foto_topo", "cartao")                    # os emitidos aqui: o validador do gerador reprova muitas combinações
# de texto em "foto_cheia" (exige >= 300 px de foto visível); com foto_topo/cartao o pior caso 22/22/80 sempre passa (ver testes)
RESOLUCAO = "1080x1350"
# Limites calibrados com o gerador (pior caso: letras maiúsculas largas; ver tests): título e destaque até 22 caracteres cada
# (maiúsculas), texto até 80, de 1 a 10 slides.
LIM_TITULO, LIM_DESTAQUE, LIM_TEXTO, MAX_SLIDES = 22, 22, 80, 10
MAX_FATOS = 3
HOSTS_OFICIAIS = {"whatsapp": ("wa.me", "chat.whatsapp.com", "whatsapp.com"), "telegram": ("t.me", "telegram.me")}
AVISO_LEGENDA = "Publicidade. Preços e condições podem mudar; confira no link."
ROTULO_CLASSE = {"foto_real_autorizada": None, "ambientacao_ilustrativa": "Imagem ilustrativa", "composicao_grafica": "Arte ilustrativa"}
_CTRL = re.compile(r"[\x00-\x1f\x7f​-‏‪-‮⁠﻿]")
_FOCO_PADRAO = (0.5, 0.45)


class CarrosselRecusado(ValueError):
    """Chamada inválida (ficha de outro contrato, horário sem fuso, classe visual ou alegação malformadas); nenhum conteúdo."""


def _limpa(txt) -> str:
    return re.sub(r"\s+", " ", _CTRL.sub("", unicodedata.normalize("NFKC", str(txt)))).strip()


def _slug(txt: str) -> str:
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def reais(centavos: int) -> str:
    inteiro, frac = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{frac:02d}"


def _dividir(texto: str, lim1: int, lim2: int) -> tuple[str, str, bool]:
    """Divide em (titulo, destaque) por palavras, em maiúsculas; ``True`` se foi preciso abreviar (reticências)."""
    palavras, i, abreviado, linhas = _limpa(texto).split(), 0, False, []
    for lim in (lim1, lim2):
        atual = ""
        while i < len(palavras):
            cand = f"{atual} {palavras[i]}".strip()
            if len(cand) <= lim:
                atual, i = cand, i + 1
            elif not atual:                                       # uma só palavra maior que a linha
                atual, i, abreviado = palavras[i][:lim], i + 1, True
                break
            else:
                break
        linhas.append(atual)
    d = linhas[1]
    if i < len(palavras):                                         # sobrou texto: abrevia com reticências
        abreviado = True
        d = (d[:LIM_DESTAQUE - 1].rstrip() if len(d) >= lim2 else d) + "…"
    return linhas[0].upper(), d.upper(), abreviado


def _slide(layout, foto, titulo, destaque, texto, foco, reutilizar) -> dict:
    s = {"layout": layout, "foto": foto, "foco": list(foco), "titulo": titulo[:LIM_TITULO], "destaque": destaque[:LIM_DESTAQUE],
         "texto": texto[:LIM_TEXTO]}
    if reutilizar:
        s["reutilizar"] = True
    return {k: v for k, v in s.items() if v not in ("", None)}


def _link_oficial(canal: str, url) -> str | None:
    """URL oficial válida do canal (https, host permitido, sem credenciais/porta/consulta) ou ``None``."""
    if not isinstance(url, str):
        return None
    u = urlparse(url.strip())
    if u.scheme != "https" or u.username or u.password or u.port or u.query or u.fragment or not u.path.strip("/"):
        return None
    if (u.hostname or "").lower() not in HOSTS_OFICIAIS[canal]:
        return None
    return url.strip()


def _verificar_foto(ficha: dict, classe: str, foto_id, catalogo, bloqueios: list, avisos: list) -> None:
    def bloq(cod, motivo):
        bloqueios.append({"codigo": cod, "motivo": motivo})
    if not foto_id or not isinstance(foto_id, str):
        bloq("foto_catalogo_ausente", "informe foto_catalogo_id (ID de uma foto do catálogo do gerador)")
        return
    meta = (catalogo or {}).get(foto_id) if catalogo is not None else None
    if classe == "foto_real_autorizada":
        f = ficha["foto"]
        if not f.get("utilizavel") or not f.get("fotoSha256") or not f.get("termoId"):
            bloq("foto_sem_permissao_humana", "foto real exige registro humano de permissão válido (termo + hash do arquivo): "
                 + str(f.get("motivo") or "sem registro"))
            return
        if catalogo is None or meta is None:
            bloq("foto_fora_do_catalogo", "catálogo do gerador não informado ou foto ausente: hash não verificável")
            return
        if meta.get("provedor") != "foto-real" or meta.get("origem") != "fotografia-real":
            bloq("foto_nao_e_real", "o catálogo não registra esta foto como fotografia real")
        if f["fotoSha256"] not in (meta.get("sha256_original"), meta.get("sha256")):
            bloq("foto_hash_divergente", "hash da foto do catálogo diverge de fotoSha256 do registro humano: "
                 "não pode ser usada como foto real autorizada")
        if (meta.get("aprovacao") or {}).get("status") != "aprovada":
            bloq("foto_nao_aprovada_no_catalogo", "a foto do catálogo ainda não foi aprovada visualmente")
        return
    # ilustrativa / gráfica: nunca a foto real do produto passando por ilustração
    if meta is None:
        avisos.append("catálogo do gerador não informado: origem da imagem ilustrativa não verificada")
    elif meta.get("provedor") == "foto-real" or meta.get("origem") == "fotografia-real":
        bloq("foto_real_como_ilustracao", "fotografia real só pode entrar como foto_real_autorizada (com permissão e hash)")
    elif (meta.get("aprovacao") or {}).get("status") != "aprovada":
        bloq("foto_nao_aprovada_no_catalogo", "a imagem ilustrativa ainda não foi aprovada visualmente no catálogo")


def ficha_para_carrossel_v11(ficha: dict, *, t_publicacao: datetime, foto_catalogo_id: str | None = None,
                             recurso_visual: str = "composicao_grafica", catalogo: dict | None = None,
                             links_oficiais: dict | None = None, alegacoes: list[dict] | None = None,
                             preco_aprovado_centavos: int | None = None, margem_min: int = 30,
                             prova_menor_preco: bool = False, carrossel_id: str | None = None,
                             foco: tuple = _FOCO_PADRAO) -> dict:
    """Devolve o dicionário de resultado (ver módulo). ``carrossel`` é ``None`` quando há bloqueio."""
    if ficha.get("contrato") != "1.1":
        raise CarrosselRecusado("ficha não é do contrato 1.1")
    if not isinstance(t_publicacao, datetime) or t_publicacao.tzinfo is None:
        raise CarrosselRecusado("t_publicacao deve ser datetime com fuso (UTC): o relógio nunca é lido aqui")
    if recurso_visual not in CLASSES_VISUAIS:
        raise CarrosselRecusado(f"recurso_visual deve ser um de {', '.join(CLASSES_VISUAIS)}")
    origem, estado = ficha.get("origem"), ficha.get("estado")
    elegiveis = ((estados.APROVADO_RASCUNHO, estados.APROVADO_PUBLICACAO) if origem == "A"
                 else (estados.CANDIDATO_NAO_VERIFICADO, estados.APROVADO_RASCUNHO) if origem == "B" else ())
    if estado not in elegiveis:
        return _inelegivel(ficha, estado, origem, elegiveis, t_publicacao, recurso_visual)

    prod = ficha["produto"]
    bloqueios: list[dict] = []
    avisos: list[str] = ["rascunho: revisão humana obrigatória antes de qualquer publicação ou agendamento",
                         "aprovado_para_publicacao NUNCA é definido por esta função"]
    omitidas: list[dict] = []
    revisao = True

    # --- título (política de títulos)
    tit = avaliar_titulo(prod["title"])
    if tit["nivel"] == ALTA:
        bloqueios.append({"codigo": "titulo_risco_alta", "motivo": "título com termo de risco ALTA (" + ", ".join(tit["trechos"])
                          + "): não pode ser usado em texto público"})
    elif tit["nivel"] == MEDIA:
        avisos.append("título com termo de risco MÉDIA (" + ", ".join(tit["trechos"]) + "): não é fato verificado; revisão humana")

    # --- imagem
    _verificar_foto(ficha, recurso_visual, foto_catalogo_id, catalogo, bloqueios, avisos)
    rotulo = ROTULO_CLASSE[recurso_visual]
    if rotulo:
        avisos.append(f"{rotulo}: não representa o produto específico; rotulada na capa e na legenda")

    # --- alegações comerciais (somente pelo portão; B nunca)
    pedidas = []
    for a in (alegacoes or []):
        if not isinstance(a, dict) or a.get("funcao") not in FUNCOES or a.get("tipo") not in TIPOS_ALEGACAO or not a.get("id"):
            raise CarrosselRecusado("alegação inválida (id, tipo e função essencial|acessoria são obrigatórios)")
        pedidas.append({"id": a["id"], "tipo": a["tipo"], "funcao": a["funcao"],
                        "tem_variante_sem": bool(a.get("tem_variante_sem", a["funcao"] == "acessoria")),
                        "texto": a.get("texto")})
    portao = avaliar_portao(ficha, preco_aprovado_centavos=preco_aprovado_centavos, t_publicacao=t_publicacao, alegacoes=pedidas,
                            margem_min=margem_min, prova_menor_preco=prova_menor_preco)
    permitidas = set(portao["alegacoes_comerciais"]) if origem == "A" else set()
    if portao["acao"] == BLOQUEAR:
        bloqueios.append({"codigo": "alegacao_essencial_invalida", "motivo": "; ".join(portao["motivos"])})
    else:
        for a in pedidas:
            if a["id"] not in permitidas:
                omitidas.append({"id": a["id"], "tipo": a["tipo"], "motivo": "; ".join(portao["motivos"]) or "não permitida"})
    if origem == "B" and not pedidas:
        avisos.append("fonte B: rascunho editorial sem preço, desconto, estoque, urgência ou alegação comercial")

    # --- links oficiais (somente os fornecidos) e afiliação
    links, links_avisos = {}, []
    for canal in ("whatsapp", "telegram"):
        bruto = (links_oficiais or {}).get(canal)
        if bruto is None:
            links_avisos.append(f"link oficial do {canal} não informado: CTA sem link")
        elif _link_oficial(canal, bruto) is None:
            bloqueios.append({"codigo": f"link_{canal}_invalido",
                              "motivo": f"link do {canal} fora do padrão oficial (https, host {', '.join(HOSTS_OFICIAIS[canal])})"})
        else:
            links[canal] = _link_oficial(canal, bruto)
    avisos += links_avisos
    afiliado = bool(prod.get("affiliateUrl"))

    # --- fatos (nunca truncados; só frescos; sem termo comercial)
    fatos, usados = [], 0
    for f in ficha.get("fatosParaUso", []):
        t = _limpa(f["text"])
        if avaliar_titulo(t)["nivel"] == ALTA or "r$" in t.lower():
            omitidas.append({"id": "fato", "tipo": "fato", "motivo": "texto do fato contém termo comercial/ALTA"})
        elif len(t) > LIM_TEXTO:
            avisos.append(f"fato omitido: mais de {LIM_TEXTO} caracteres (não é truncado)")
        elif usados >= MAX_FATOS:
            avisos.append("fato omitido: limite de fatos por carrossel")
        else:
            fatos.append(t)
            usados += 1
    if ficha.get("fatosEmRevisao"):
        avisos.append("há fatos em revisão: ficam fora de qualquer alegação")

    if bloqueios:
        return _resultado(ficha, None, bloqueios, avisos, omitidas, permitidas, portao, recurso_visual, afiliado, links, t_publicacao)

    # --- montagem dos slides
    foto = foto_catalogo_id
    usado = []                                                   # a foto só se repete com "reutilizar": true

    def adicionar(layout, titulo, destaque, texto):
        usado.append(1)
        return _slide(layout, foto, titulo, destaque, texto, foco, len(usado) > 1)
    store = _limpa(prod["store"])
    t_cap, d_cap, abreviado = _dividir(prod["title"], LIM_TITULO, LIM_DESTAQUE)
    if abreviado:
        avisos.append("título do produto abreviado na capa (limite do gerador); conferir o nome completo na legenda")
    partes = [store[:24]] + (["Publicidade"] if afiliado else []) + ([rotulo] if rotulo else [])
    slides = [adicionar("foto_topo", t_cap, d_cap, " · ".join(partes))]
    for a in pedidas:
        if a["id"] not in permitidas:
            continue
        loja = store[:28]
        if a["tipo"] == "preco":
            slides.append(adicionar("cartao", "PREÇO NA LOJA", reais(ficha["preco"]["amountCents"]),
                                    f"{loja}. Preços e condições podem mudar."))
        elif a["tipo"] == "desconto":
            orig, atual = ficha["preco"].get("originalAmountCents"), ficha["preco"]["amountCents"]
            if not orig or orig <= atual:
                omitidas.append({"id": a["id"], "tipo": "desconto", "motivo": "sem preço original maior que o atual"})
                continue
            slides.append(adicionar("cartao", "DESCONTO", f"{(orig - atual) * 100 // orig}% OFF",
                                    f"De {reais(orig)} por {reais(atual)} na {loja}"))
        elif a["tipo"] == "disponibilidade":
            slides.append(adicionar("cartao", "DISPONIBILIDADE", "EM ESTOQUE", "Na data da verificação; pode mudar."))
        else:                                                    # oferta, urgência, menor preço: texto do chamador, não truncado
            txt = _limpa(a.get("texto") or "")
            t, d, abrev = _dividir(txt, LIM_TITULO, LIM_DESTAQUE)
            if not txt or abrev:
                omitidas.append({"id": a["id"], "tipo": a["tipo"], "motivo": "texto ausente ou maior que o limite do gerador"})
                continue
            slides.append(adicionar("cartao", t, d, "Preços e condições podem mudar."))
    for t in fatos:
        slides.append(adicionar("cartao", "CARACTERÍSTICA", "COMPROVADA", t))
    cta_txt = (f"WhatsApp: {links['whatsapp'][8:]} · Telegram: {links['telegram'][8:]}" if len(links) == 2 else "Links oficiais na legenda.")
    if len(cta_txt) > LIM_TEXTO:
        cta_txt = "Links oficiais na legenda."
    slides.append(adicionar("foto_topo", "CHAME NO", "WHATSAPP E TELEGRAM", cta_txt))
    if len(slides) > MAX_SLIDES:
        bloqueios.append({"codigo": "slides_demais", "motivo": f"o gerador aceita de 1 a {MAX_SLIDES} slides"})
        return _resultado(ficha, None, bloqueios, avisos, omitidas, permitidas, portao, recurso_visual, afiliado, links, t_publicacao)

    cid = carrossel_id or f"{_slug(prod['provider'])}-{_slug(str(prod['id']))}-{ficha['versao']['exportId'][:8]}"
    cid = _slug(cid)[:60]
    carrossel = {"id": cid, "permitir_fotos_pendentes": False, "slides": slides}
    return _resultado(ficha, carrossel, bloqueios, avisos, omitidas, permitidas, portao, recurso_visual, afiliado, links, t_publicacao)


def _resultado(ficha, carrossel, bloqueios, avisos, omitidas, permitidas, portao, classe, afiliado, links, t_publicacao) -> dict:
    legenda = [AVISO_LEGENDA] if (afiliado or permitidas) else []
    if afiliado:
        legenda.insert(0, "Publicidade: este conteúdo pode conter link de afiliado.")
    if ROTULO_CLASSE[classe]:
        legenda.append(f"{ROTULO_CLASSE[classe]}: não representa fielmente o produto.")
    if links:
        legenda.append(" · ".join(f"{c.capitalize()}: {u}" for c, u in sorted(links.items())))
    return {
        "contrato": "1.1", "status": "bloqueado" if bloqueios else "rascunho", "resolucao": RESOLUCAO,
        "carrossel": carrossel, "bloqueios": bloqueios, "avisos": avisos, "alegacoes_omitidas": omitidas,
        "alegacoes_comerciais_permitidas": sorted(permitidas), "portao": portao, "classe_visual": classe,
        "afiliado": afiliado, "origem": ficha["origem"], "estado_ficha": ficha["estado"],
        "revisao_humana_obrigatoria": True, "aprovado_para_publicacao_definido": False,
        "legenda_sugerida": "\n".join(legenda), "t_publicacao_avaliado": portao["avaliado_para"],
    }


def _inelegivel(ficha: dict, estado, origem, elegiveis, t_publicacao, classe) -> dict:
    """Relatório de bloqueio para ficha em estado inelegível: mesmas chaves do resultado normal, sem conteúdo e sem avaliar o portão."""
    motivo = (f"estado '{estado}' (origem {origem}) é inelegível para carrossel; estados aceitos: "
              + (", ".join(elegiveis) if elegiveis else "nenhum (origem desconhecida)") + ". Nenhum conteúdo foi gerado.")
    return {
        "contrato": "1.1", "status": "bloqueado", "resolucao": RESOLUCAO, "carrossel": None,
        "bloqueios": [{"codigo": "estado_inelegivel", "motivo": motivo, "estado": estado, "origem": origem,
                       "estados_elegiveis": list(elegiveis)}],
        "avisos": ["revisão humana: a ficha precisa chegar a um estado elegível antes de gerar rascunho"],
        "alegacoes_omitidas": [], "alegacoes_comerciais_permitidas": [], "portao": None, "classe_visual": classe,
        "afiliado": bool((ficha.get("produto") or {}).get("affiliateUrl")), "origem": origem, "estado_ficha": estado,
        "revisao_humana_obrigatoria": True, "aprovado_para_publicacao_definido": False,
        "legenda_sugerida": "", "t_publicacao_avaliado": formatar(t_publicacao),
    }
