"""Orquestrador B2: fluxo ponta a ponta fictício, aprovação, bloqueios, relatórios, folha de contato, determinismo e ausência de rede."""
import contextlib
import copy
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from orquestrador_b2 import __main__ as cli
from orquestrador_b2 import fluxo, folha
from orquestrador_b2.fluxo import ErroFluxo, executar, resolver_aprovacao
from gerador import fundo_marca
from gerador.catalogo import Catalogo
from produtos.selecao_contrato import DADOS_REAIS_HABILITADO
from produtos.tests.base import AGORA, Base
from produtos.tests.base_v11 import gravar_lote, produto_b
from curadoria_b.ficha import PRODUTOS_REAIS_HABILITADO

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "curadoria_b" / "exemplos_ficticios" / "ficha_valida.json"
CATALOGO_REPO = RAIZ / "photos" / "catalogo.json"
LINKS = {"whatsapp": "https://wa.me/5511999999999", "telegram": "https://t.me/suzukiofertas_ficticio"}
COMERCIAL = re.compile(r"R\$|%|estoque|urgen|desconto|promo|frete|\boferta\b|menor pre|\boff\b", re.I)
DEL = object()


def ficha(**over):
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for k, v in over.items():
        partes = k.split("__")
        alvo = d
        for p in partes[:-1]:
            alvo = alvo[int(p)] if isinstance(alvo, list) else alvo[p]
        if v is DEL:
            alvo.pop(partes[-1], None)
        else:
            alvo[partes[-1]] = v
    return d


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def estado_do_repo():
    return (sha(CATALOGO_REPO), sorted(p.name for p in (RAIZ / "photos").iterdir()))


class Cache(unittest.TestCase):
    """Executa o fluxo completo UMA vez por classe (a renderização leva alguns segundos)."""
    ARGS: dict = {"aprovar_fundo_ficticio": True}

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="b2test_"))
        cls.saida = cls.tmp / "saida"
        cls.rel = executar(FIXTURE, cls.saida, AGORA, **cls.ARGS)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class FluxoCompletoTest(Cache):
    def test_status_e_etapas(self):
        self.assertEqual(self.rel["status"], "concluido", self.rel["bloqueios"])
        nomes = [e["etapa"] for e in self.rel["etapas"]]
        self.assertEqual(nomes, ["ficha", "exportacao_b", "receptor_1_1", "elegibilidade_editorial", "fundo_de_marca",
                                 "aprovacao_da_imagem", "ficha_para_carrossel", "renderizacao_e_validacao", "validacao_de_conteudo",
                                 "folha_de_contato"])
        self.assertTrue(all(e["status"] in ("ok", "aprovada_de_teste") for e in self.rel["etapas"]))
        self.assertEqual(self.rel["bloqueios"], [])

    def test_ficha_permanece_editorial_elegivel(self):
        f = self.rel["ficha"]
        self.assertEqual((f["estado"], f["origem"], f["fonte"], f["provedor"]), ("candidato_nao_verificado", "B", "curadoria_manual", "CURADORIA"))
        self.assertEqual((f["precoVerificado"], f["alegacaoComercialPermitida"]), (False, False))

    def test_entre_3_e_5_slides_na_resolucao_correta(self):
        slides = self.rel["slides"]
        self.assertTrue(3 <= len(slides) <= 5)
        self.assertEqual(len(slides), len(self.rel["carrossel"]["slides"]))
        for s in slides:
            with Image.open(self.saida / "slides" / s["arquivo"]) as im:
                self.assertEqual((im.size, im.format, im.mode), ((1080, 1350), "JPEG", "RGB"))
            with Image.open(self.saida / "slides_png" / s["png"]) as im:
                self.assertEqual((im.size, im.format), ((1080, 1350), "PNG"))
            self.assertEqual((s["largura"], s["altura"], s["formato"]), (1080, 1350, "JPEG"))
            self.assertEqual(s["validacaoDoGerador"], "ok")
        self.assertEqual(self.rel["statusDoGerador"], "pronto")

    def test_estrutura_do_carrossel(self):
        sl = self.rel["carrossel"]["slides"]
        self.assertEqual(sl[0]["layout"], "foto_topo")
        self.assertIn("Arte ilustrativa", sl[0]["texto"])
        self.assertEqual([s["titulo"] for s in sl[1:-1]], ["CARACTERÍSTICA"] * (len(sl) - 2))
        self.assertEqual((sl[-1]["titulo"], sl[-1]["destaque"]), ("CHAME NO", "WHATSAPP E TELEGRAM"))
        self.assertEqual(sl[-1]["texto"], fluxo.CTA_SEM_LINKS)
        self.assertNotIn("http", json.dumps(self.rel["carrossel"]))

    def test_sem_conteudo_comercial_nos_slides_e_na_legenda(self):
        textos = " ".join(f"{s.get('titulo', '')} {s.get('destaque', '')} {s.get('texto', '')}" for s in self.rel["carrossel"]["slides"])
        sem_marca = textos.replace("Suzuki Ofertas", "")
        self.assertIsNone(COMERCIAL.search(sem_marca), sem_marca)
        self.assertIsNone(COMERCIAL.search(self.rel["ponte"]["legenda"].replace("Suzuki Ofertas", "")))
        self.assertEqual(self.rel["ponte"]["alegacoesOmitidas"], [])

    def test_folha_de_contato(self):
        fo = self.rel["arquivos"]["folha"]
        arq = self.saida / "folha_de_contato.png"
        with Image.open(arq) as im:
            self.assertEqual((im.format, im.size), ("PNG", (fo["largura"], fo["altura"])))
        self.assertEqual((fo["sha256"], fo["slides"]), (sha(arq), len(self.rel["slides"])))
        self.assertGreater(fo["largura"], 1080 // 2)

    def test_arquivos_de_saida(self):
        for nome in ("relatorio_b2.json", "relatorio_b2.md", "folha_de_contato.png"):
            self.assertTrue((self.saida / nome).is_file(), nome)
        self.assertEqual(sorted(p.name for p in (self.saida / "slides").glob("slide_*.jpg")), self.rel["arquivos"]["slidesJpeg"])
        self.assertEqual(sorted(p.name for p in (self.saida / "slides_png").glob("slide_*.png")), self.rel["arquivos"]["slidesPng"])

    def test_aprovacao_de_teste_registrada_sem_valor_de_homologacao(self):
        a = self.rel["aprovacaoDaImagem"]
        self.assertEqual((a["status"], a["tipo"], a["valorDeHomologacaoHumana"]), ("aprovada", "teste_ficticio", False))
        self.assertIn("TESTE", a["por"])
        self.assertTrue(any("aprovação de TESTE" in x for x in self.rel["avisos"]))
        md = (self.saida / "relatorio_b2.md").read_text(encoding="utf-8")
        self.assertIn("valor de homologação humana: **não**", md)
        cat = Catalogo(self.saida / "catalogo_temporario")
        self.assertEqual(cat.obter("cg-0001")["aprovacao"]["status"], "aprovada")
        self.assertIn("TESTE", cat.obter("cg-0001")["aprovacao"]["por"])

    def test_relatorios_completos_e_consistentes_com_os_arquivos(self):
        r = json.loads((self.saida / "relatorio_b2.json").read_text(encoding="utf-8"))
        for chave in ("fluxo", "versao", "geradoEm", "status", "fixtureFicticia", "fichaSha256", "exportacao", "ficha", "fundo",
                      "aprovacaoDaImagem", "ponte", "carrossel", "slides", "statusDoGerador", "arquivos", "etapas", "avisos", "bloqueios",
                      "restricoes"):
            self.assertIn(chave, r, chave)
        self.assertEqual(r["fichaSha256"], sha(FIXTURE))
        for s in r["slides"]:
            self.assertEqual(s["sha256"], sha(self.saida / "slides" / s["arquivo"]))
            self.assertEqual(s["pngSha256"], sha(self.saida / "slides_png" / s["png"]))
        self.assertEqual(r["fundo"]["sha256"], fundo_marca.sha256_fundo(0))
        self.assertEqual(r["exportacao"]["sha256"], sha(next((self.saida / "lote_curadoria" / "B").glob("produto_*.json"))))
        self.assertNotIn(str(self.tmp), json.dumps(r), "o relatório não deve conter caminhos absolutos")
        md = (self.saida / "relatorio_b2.md").read_text(encoding="utf-8")
        for trecho in ("RASCUNHO FICTÍCIO — NÃO PUBLICAR", "## Slides", "## Etapas", "## Folha de contato", "## Restrições", "## Avisos"):
            self.assertIn(trecho, md)

    def test_restricoes_registradas(self):
        r = self.rel["restricoes"]
        self.assertEqual((r["produtosReaisHabilitado"], r["dadosReaisHabilitado"], r["rede"], r["publicacao"], r["agendamento"]),
                         (False, False, "nao_utilizada", "nao_realizada", "nao_realizado"))
        self.assertIs(PRODUTOS_REAIS_HABILITADO, False)
        self.assertIs(DADOS_REAIS_HABILITADO, False)

    def test_catalogo_persistente_intacto_e_catalogo_temporario_na_saida(self):
        self.assertTrue((self.saida / "catalogo_temporario" / "photos" / "catalogo.json").is_file())
        self.assertNotIn("cg-0001", CATALOGO_REPO.read_text(encoding="utf-8"))


class ValidacaoDeConteudoTest(unittest.TestCase):
    def validar(self, slides):
        f = fluxo._Fluxo(Path("."), AGORA)
        fluxo._validar_conteudo(f, {"slides": slides})
        return [b["codigo"] for b in f.bloqueios]

    def test_rede_de_seguranca_bloqueia_conteudo_comercial_url_e_rotulo_ausente(self):
        limpo = [{"titulo": "PANELA", "texto": "Loja · Arte ilustrativa"}]
        self.assertEqual(self.validar(limpo), [])
        for txt in ("30% OFF", "R$ 99", "em estoque", "Frete grátis", "menor preço", "corra", "oferta"):
            self.assertIn("conteudo_comercial_nos_slides", self.validar([{"titulo": txt, "texto": "Arte ilustrativa"}]), txt)
        self.assertIn("url_nos_slides", self.validar([{"titulo": "X", "texto": "Arte ilustrativa https://x.example"}]))
        self.assertIn("rotulo_ausente", self.validar([{"titulo": "X", "texto": "sem rótulo"}]))
        self.assertEqual(self.validar([{"titulo": "CANAIS DO SUZUKI OFERTAS", "texto": "Arte ilustrativa"}]), [])   # nome da marca é permitido


class FolhaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def slides(self, n):
        out = []
        for i in range(n):
            p = self.tmp / f"s{i}.png"
            Image.new("RGB", (1080, 1350), (10 * i, 60, 140)).save(p)
            out.append(p)
        return out

    def test_texto_de_rascunho_e_numeracao_aparecem(self):
        chamados = []
        original = folha._texto
        with mock.patch.object(folha, "_texto", lambda d, xy, t, *a, **k: (chamados.append(t), original(d, xy, t, *a, **k))[1]):
            folha.gerar_folha(self.slides(5), self.tmp / "f.png")
        self.assertEqual(folha.TEXTO_RASCUNHO, "RASCUNHO FICTÍCIO — NÃO PUBLICAR")
        self.assertGreaterEqual(chamados.count(folha.TEXTO_RASCUNHO), 2)
        for i in range(1, 6):
            self.assertIn(str(i), chamados)
            self.assertIn(f"Slide {i} de 5", chamados)

    def test_dimensoes_por_quantidade_e_determinismo(self):
        for n, cols in ((3, 3), (4, 4), (5, 3)):
            r = folha.gerar_folha(self.slides(n), self.tmp / f"f{n}.png")
            self.assertEqual((r["colunas"], r["slides"], r["formato"]), (cols, n, "PNG"))
            with Image.open(self.tmp / f"f{n}.png") as im:
                self.assertEqual(im.size, (r["largura"], r["altura"]))
        a = folha.gerar_folha(self.slides(4), self.tmp / "a.png")
        b = folha.gerar_folha(self.slides(4), self.tmp / "b.png")
        self.assertEqual(a["sha256"], b["sha256"])

    def test_faixa_de_aviso_vermelha_no_topo(self):
        folha.gerar_folha(self.slides(3), self.tmp / "f.png")
        with Image.open(self.tmp / "f.png") as im:
            self.assertEqual(im.getpixel((5, 5)), (246, 2, 19))

    def test_sem_slides_e_erro(self):
        with self.assertRaises(ValueError):
            folha.gerar_folha([], self.tmp / "f.png")


class AprovacaoTest(Base):
    def setUp(self):
        super().setUp()
        self.saida = self.tmp / "saida"

    def test_sem_a_opcao_o_fluxo_para_com_aprovacao_pendente(self):
        antes = estado_do_repo()
        rel = executar(FIXTURE, self.saida, AGORA)
        self.assertEqual(rel["status"], "aprovacao_pendente")
        self.assertEqual(rel["aprovacaoDaImagem"]["status"], "pendente")
        self.assertEqual(rel["bloqueios"][0]["codigo"], "aprovacao_pendente")
        self.assertNotIn("slides", rel)
        self.assertFalse((self.saida / "slides").exists() or (self.saida / "folha_de_contato.png").exists())
        self.assertTrue((self.saida / "relatorio_b2.json").is_file() and (self.saida / "relatorio_b2.md").is_file())
        cat = Catalogo(self.saida / "catalogo_temporario")
        self.assertEqual(cat.obter("cg-0001")["aprovacao"]["status"], "pendente")
        self.assertIn("pendente", (self.saida / "relatorio_b2.md").read_text(encoding="utf-8"))
        self.assertEqual(estado_do_repo(), antes)

    def test_opcao_so_vale_para_a_fixture_reconhecida(self):
        outra = self.tmp / "outra.json"
        outra.write_text(json.dumps(ficha(title="Outra Panela Fictícia 6 Litros")), encoding="utf-8")
        rel = executar(outra, self.saida, AGORA, aprovar_fundo_ficticio=True)
        self.assertEqual(rel["status"], "aprovacao_de_teste_recusada")
        self.assertFalse(rel["fixtureFicticia"])
        self.assertFalse((self.saida / "slides").exists())
        self.assertFalse((self.saida / "catalogo_temporario").exists(), "nem o catálogo é criado quando a opção é recusada")
        rel2 = executar(outra, self.tmp / "s2", AGORA)                        # sem a opção, uma ficha válida também fica pendente
        self.assertEqual(rel2["status"], "aprovacao_pendente")
        self.assertEqual(Catalogo(self.tmp / "s2" / "catalogo_temporario").obter("cg-0001")["aprovacao"]["status"], "pendente")

    def test_resolver_aprovacao_exige_opcao_fixture_e_catalogo_temporario(self):
        sha_ok = next(iter(fluxo.FIXTURES_FICTICIAS))
        self.assertEqual(sha_ok, sha(FIXTURE))
        temp = Catalogo(self.tmp / "cat")
        self.assertEqual(resolver_aprovacao(sha_ok, True, temp)[0], True)
        self.assertEqual(resolver_aprovacao(sha_ok, False, temp)[0], False)
        self.assertEqual(resolver_aprovacao("0" * 64, True, temp)[0], False)
        self.assertEqual(resolver_aprovacao(sha_ok, True, Catalogo(RAIZ))[0], False)           # catálogo do repositório: nunca
        self.assertEqual(resolver_aprovacao(sha_ok, True, Catalogo(RAIZ / "photos"))[0], False)

    def test_nunca_aprova_fotografia_real_nem_catalogo_persistente(self):
        antes = estado_do_repo()
        with mock.patch.object(Catalogo, "definir_aprovacao", autospec=True) as d:
            executar(FIXTURE, self.saida, AGORA, aprovar_fundo_ficticio=True)
        raizes = {str(Path(c.args[0].raiz).resolve()) for c in d.call_args_list}
        self.assertEqual(raizes, {str((self.saida / "catalogo_temporario").resolve())})
        self.assertEqual(estado_do_repo(), antes)

    def test_catalogo_nunca_e_criado_sem_raiz(self):
        chamadas = []
        original = fluxo.Catalogo

        def espiao(*a, **k):
            chamadas.append((a, k))
            assert a or k, "Catalogo() sem raiz aponta para o catálogo do repositório"
            return original(*a, **k)
        with mock.patch.object(fluxo, "Catalogo", espiao):
            executar(FIXTURE, self.saida, AGORA)
        self.assertTrue(chamadas)


class RejeicoesTest(Base):
    def setUp(self):
        super().setUp()
        self.saida = self.tmp / "saida"

    def rodar(self, obj, **kw):
        p = self.tmp / "f.json"
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return executar(p, self.saida, AGORA, **kw)

    def assert_rejeitada(self, obj, trecho=None):
        rel = self.rodar(obj, aprovar_fundo_ficticio=True)
        self.assertEqual(rel["status"], "rejeitado", rel["bloqueios"])
        self.assertNotIn("slides", rel)
        self.assertFalse((self.saida / "slides").exists())
        self.assertFalse((self.saida / "lote_curadoria" / "B").exists())
        self.assertTrue((self.saida / "relatorio_b2.json").is_file())
        if trecho:
            self.assertIn(trecho, json.dumps(rel["bloqueios"], ensure_ascii=False))
        return rel

    def test_produto_real_e_rejeitado(self):
        self.assert_rejeitada(ficha(officialUrl="https://www.amazon.com.br/produto/1"), "produtos reais estão desabilitados")
        self.assert_rejeitada(ficha(fatos__0__sourceRef="https://www.fabricante.com.br/manual"), "sourceRef")
        self.assert_rejeitada(ficha(referencias__0__url="https://www.magazineluiza.com.br/p"), "referencias[0].url")

    def test_origem_falsa_e_rejeitada(self):
        for campo, valor in (("source", {"kind": "agente_publicada", "system": "SuzukiOfertas-AgenteAutomatico"}),
                             ("provider", "AMAZON"), ("kind", "agente_publicada"), ("system", "SuzukiOfertas-AgenteAutomatico")):
            self.assert_rejeitada(ficha(**{campo: valor}), "campo desconhecido")
        self.assert_rejeitada(ficha(fichaCuradoriaVersion="2.0"))

    def test_lote_com_origem_de_agente_e_bloqueado_depois_do_receptor(self):
        def exportar_falso(ficha_arquivo, saida, agora, *, export_id=None):
            gravar_lote(Path(saida) / "B", {"b.json": produto_b(4, "B001")})
            return {"arquivo": "b.json", "sha256": "0" * 64, "bytes": 1, "exportId": export_id}
        with mock.patch.object(fluxo, "exportar", exportar_falso):
            rel = executar(FIXTURE, self.saida, AGORA, aprovar_fundo_ficticio=True)
        self.assertEqual(rel["status"], "bloqueado")
        self.assertEqual(rel["bloqueios"][0]["codigo"], "origem_inesperada")
        self.assertFalse((self.saida / "slides").exists())

    def test_urls_invalidas_sao_rejeitadas(self):
        ruins = ["http://www.lojaficticia.example/p", "https://bit.ly/abc", "https://u:s@www.lojaficticia.example/p",
                 "https://www.lojaficticia.example:8443/p", "https://203.0.113.9/p", "https://localhost/p",
                 "https://www.lojaficticia.example/p?utm_source=x", "https://", "javascript:alert(1)"]
        for url in ruins:
            for campo in ("officialUrl", "fatos__0__sourceRef", "referencias__0__url"):
                self.setUp()
                self.assert_rejeitada(ficha(**{campo: url}))

    def test_alegacoes_comerciais_e_campos_de_preco_sao_rejeitados(self):
        for t in ("Panela em promoção", "Panela com frete grátis", "Panela 30% OFF", "Menor preço do ano"):
            self.setUp()
            self.assert_rejeitada(ficha(title=t), "alegação comercial")
        self.setUp()
        self.assert_rejeitada(ficha(fatos__0__text="Em estoque agora"), "alegação comercial")
        for campo in ("price", "preco", "availability", "estoque", "affiliateUrl", "desconto", "frete"):
            self.setUp()
            self.assert_rejeitada(ficha(**{campo: 1}), "campo comercial proibido")

    def test_ficha_ilegivel_ou_json_invalido(self):
        self.assert_rejeitada("{truncado")
        self.setUp()
        rel = executar(self.tmp / "nao_existe.json", self.saida, AGORA)
        self.assertEqual(rel["status"], "rejeitado")

    def test_links_invalidos_bloqueiam_o_carrossel(self):
        for url in ("http://wa.me/1", "https://evil.example/1", "https://user:x@wa.me/1", "https://wa.me/1?x=1", "https://wa.me:8080/1"):
            self.setUp()
            rel = executar(FIXTURE, self.saida, AGORA, aprovar_fundo_ficticio=True, links_oficiais={"whatsapp": url})
            self.assertEqual(rel["status"], "bloqueado", url)
            self.assertEqual(rel["bloqueios"][0]["codigo"], "link_whatsapp_invalido")
            self.assertFalse((self.saida / "slides").exists())
        self.setUp()
        rel = executar(FIXTURE, self.saida, AGORA, aprovar_fundo_ficticio=True, links_oficiais={"telegram": "https://wa.me/1"})
        self.assertEqual(rel["bloqueios"][0]["codigo"], "link_telegram_invalido")

    def test_saida_dentro_do_repositorio_e_recusada(self):
        for destino in (RAIZ / "saida_b2_teste", RAIZ / "photos" / "x", RAIZ):
            with self.assertRaises(ErroFluxo):
                executar(FIXTURE, destino, AGORA)
        self.assertFalse((RAIZ / "saida_b2_teste").exists())


class LinksOficiaisTest(Cache):
    ARGS = {"aprovar_fundo_ficticio": True, "links_oficiais": LINKS}

    def test_links_validos_fornecidos_entram_no_cta_e_na_legenda(self):
        self.assertEqual(self.rel["status"], "concluido", self.rel["bloqueios"])
        ult = self.rel["carrossel"]["slides"][-1]
        self.assertIn("wa.me/5511999999999", ult["texto"])
        self.assertIn("t.me/suzukiofertas_ficticio", ult["texto"])
        self.assertIn("https://wa.me/5511999999999", self.rel["ponte"]["legenda"])
        self.assertEqual(self.rel["slides"][-1]["validacaoDoGerador"], "ok")


class NumeroDeSlidesTest(Base):
    def test_de_3_a_5_slides_renderizados_conforme_os_fatos(self):
        fato = ficha()["fatos"][0]
        for n_fatos, esperado in ((1, 3), (3, 5)):
            self.setUp()
            p = self.tmp / f"f{n_fatos}.json"
            p.write_text(json.dumps(ficha(fatos=[{**fato, "text": f"Característica fictícia tipo {chr(65 + i)}"} for i in range(n_fatos)]),
                                    ensure_ascii=False), encoding="utf-8")
            # só neste teste a ficha variante é reconhecida como fixture (patch do dicionário em memória; o código não muda)
            with mock.patch.dict(fluxo.FIXTURES_FICTICIAS, {sha(p): "teste"}):
                rel = executar(p, self.tmp / f"saida{n_fatos}", AGORA, aprovar_fundo_ficticio=True)
            self.assertEqual(rel["status"], "concluido", rel["bloqueios"])
            self.assertEqual(len(rel["slides"]), esperado)
            self.assertEqual(rel["arquivos"]["folha"]["slides"], esperado)
            for s in rel["slides"]:
                self.assertEqual((s["largura"], s["altura"], s["validacaoDoGerador"]), (1080, 1350, "ok"))

    def test_fixture_continua_sendo_a_unica_reconhecida_sem_patch(self):
        self.assertEqual(list(fluxo.FIXTURES_FICTICIAS), [sha(FIXTURE)])


class DeterminismoTest(unittest.TestCase):
    def test_mesmas_entradas_mesmas_saidas(self):
        tmp = Path(tempfile.mkdtemp(prefix="b2det_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        a = executar(FIXTURE, tmp / "a", AGORA, aprovar_fundo_ficticio=True)
        b = executar(FIXTURE, tmp / "b", AGORA, aprovar_fundo_ficticio=True)
        self.assertEqual(a["status"], b["status"])
        self.assertEqual([(s["sha256"], s["pngSha256"]) for s in a["slides"]], [(s["sha256"], s["pngSha256"]) for s in b["slides"]])
        self.assertEqual(a["arquivos"]["folha"]["sha256"], b["arquivos"]["folha"]["sha256"])
        self.assertEqual(a["exportacao"], b["exportacao"])
        self.assertEqual(a["fundo"], b["fundo"])
        self.assertEqual((tmp / "a" / "relatorio_b2.json").read_bytes(), (tmp / "b" / "relatorio_b2.json").read_bytes())
        self.assertEqual((tmp / "a" / "relatorio_b2.md").read_text(encoding="utf-8"), (tmp / "b" / "relatorio_b2.md").read_text(encoding="utf-8"))
        outro = executar(FIXTURE, tmp / "c", AGORA.replace(hour=16), aprovar_fundo_ficticio=True)
        self.assertNotEqual(outro["exportacao"]["exportId"], a["exportacao"]["exportId"])


class CliTest(Base):
    def rodar(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(list(args))
        return rc, out.getvalue(), err.getvalue()

    def test_codigos_de_saida(self):
        s = self.tmp / "s"
        rc, out, _ = self.rodar(str(FIXTURE), "--saida", str(s), "--agora", "2026-11-17T15:00:00Z")
        self.assertEqual((rc, json.loads(out)["status"]), (3, "aprovacao_pendente"))
        rc, out, _ = self.rodar(str(FIXTURE), "--saida", str(self.tmp / "s2"), "--agora", "2026-11-17T15:00:00Z", "--aprovar-fundo-ficticio")
        self.assertEqual((rc, json.loads(out)["slides"]), (0, 4))
        bad = self.tmp / "ruim.json"
        bad.write_text(json.dumps(ficha(price=1)))
        self.assertEqual(self.rodar(str(bad), "--saida", str(self.tmp / "s3"), "--agora", "2026-11-17T15:00:00Z")[0], 2)

    def test_usos_invalidos(self):
        self.assertEqual(self.rodar(str(FIXTURE), "--saida", str(self.tmp / "s"), "--agora", "ontem")[0], 2)
        rc, _, err = self.rodar(str(FIXTURE), "--saida", str(RAIZ / "saida_b2_cli"), "--agora", "2026-11-17T15:00:00Z")
        self.assertEqual(rc, 2)
        self.assertIn("FORA do repositório", err)
        self.assertFalse((RAIZ / "saida_b2_cli").exists())

    def test_cli_nao_tem_opcao_para_habilitar_produtos_ou_dados_reais(self):
        for flag in ("--reais", "--produtos-reais", "--dados-reais", "--habilitar", "--forcar"):
            with self.assertRaises(SystemExit) as c, contextlib.redirect_stderr(io.StringIO()):
                cli.main([str(FIXTURE), "--saida", str(self.tmp / "s"), flag])
            self.assertEqual(c.exception.code, 2, flag)

    def test_links_via_cli(self):
        rc, out, _ = self.rodar(str(FIXTURE), "--saida", str(self.tmp / "s"), "--agora", "2026-11-17T15:00:00Z", "--aprovar-fundo-ficticio",
                                "--whatsapp", "http://wa.me/1")
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(out)["bloqueios"], ["link_whatsapp_invalido"])


class SemRedeESemVersionamentoTest(Base):
    def test_fluxo_roda_com_a_rede_bloqueada(self):
        with self.assertRaises(AssertionError):
            import socket
            socket.create_connection(("exemplo.example", 443))
        rel = executar(FIXTURE, self.tmp / "s", AGORA, aprovar_fundo_ficticio=True)        # Base.setUp bloqueia qualquer conexão
        self.assertEqual(rel["status"], "concluido")

    def test_modulos_sem_rede_processos_ou_ambiente(self):
        for arq in (RAIZ / "orquestrador_b2").glob("*.py"):
            fonte = arq.read_text(encoding="utf-8")
            for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", fonte, re.M):
                alvo = (m.group(1) or m.group(2)).replace(" ", "")
                for mod in alvo.split(","):
                    for proibido in ("urllib", "http", "socket", "requests", "subprocess", "ssl", "ftplib", "smtplib", "webbrowser"):
                        self.assertFalse(mod == proibido or mod.startswith(proibido + "."), (arq.name, mod))
            for padrao in ("os.environ", "getenv", "urlopen", "Popen", "os.system"):
                self.assertNotIn(padrao, fonte, (arq.name, padrao))

    def test_nada_e_versionado_nem_alterado_no_repositorio(self):
        antes = subprocess.run(["git", "status", "--porcelain", "--", ":!orquestrador_b2"], cwd=RAIZ, capture_output=True, text=True).stdout
        repo_antes = estado_do_repo()
        executar(FIXTURE, self.tmp / "s", AGORA, aprovar_fundo_ficticio=True)
        depois = subprocess.run(["git", "status", "--porcelain", "--", ":!orquestrador_b2"], cwd=RAIZ, capture_output=True, text=True).stdout
        self.assertEqual((antes, estado_do_repo()), (depois, repo_antes))

    def test_o_fluxo_nao_altera_as_implementacoes_reutilizadas(self):
        fonte = (RAIZ / "orquestrador_b2" / "fluxo.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*(PRODUTOS|DADOS)_REAIS_HABILITADO\s*=", fonte, re.M))      # nenhuma atribuição das chaves de bloqueio
        for proibido in ("selecao_contrato.DADOS", "setattr(", "mock.patch"):
            self.assertNotIn(proibido, fonte, proibido)


if __name__ == "__main__":
    unittest.main()
