"""Fluxo ponta a ponta B2. Cada etapa é registrada em ``etapas`` com status; qualquer parada deixa relatório explícito.

Etapas: 1 ficha -> 2 exportação B (curadoria_b) -> 3 receptor 1.1 -> 4 elegibilidade editorial -> 5 fundo de marca no catálogo
TEMPORÁRIO -> 6 aprovação da imagem -> 7 ficha -> carrossel -> 8 renderização (3 a 5 slides) -> 9 validação -> 10 relatórios
(a folha de contato e os relatórios fecham a etapa 10).

Aprovação da imagem: sem ``aprovar_fundo_ficticio`` o fluxo PARA com ``aprovacao_pendente`` (a imagem fica pendente, como no
funcionamento normal). Com a opção, só a fixture fictícia reconhecida (hash conhecido) e um catálogo temporário criado aqui são
aceitos; a aprovação é registrada como "teste", SEM valor de homologação humana.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image

from curadoria_b.exportador import ErroExportacao, exportar
from curadoria_b.ficha import ErroFicha, PRODUTOS_REAIS_HABILITADO, ler_ficha
from gerador import fundo_marca
from gerador.carrossel import gerar
from gerador.catalogo import RAIZ as RAIZ_REPO
from gerador.catalogo import Catalogo
from gerador.layouts import LAYOUTS, sem_texto
from gerador.validacao import validar_slide_v2
from produtos import estados
from produtos.carrossel_fragmento_v11 import ficha_para_carrossel_v11
from produtos.leitor import decodificar_json
from produtos.pipeline_v11 import processar_v11
from produtos.selecao_contrato import DADOS_REAIS_HABILITADO
from produtos.tempo import formatar

from . import estilo_v2, ilustracoes
from .folha import gerar_folha

VERSAO = "1.0"
RESOLUCAO = (1080, 1350)
MIN_SLIDES, MAX_SLIDES = 3, 5
# Única fixture reconhecida para a aprovação de teste: ``curadoria_b/exemplos_ficticios/ficha_valida.json`` (SHA-256 dos bytes).
FIXTURES_FICTICIAS = {"68e4dd96bee57e61ddd1e5670153c81381de8035156b5766a01e95099af989a3": "curadoria_b/exemplos_ficticios/ficha_valida.json"}
NAMESPACE = uuid.UUID("6f1f6f3e-2b0a-4a0e-9a53-5b6b7d0c4a11")
CTA_SEM_LINKS = "Conheça os canais do Suzuki Ofertas no WhatsApp e no Telegram."
TEXTO_CTA_PADRAO_DA_PONTE = "Links oficiais na legenda."
ESTADOS_ELEGIVEIS_B = (estados.CANDIDATO_NAO_VERIFICADO, estados.APROVADO_RASCUNHO)
APROVADOR_TESTE = "TESTE-FICTICIO (sem valor de homologação humana)"


class ErroFluxo(Exception):
    """Pré-condição violada (ex.: saída dentro do repositório)."""


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _dentro(a: Path, b: Path) -> bool:
    a, b = a.resolve(), b.resolve()
    return a == b or b in a.parents


class _Fluxo:
    def __init__(self, saida: Path, agora: datetime):
        self.saida, self.agora = saida, agora
        self.etapas: list[dict] = []
        self.avisos: list[str] = []
        self.bloqueios: list[dict] = []
        self.rel: dict = {}

    def etapa(self, nome: str, status: str, **extra):
        self.etapas.append({"n": len(self.etapas) + 1, "etapa": nome, "status": status, **extra})


def resolver_aprovacao(sha_ficha: str, aprovar_fundo_ficticio: bool, catalogo: Catalogo, fixture: dict | None = None) -> tuple[bool, str]:
    """``(permitida, motivo)``: só fixture reconhecida (por conteúdo) + catálogo temporário (nunca o do repositório).
    ``fixture``: resultado de ``estilo_v2.identificar_fixture``; ausente, vale apenas a fixture legada da B2 (hash dos bytes)."""
    if not aprovar_fundo_ficticio:
        return False, "sem a opção --aprovar-fundo-ficticio a imagem permanece pendente de aprovação humana"
    if fixture is None and sha_ficha not in FIXTURES_FICTICIAS:
        return False, "aprovação de teste recusada: a ficha não é a fixture fictícia reconhecida"
    if _dentro(Path(catalogo.raiz), RAIZ_REPO):
        return False, "aprovação de teste recusada: o catálogo não é temporário (está dentro do repositório)"
    return True, "aprovação de teste da fixture fictícia em catálogo temporário"


def executar(ficha_arquivo, saida, agora: datetime, *, aprovar_fundo_ficticio: bool = False, links_oficiais: dict | None = None,
             variante: int = 0, estilo: str = "auto") -> dict:
    """Executa o fluxo. Devolve o relatório (dicionário) com ``status``:
    ``concluido`` | ``aprovacao_pendente`` | ``rejeitado`` | ``bloqueado`` | ``aprovacao_de_teste_recusada``."""
    ficha_arquivo, saida = Path(ficha_arquivo), Path(saida)
    if estilo not in estilo_v2.ESTILOS:
        raise ErroFluxo(f"estilo inválido '{estilo}' (use {', '.join(estilo_v2.ESTILOS)})")
    if _dentro(saida, RAIZ_REPO):
        raise ErroFluxo("a pasta de saída deve ficar FORA do repositório (nada é versionado nesta etapa)")
    saida.mkdir(parents=True, exist_ok=True)
    f = _Fluxo(saida, agora)
    rel = f.rel
    rel.update({"fluxo": "orquestrador_b2", "versao": VERSAO, "estilo": None, "geradoEm": formatar(agora), "status": None, "fixtureFicticia": False,
                "restricoes": {"produtosReaisHabilitado": PRODUTOS_REAIS_HABILITADO, "dadosReaisHabilitado": DADOS_REAIS_HABILITADO,
                               "rede": "nao_utilizada", "publicacao": "nao_realizada", "agendamento": "nao_realizado",
                               "catalogoPersistenteTocado": False}})
    try:
        _executar(f, ficha_arquivo, agora, aprovar_fundo_ficticio, links_oficiais, variante, estilo)
    finally:
        rel["etapas"], rel["avisos"], rel["bloqueios"] = f.etapas, f.avisos, f.bloqueios
        _finalizar(f)
    return rel


def _executar(f: _Fluxo, ficha_arquivo: Path, agora: datetime, aprovar: bool, links: dict | None, variante: int, estilo: str = "auto") -> None:
    rel, saida = f.rel, f.saida
    # 1. ficha ------------------------------------------------------------------------------------------------------------
    try:
        bruto = ficha_arquivo.read_bytes()
        sha_ficha = _sha(bruto)
        obj = decodificar_json(bruto)
        ler_ficha(obj, agora)
    except OSError:
        f.etapa("ficha", "falhou", motivo="ficha ilegível")
        rel["status"] = "rejeitado"
        f.bloqueios.append({"codigo": "ficha_ilegivel", "motivo": "ficha ilegível"})
        return
    except ValueError as e:                                           # JSON inválido ou ErroFicha (ValueError)
        erros = getattr(e, "erros", [str(e)])
        f.etapa("ficha", "rejeitada", erros=erros)
        rel["status"] = "rejeitado"
        f.bloqueios += [{"codigo": "ficha_invalida", "motivo": m} for m in erros]
        return
    rel["fichaSha256"] = sha_ficha
    fixture = estilo_v2.identificar_fixture(sha_ficha, obj, FIXTURES_FICTICIAS)
    rel["fixtureFicticia"] = fixture is not None
    if fixture:
        rel["fixture"] = {"id": fixture["id"], "arquivo": fixture["arquivo"]}
    if estilo == "auto":                                                # fixture legada → v1 (reproduz a B2); demais → v2
        estilo = fixture["estilo_padrao"] if fixture else "v2"
    rel["estilo"] = estilo
    f.etapa("ficha", "ok", sha256=sha_ficha, fixtureFicticia=rel["fixtureFicticia"], estilo=estilo)
    # 2. exportação B -----------------------------------------------------------------------------------------------------
    export_id = str(uuid.uuid5(NAMESPACE, sha_ficha + formatar(agora)))      # determinístico para a mesma ficha e horário
    lote_raiz = saida / "lote_curadoria"
    if (lote_raiz / "B").exists():
        shutil.rmtree(lote_raiz)                                            # pasta de trabalho criada por este fluxo
    try:
        exp = exportar(ficha_arquivo, lote_raiz, agora, export_id=export_id)
    except (ErroFicha, ErroExportacao) as e:
        f.etapa("exportacao_b", "falhou", motivo=str(e)[:300])
        rel["status"] = "rejeitado"
        f.bloqueios.append({"codigo": "exportacao_recusada", "motivo": str(e)[:300]})
        return
    rel["exportacao"] = {"arquivo": exp["arquivo"], "sha256": exp["sha256"], "bytes": exp["bytes"], "exportId": exp["exportId"]}
    f.etapa("exportacao_b", "ok", **rel["exportacao"])

    # 3. receptor 1.1 -----------------------------------------------------------------------------------------------------
    receptor_out = saida / "receptor"
    if receptor_out.exists():
        shutil.rmtree(receptor_out)
    resumo = processar_v11(lote_raiz, receptor_out, agora)
    fichas = sorted((receptor_out / "fichas").glob("*.json"))
    if resumo["fichas"] != 1 or resumo["lotes"]["B"]["status"] != "ok" or len(fichas) != 1:
        f.etapa("receptor_1_1", "falhou", resumo={k: resumo[k] for k in ("fichas", "lotes")})
        rel["status"] = "rejeitado"
        f.bloqueios.append({"codigo": "receptor_recusou", "motivo": "o receptor 1.1 não aceitou o lote exportado"})
        return
    ficha = json.loads(fichas[0].read_text(encoding="utf-8"))
    f.etapa("receptor_1_1", "ok", fichasPorEstado=resumo["fichasPorEstado"], lote=resumo["lotes"]["B"]["status"])

    # 4. elegibilidade editorial + origem ---------------------------------------------------------------------------------
    if (ficha.get("fonte"), ficha["produto"]["provider"], ficha.get("origem")) != ("curadoria_manual", "CURADORIA", "B"):
        f.etapa("elegibilidade_editorial", "falhou", motivo="origem diferente de curadoria manual (B)")
        rel["status"] = "bloqueado"
        f.bloqueios.append({"codigo": "origem_inesperada", "motivo": "a ficha não vem da curadoria manual (fonte B)"})
        return
    if ficha["estado"] not in ESTADOS_ELEGIVEIS_B:
        f.etapa("elegibilidade_editorial", "falhou", estado=ficha["estado"])
        rel["status"] = "bloqueado"
        f.bloqueios.append({"codigo": "estado_inelegivel", "motivo": f"estado '{ficha['estado']}' inelegível para carrossel editorial"})
        return
    rel["ficha"] = {"estado": ficha["estado"], "origem": ficha["origem"], "fonte": ficha["fonte"], "provedor": ficha["produto"]["provider"],
                    "id": ficha["produto"]["id"], "titulo": ficha["produto"]["title"], "precoVerificado": ficha["preco"]["amountCents"] is not None,
                    "alegacaoComercialPermitida": ficha["alegacaoComercialPermitida"], "fatosParaUso": len(ficha["fatosParaUso"])}
    f.etapa("elegibilidade_editorial", "ok", estado=ficha["estado"])

    if aprovar and not rel["fixtureFicticia"]:                          # a opção só vale para a fixture reconhecida (antes de criar o catálogo)
        rel["status"] = "aprovacao_de_teste_recusada"
        f.bloqueios.append({"codigo": "aprovacao_de_teste_recusada",
                            "motivo": "--aprovar-fundo-ficticio só é aceito para a fixture fictícia reconhecida"})
        f.etapa("aprovacao_da_imagem", "recusada", motivo=f.bloqueios[-1]["motivo"])
        return

    # 5. fundo de marca no catálogo TEMPORÁRIO ----------------------------------------------------------------------------
    cat_raiz = saida / "catalogo_temporario"
    if cat_raiz.exists():
        shutil.rmtree(cat_raiz)
    catalogo = Catalogo(cat_raiz)                                            # nunca Catalogo() sem raiz: não toca o do repositório
    v2 = estilo == "v2"
    fid, _ = fundo_marca.registrar(catalogo, variante, agora=formatar(agora), marca=not v2)    # v2: fundo SEM logotipo embutido
    meta = catalogo.obter(fid)
    rel["fundo"] = {"id": fid, "provedor": meta["provedor"], "origem": meta["origem"], "variante": variante, "sha256": meta["sha256"],
                    "largura": meta["largura"], "altura": meta["altura"], "aprovacaoInicial": meta["aprovacao"]["status"]}
    f.etapa("fundo_de_marca", "ok", **{k: rel["fundo"][k] for k in ("id", "sha256", "aprovacaoInicial")})
    ids_v2 = None
    if v2:                                                              # ilustração da categoria + 2 fundos extras (todos composição gráfica, sem logo)
        categoria = estilo_v2.categoria_da_ficha(ficha)
        extras = [fundo_marca.registrar(catalogo, (variante + k) % 12, agora=formatar(agora), marca=False)[0] for k in (1, 2)]
        ilu, _ = ilustracoes.registrar_ilustracao(catalogo, categoria, variante % ilustracoes.VARIANTES, agora=formatar(agora))
        ids_v2 = {"ilustracao": ilu, "fundos": [fid, *extras]}
        rel["ilustracao"] = {"id": ilu, "categoria": ilustracoes.normalizar_categoria(categoria), "provedor": catalogo.obter(ilu)["provedor"],
                             "sha256": catalogo.obter(ilu)["sha256"], "aprovacaoInicial": catalogo.obter(ilu)["aprovacao"]["status"]}
        rel["fundosV2"] = ids_v2["fundos"]
        f.etapa("ilustracao_e_fundos_v2", "ok", categoria=rel["ilustracao"]["categoria"], fundos=len(ids_v2["fundos"]))

    # 6. aprovação da imagem -----------------------------------------------------------------------------------------------
    permitida, motivo = resolver_aprovacao(sha_ficha, aprovar, catalogo, fixture)
    if not permitida:
        pendente = not aprovar
        rel["status"] = "aprovacao_pendente" if pendente else "aprovacao_de_teste_recusada"
        rel["aprovacaoDaImagem"] = {"status": "pendente", "tipo": None, "motivo": motivo}
        f.bloqueios.append({"codigo": rel["status"], "motivo": motivo})
        f.etapa("aprovacao_da_imagem", "pendente" if pendente else "recusada", motivo=motivo)
        return
    for imagem in ([fid] if not v2 else [*ids_v2["fundos"], ids_v2["ilustracao"]]):
        catalogo.definir_aprovacao(imagem, "aprovada", APROVADOR_TESTE,
                                   "aprovação AUTOMÁTICA de teste da fixture fictícia; não é homologação humana")
    catalogo.salvar()
    rel["aprovacaoDaImagem"] = {"status": "aprovada", "tipo": "teste_ficticio", "valorDeHomologacaoHumana": False, "por": APROVADOR_TESTE,
                                "motivo": motivo}
    f.avisos.append("imagem aprovada por aprovação de TESTE da fixture fictícia (sem valor de homologação humana)")
    f.etapa("aprovacao_da_imagem", "aprovada_de_teste", valorDeHomologacaoHumana=False)

    # 7. ficha -> carrossel -------------------------------------------------------------------------------------------------
    ponte = ficha_para_carrossel_v11(ficha, t_publicacao=agora, foto_catalogo_id=ids_v2["ilustracao"] if v2 else fid, recurso_visual="composicao_grafica",
                                     catalogo=catalogo.fotos, links_oficiais=links)
    f.avisos += ponte["avisos"]
    rel["ponte"] = {"status": ponte["status"], "classeVisual": ponte["classe_visual"], "legenda": ponte["legenda_sugerida"],
                    "alegacoesOmitidas": ponte["alegacoes_omitidas"], "revisaoHumanaObrigatoria": ponte["revisao_humana_obrigatoria"]}
    if ponte["status"] != "rascunho":
        rel["status"] = "bloqueado"
        f.bloqueios += ponte["bloqueios"]
        f.etapa("ficha_para_carrossel", "bloqueada", bloqueios=[b["codigo"] for b in ponte["bloqueios"]])
        return
    config = ponte["carrossel"]
    if v2:
        montagem = estilo_v2.montar_slides(ficha, config, ids_v2, links)
        f.avisos += montagem.avisos
        rel["slidesDescartados"] = montagem.descartes
        if montagem.bloqueios:
            rel["status"] = "bloqueado"
            f.bloqueios += montagem.bloqueios
            f.etapa("ficha_para_carrossel", "bloqueada", bloqueios=[b["codigo"] for b in montagem.bloqueios], slides=len(montagem.slides))
            return
        config = {**config, "slides": montagem.slides}
    elif not links:                                                           # sem links oficiais: CTA textual, sem URL e sem promessa de link
        ult = config["slides"][-1]
        if ult.get("texto") == TEXTO_CTA_PADRAO_DA_PONTE:
            ult["texto"] = CTA_SEM_LINKS
    n = len(config["slides"])
    if not MIN_SLIDES <= n <= MAX_SLIDES:
        rel["status"] = "bloqueado"
        f.bloqueios.append({"codigo": "numero_de_slides", "motivo": f"{n} slides; o fluxo exige de {MIN_SLIDES} a {MAX_SLIDES}"})
        f.etapa("ficha_para_carrossel", "bloqueada", slides=n)
        return
    rel["carrossel"] = config
    f.etapa("ficha_para_carrossel", "ok", slides=n, statusDaPonte=ponte["status"])

    # 8. renderização + 9. validação -----------------------------------------------------------------------------------------
    pasta_slides = saida / "slides"
    if pasta_slides.exists():
        shutil.rmtree(pasta_slides)
    manifesto = gerar(config, catalogo=catalogo, saida=pasta_slides)
    pasta_png = saida / "slides_png"
    if pasta_png.exists():
        shutil.rmtree(pasta_png)
    pasta_png.mkdir()
    itens = []
    for s in manifesto["slides"]:
        jpg = pasta_slides / s["arquivo"]
        png = pasta_png / (Path(s["arquivo"]).stem + ".png")
        with Image.open(jpg) as im:
            formato, dim = im.format, im.size
            im.convert("RGB").save(png, "PNG")                              # cópia PNG para a entrega visual (o JPEG nativo é preservado)
        with Image.open(png) as ip:
            dim_png = ip.size
        itens.append({"arquivo": s["arquivo"], "formato": formato, "largura": dim[0], "altura": dim[1], "sha256": _sha(jpg.read_bytes()),
                      "png": png.name, "pngLargura": dim_png[0], "pngAltura": dim_png[1], "pngSha256": _sha(png.read_bytes()),
                      "layout": s["layout"], "validacaoDoGerador": s["validacao"]})
    problemas = list(manifesto["problemas"])
    for it in itens:
        if (it["largura"], it["altura"]) != RESOLUCAO or it["formato"] != "JPEG":
            problemas.append(f"{it['arquivo']}: dimensões/formato fora do esperado")
    if v2 and not problemas:
        medidas, erros_v2 = _validar_v2(config, catalogo, pasta_slides, ids_v2)
        rel["validacaoV2"] = medidas
        problemas += erros_v2
    rel["slides"] = itens
    rel["statusDoGerador"] = manifesto["status"]
    if problemas or manifesto["status"] != "pronto":
        rel["status"] = "bloqueado"
        f.bloqueios += [{"codigo": "validacao_visual_do_gerador", "motivo": p} for p in problemas]
        f.etapa("renderizacao_e_validacao", "reprovada", problemas=problemas)
        return
    f.etapa("renderizacao_e_validacao", "ok", slides=len(itens), resolucao="1080x1350", statusDoGerador=manifesto["status"])
    _validar_conteudo(f, config, v2)
    if not f.bloqueios:
        folha = gerar_folha([pasta_png / it["png"] for it in itens], saida / "folha_de_contato.png")
        rel["arquivos"] = {"folha": folha, "slidesPng": [it["png"] for it in itens], "slidesJpeg": [it["arquivo"] for it in itens]}
        f.etapa("folha_de_contato", "ok", arquivo=folha["arquivo"], sha256=folha["sha256"])
    rel["status"] = "bloqueado" if f.bloqueios else "concluido"


COMERCIAL_PROIBIDO = ("R$", "%", "estoque", "desconto", "promoç", "frete", "últimas unidades", "corra", "só hoje", "menor preço", "oferta")


def _validar_v2(config: dict, catalogo: Catalogo, pasta: Path, ids: dict) -> tuple[list[dict], list[str]]:
    """Validação B2R de cada slide exportado (fontes, margem, contraste medido, logotipo, rótulo, áreas) + diversidade do carrossel."""
    slides, total, medidas, erros = config["slides"], len(config["slides"]), [], []
    for i, s in enumerate(slides, 1):
        with Image.open(catalogo.caminho(s["foto"])) as foto:
            _, areas = LAYOUTS[s["layout"]](foto.copy(), s, i, total)
            with sem_texto():
                fundo, _ = LAYOUTS[s["layout"]](foto.copy(), s, i, total)
        r = validar_slide_v2(pasta / f"slide_{i:02d}.jpg", areas, fundo_sem_texto=fundo.convert("RGB"))
        medidas.append({"slide": i, **r["medidas"], "ok": r["ok"]})
        erros += [f"slide {i}: {e}" for e in r["erros"]]
    erros += [f"carrossel: {e}" for e in estilo_v2.verificar_variedade(slides, {})]
    return medidas, erros


def _validar_conteudo(f: _Fluxo, config: dict, v2: bool = False) -> None:
    """Etapa 9 (conteúdo): nenhum slide pode conter informação comercial; rótulo da arte ilustrativa obrigatório; sem URL inventada."""
    textos = " | ".join(" ".join(str(s.get(k, "")) for k in ("titulo", "destaque", "texto")) for s in config["slides"])
    baixo = textos.lower().replace("suzuki ofertas", "").replace("suzukiofertas", "")     # o nome da marca não é alegação comercial
    achados = [p for p in COMERCIAL_PROIBIDO if p.lower() in baixo] if not v2 else (
        [m.group(0) for m in [estilo_v2.TERMOS_PROIBIDOS.search(textos)] if m])    # v2: o CTA cita "ofertas" (nome da marca/assunto), sem alegação
    if achados:
        f.bloqueios.append({"codigo": "conteudo_comercial_nos_slides", "motivo": "termos comerciais encontrados: " + ", ".join(achados)})
    if not v2 and "Arte ilustrativa" not in textos:
        f.bloqueios.append({"codigo": "rotulo_ausente", "motivo": "rótulo \"Arte ilustrativa\" ausente"})
    if "http" in baixo:
        f.bloqueios.append({"codigo": "url_nos_slides", "motivo": "URL encontrada no texto dos slides"})
    f.etapa("validacao_de_conteudo", "ok" if not f.bloqueios else "reprovada", termosComerciais=achados)


def _finalizar(f: _Fluxo) -> None:
    """Etapa 10: relatórios JSON e Markdown (a folha de contato é acrescentada pelo módulo ``folha``, quando presente)."""
    rel = f.rel
    rel.setdefault("status", "rejeitado")
    rel["arquivos"] = rel.get("arquivos", {})
    (f.saida / "relatorio_b2.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (f.saida / "relatorio_b2.md").write_text(_markdown(rel), encoding="utf-8")
    if rel.get("estilo") == "v2" and rel.get("validacaoV2"):
        (f.saida / "relatorio_visual.md").write_text(_markdown_visual(rel), encoding="utf-8")


def _markdown_visual(rel: dict) -> str:
    """Relatório visual do estilo v2: medições AUTOMÁTICAS por slide. Não substitui o julgamento visual humano."""
    L = ["# Relatório visual — estilo editorial v2 (B2R)", "", "> RASCUNHO FICTÍCIO — NÃO PUBLICAR. As medidas abaixo são verificações automáticas; "
         "a aprovação visual definitiva é humana.", "", f"- Ficha: `{rel.get('fixture', {}).get('id', '?')}` · status `{rel['status']}` · estilo `{rel['estilo']}`"]
    if "ilustracao" in rel:
        il = rel["ilustracao"]
        L.append(f"- Ilustração: categoria `{il['categoria']}` · `{il['id']}` · provedor `{il['provedor']}` · aprovação inicial `{il['aprovacaoInicial']}`")
    L += ["", "| Slide | Layout | Fontes mín. (px) | Contraste mín. | Maior área decorativa | Logo (px) |", "|---|---|---|---|---|---|"]
    for m in rel["validacaoV2"]:
        fm = ", ".join(f"{k} {v}" for k, v in m["fontes_min_px"].items())
        L.append(f"| {m['slide']} | {m['layout']} | {fm} | {m['contraste_min']:.2f}:1 | {m['maior_area_decorativa']:.0%} | {m['logo_px'][0]}×{m['logo_px'][1]} |")
    if rel.get("slidesDescartados"):
        L += ["", "## Slides descartados"] + [f"- {d['slide']}: {d['texto']} — {d['motivo']}" for d in rel["slidesDescartados"]]
    L += ["", "Critérios automáticos: fontes mínimas (título 72, texto 44, rótulo 36, contador 36), margem de segurança 72 px, contraste ≥ 4,5:1 medido, "
          "logotipo de 160 px inteiro, rótulo \"Arte ilustrativa\", sem truncamento, área decorativa contígua ≤ 25 %.", ""]
    return "\n".join(L)


def _markdown(rel: dict) -> str:
    L = ["# Relatório B2 — carrossel fictício", "", "> RASCUNHO FICTÍCIO — NÃO PUBLICAR. Produtos fictícios; nada foi publicado nem agendado.", "",
         f"- **Status:** `{rel['status']}`", f"- **Gerado em:** {rel['geradoEm']}",
         f"- **Fixture fictícia reconhecida:** {'sim' if rel.get('fixtureFicticia') else 'não'}"]
    if "ficha" in rel:
        fi = rel["ficha"]
        L += ["", "## Ficha", f"- `{fi['provedor']}/{fi['id']}` — estado `{fi['estado']}`, origem {fi['origem']} (`{fi['fonte']}`)",
              f"- Preço verificado: {'sim' if fi['precoVerificado'] else 'não (sem preço verificado)'}; alegação comercial permitida: `{fi['alegacaoComercialPermitida']}`"]
    if "aprovacaoDaImagem" in rel:
        a = rel["aprovacaoDaImagem"]
        L += ["", "## Aprovação da imagem", f"- Status: `{a['status']}`" + (f" · tipo: `{a['tipo']}` · valor de homologação humana: **não**" if a.get("tipo") else ""),
              f"- {a['motivo']}"]
    if rel.get("slides"):
        L += ["", "## Slides"]
        L += [f"- `{s['arquivo']}` ({s['layout']}) {s['largura']}×{s['altura']} {s['formato']} · sha256 `{s['sha256'][:16]}…` · PNG `{s['png']}` · gerador: {s['validacaoDoGerador']}" for s in rel["slides"]]
    if rel.get("arquivos", {}).get("folha"):
        fo = rel["arquivos"]["folha"]
        L += ["", "## Folha de contato", f"- `{fo['arquivo']}` {fo['largura']}×{fo['altura']} {fo['formato']} · sha256 `{fo['sha256'][:16]}…`"]
    L += ["", "## Etapas"] + [f"{e['n']}. {e['etapa']} — **{e['status']}**" for e in rel.get("etapas", [])]
    if rel.get("bloqueios"):
        L += ["", "## Bloqueios"] + [f"- `{b['codigo']}`: {b['motivo']}" for b in rel["bloqueios"]]
    if rel.get("avisos"):
        L += ["", "## Avisos"] + [f"- {a}" for a in rel["avisos"]]
    r = rel["restricoes"]
    L += ["", "## Restrições", f"- PRODUTOS_REAIS_HABILITADO = {r['produtosReaisHabilitado']} · DADOS_REAIS_HABILITADO = {r['dadosReaisHabilitado']}",
          f"- Rede: {r['rede']} · publicação: {r['publicacao']} · agendamento: {r['agendamento']} · catálogo persistente tocado: {r['catalogoPersistenteTocado']}", ""]
    return "\n".join(L)
