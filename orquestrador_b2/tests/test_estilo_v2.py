"""Estilo v2 (B2R): títulos derivados dos fatos, CTA neutro, fixtures por conteúdo, aprovação restrita, --estilo, entrega visual."""
import contextlib
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from orquestrador_b2 import __main__ as cli
from orquestrador_b2 import entrega, estilo_v2 as E
from orquestrador_b2.fluxo import ErroFluxo, FIXTURES_FICTICIAS, executar, resolver_aprovacao
from gerador.catalogo import Catalogo
from produtos.tempo import parse_data
from tests import b2r_referencia as ref

RAIZ = Path(__file__).resolve().parents[2]
EX = RAIZ / "orquestrador_b2" / "exemplos_ficticios"
LEGADA = RAIZ / "curadoria_b" / "exemplos_ficticios" / "ficha_valida.json"
AGORA = parse_data("2026-11-18T12:00:00Z")
PROIBIDOS = re.compile(r"R\$|%|\bOFF\b|estoque|últimas?\s+unidades?|comprovad|garantid|melhor\s+preço|menor\s+preço|imperd|link\s+na\s+bio|links?\s+na\s+legenda", re.I)
CATALOGO_REPO = RAIZ / "photos" / "catalogo.json"


class Textos(unittest.TestCase):
    def test_destaque_numerico_extraido_do_fato(self):
        casos = {"Capacidade de 5 litros": ("5", "L"), "Autonomia de até 20 horas": ("20", "h"), "Peso de 1,2 kg": ("1,2", "kg"),
                 "Bateria de 20 V": ("20", "V"), "Autonomia de até 4 h": ("4", "h")}
        for fato, (n, u) in casos.items():
            d = E.extrair_destaque(fato)
            self.assertEqual((d["numero"], d["unidade"]), (n, u), fato)
        self.assertIsNone(E.extrair_destaque("Corpo em alumínio"))

    def test_titulos_curtos_e_sem_alegacao(self):
        for fato in ("Capacidade de 5 litros", "Corpo em alumínio", "Tampa com trava de segurança", "Peso de 1,2 kg", "Conexão sem fio Bluetooth"):
            t = E.titulo_do_fato(fato)
            self.assertLessEqual(len(t), E.TITULO_MAX)
            self.assertEqual(E.avaliar_texto(t), [], t)
            self.assertNotRegex(t, PROIBIDOS)
        self.assertEqual(E.titulo_do_fato("Capacidade de 5 litros"), "CAPACIDADE")
        self.assertEqual(E.titulo_do_fato("de 5 litros"), E.TITULO_NEUTRO)

    def test_avaliar_texto_reprova_termos(self):
        for t in ("MELHOR PREÇO", "50% OFF", "ÚLTIMAS UNIDADES", "Comprovado", "Garantido", "Imperdível", "R$ 10", "Estoque limitado"):
            self.assertTrue(E.avaliar_texto(t), t)
        self.assertEqual(E.avaliar_texto("CURTIU ESSE ACHADO? SIGA O PERFIL!"), [])

    def test_cta_sem_links_neutro(self):
        t = E.cta_textos(None)
        self.assertEqual(t["titulo"], "CURTIU ESSE ACHADO? SIGA O PERFIL!")
        self.assertTrue(t["texto"].startswith("Descubra novos produtos e novidades no Suzuki Ofertas."))
        self.assertIn("WhatsApp", t["texto"])
        self.assertIn("Telegram", t["texto"])
        corpo = t["titulo"] + t["texto"]
        self.assertNotRegex(corpo, PROIBIDOS)
        self.assertNotIn("http", corpo)
        self.assertNotIn("destaque", t)

    def test_cta_com_links_mostra_os_links_sem_frases_proibidas(self):
        t = E.cta_textos({"whatsapp": "https://wa.me/5511999999999", "telegram": "https://t.me/canal_ficticio"})
        self.assertIn("wa.me/5511999999999", t["destaque"])
        self.assertNotRegex(t["titulo"] + t["texto"] + t["destaque"], PROIBIDOS)


class TitulosDaLista(unittest.TestCase):
    def test_titulos_derivados_dos_fatos_das_fixtures(self):
        casos = {"Conexão sem fio Bluetooth|Estojo de recarga incluso": "CONEXÃO E ESTOJO",
                 "Corpo em alumínio|Tampa com trava de segurança": "MATERIAL E TAMPA",
                 "Autonomia de até 4 h|Peso de 1,2 kg": "AUTONOMIA E PESO"}
        for fatos, esperado in casos.items():
            self.assertEqual(E.titulo_da_lista(fatos.split("|")), esperado)

    def test_derivacao_generica_com_fatos_novos(self):
        self.assertEqual(E.titulo_da_lista(["Display de 6 polegadas", "Memória de 128 GB"]), "DISPLAY E MEMÓRIA")
        self.assertEqual(E.titulo_da_lista(["Cabo de 2 metros", "Corpo em plástico", "Tampa removível"]), "CABO, MATERIAL E TAMPA")

    def test_sem_informacao_suficiente_usa_titulo_neutro(self):
        self.assertEqual(E.titulo_da_lista(["de 5 litros", "com o"]), E.TITULO_NEUTRO)
        self.assertEqual(E.titulo_da_lista(["Peso de 1 kg", "Peso de 2 kg"]), E.TITULO_NEUTRO)       # rótulos repetidos
        self.assertEqual(E.titulo_da_lista(["Capacitância extraordinária", "Reconfiguração automática"]), E.TITULO_NEUTRO)  # > 24 caracteres
        self.assertNotEqual(E.TITULO_NEUTRO, "NA PRÁTICA")

    def test_titulo_nao_inventa_caracteristica(self):
        fatos = ["Conexão sem fio Bluetooth", "Estojo de recarga incluso"]
        for palavra in E.titulo_da_lista(fatos).replace(",", "").split():
            self.assertTrue(palavra == "E" or palavra.lower() in " ".join(fatos).lower())


class Fixtures(unittest.TestCase):
    def test_tres_fixtures_batem_com_o_hash_canonico(self):
        achados = set()
        for arq in sorted(EX.glob("*.json")):
            obj = json.loads(arq.read_text(encoding="utf-8"))
            h = E.hash_canonico(obj)
            self.assertIn(h, E.FIXTURES_B2R, arq.name)
            self.assertEqual(E.FIXTURES_B2R[h]["arquivo"], arq.name)
            achados.add(h)
        self.assertEqual(achados, set(E.FIXTURES_B2R))
        self.assertEqual(len(achados), 3)

    def test_fixtures_so_com_dados_ficticios(self):
        for arq in EX.glob("*.json"):
            txt = arq.read_text(encoding="utf-8")
            self.assertIn("Fictíci", txt)
            self.assertIn(".example", txt)
            self.assertNotRegex(txt, PROIBIDOS)

    def test_reconhecimento_por_conteudo(self):
        obj = json.loads((EX / "ficha_tecnologia_fone.json").read_text(encoding="utf-8"))
        self.assertEqual(E.identificar_fixture("x", obj, FIXTURES_FICTICIAS)["id"], "C101")
        obj["title"] += " X"
        self.assertIsNone(E.identificar_fixture("x", obj, FIXTURES_FICTICIAS))
        self.assertEqual(E.identificar_fixture(next(iter(FIXTURES_FICTICIAS)), {}, FIXTURES_FICTICIAS)["estilo_padrao"], "v1")

    def test_aprovacao_restrita_ao_catalogo_temporario(self):
        with tempfile.TemporaryDirectory() as t:
            cat = Catalogo(Path(t) / "c")
            fx = E.identificar_fixture("x", json.loads((EX / "ficha_ferramentas_furadeira.json").read_text(encoding="utf-8")), {})
            self.assertTrue(resolver_aprovacao("x", True, cat, fx)[0])
            self.assertFalse(resolver_aprovacao("x", True, cat, None)[0])
            self.assertFalse(resolver_aprovacao("x", False, cat, fx)[0])
            self.assertFalse(resolver_aprovacao("x", True, Catalogo(RAIZ / "photos"), fx)[0])


# Capas e destaques numéricos aprovados visualmente: preservados byte a byte no ajuste final (mesma versão de Pillow/libjpeg).
CAPAS_E_DESTAQUES = {
    "tecnologia_fone/slide_01.jpg": "a4fe14cd70297093c35ab9445efda0880745143c18b63bd7ceea919eca0497ae",
    "tecnologia_fone/slide_02.jpg": "dc91df91ad76db3ab441e55d73e69016bba0a1a495fbcb025d6ec459889efa79",
    "casa_cozinha_panela/slide_01.jpg": "bcafc364e9b4adaff7e5a99077dc56a52bdeeda65b1c364165c8dae1337216d9",
    "casa_cozinha_panela/slide_02.jpg": "b9e9b03b575a631345dec173813b67fcbbd8dc8be569220abb59179be536a9cc",
    "ferramentas_furadeira/slide_01.jpg": "16803f6b40917e349e94f03153bbba4182da38b068832c97f0cbc0594720f27b",
    "ferramentas_furadeira/slide_02.jpg": "e67d72cbad9e5b47f2d199a05179cf1909c7446d9fbd9fb9b28013e058b93f52"
}


class Fluxo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="b2r_"))
        cls.antes = CATALOGO_REPO.read_bytes()
        cls.saida = cls.tmp / "ent"
        cls.out = entrega.entregar(cls.saida, AGORA)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_tres_carrosseis_concluidos_com_3_a_5_slides(self):
        self.assertEqual(len(self.out["carrosseis"]), 3)
        for r in self.out["carrosseis"]:
            self.assertEqual(r["status"], "concluido")
            self.assertTrue(3 <= r["slides"] <= 5)
            self.assertGreaterEqual(r["contrasteMin"], 4.5)

    def test_arquivos_da_entrega(self):
        for pasta in self.saida.iterdir():
            if not pasta.is_dir():
                continue
            for nome in ("folha_de_contato.png", "relatorio_visual.md", "relatorio_b2.json"):
                self.assertTrue((pasta / nome).exists(), f"{pasta.name}/{nome}")
            jpgs, pngs = sorted((pasta / "slides").glob("*.jpg")), sorted((pasta / "slides_png").glob("*.png"))
            self.assertEqual(len(jpgs), len(pngs))
            for j in jpgs:
                with Image.open(j) as im:
                    self.assertEqual((im.format, im.size), ("JPEG", (1080, 1350)))
        self.assertTrue((self.saida / "folha_geral.png").exists())
        self.assertTrue((self.saida / "relatorio_consolidado.md").exists())

    def test_relatorio_flags_e_estilo(self):
        for pasta in self.saida.iterdir():
            if pasta.is_dir():
                rel = json.loads((pasta / "relatorio_b2.json").read_text(encoding="utf-8"))
                self.assertEqual(rel["estilo"], "v2")
                self.assertTrue(rel["fixtureFicticia"])
                self.assertIs(rel["restricoes"]["produtosReaisHabilitado"], False)
                self.assertIs(rel["restricoes"]["dadosReaisHabilitado"], False)
                self.assertEqual(rel["restricoes"]["rede"], "nao_utilizada")
                self.assertFalse(rel["aprovacaoDaImagem"]["valorDeHomologacaoHumana"])
                self.assertEqual(rel["ilustracao"]["provedor"], "composicao-grafica")

    def test_sem_termos_proibidos_nos_slides_e_legenda(self):
        for pasta in self.saida.iterdir():
            if pasta.is_dir():
                rel = json.loads((pasta / "relatorio_b2.json").read_text(encoding="utf-8"))
                txt = " ".join(str(s.get(k, "")) for s in rel["carrossel"]["slides"] for k in ("titulo", "destaque", "texto"))
                self.assertNotRegex(txt, PROIBIDOS)
                self.assertNotRegex(rel["ponte"]["legenda"], re.compile(r"R\$|%|\bOFF\b|estoque|comprovad|garantid|imperd", re.I))

    def test_layouts_vizinhos_diferentes_e_fundos_nao_repetidos(self):
        for pasta in self.saida.iterdir():
            if pasta.is_dir():
                rel = json.loads((pasta / "relatorio_b2.json").read_text(encoding="utf-8"))
                sl = rel["carrossel"]["slides"]
                lay = [s["layout"] for s in sl]
                self.assertTrue(all(a != b for a, b in zip(lay, lay[1:])))
                self.assertEqual(lay[0], "ilustracao_capa")
                self.assertEqual(lay[-1], "cta_seguir")
                fotos = [s["foto"] for s in sl]
                self.assertTrue(all(fotos.count(f) <= 2 for f in fotos))

    def test_capas_e_destaques_preservados(self):
        for rel, h in CAPAS_E_DESTAQUES.items():
            self.assertEqual(hashlib.sha256((self.saida / rel.split("/")[0] / "slides" / rel.split("/")[1]).read_bytes()).hexdigest(), h, rel)

    def test_lista_e_cta_da_entrega(self):
        for pasta in self.saida.iterdir():
            if pasta.is_dir():
                rel = json.loads((pasta / "relatorio_b2.json").read_text(encoding="utf-8"))
                sl = {s["layout"]: s for s in rel["carrossel"]["slides"]}
                self.assertNotEqual(sl["lista_caracteristicas"]["titulo"], "NA PRÁTICA")
                self.assertEqual(sl["cta_seguir"]["titulo"], "CURTIU ESSE ACHADO? SIGA O PERFIL!")
                self.assertNotRegex(json.dumps(sl["cta_seguir"], ensure_ascii=False), re.compile(r"bio|legenda|http", re.I))

    def test_catalogo_do_repositorio_intacto(self):
        self.assertEqual(CATALOGO_REPO.read_bytes(), self.antes)

    def test_sem_aprovacao_para_na_pendencia(self):
        rel = executar(EX / "ficha_ferramentas_furadeira.json", self.tmp / "pend", AGORA)
        self.assertEqual(rel["status"], "aprovacao_pendente")
        self.assertNotIn("slides", rel)

    def test_aprovacao_recusada_para_ficha_alterada(self):
        obj = json.loads((EX / "ficha_ferramentas_furadeira.json").read_text(encoding="utf-8"))
        obj["title"] = "Furadeira Sem Fio Fictícia Plus"
        arq = self.tmp / "alterada.json"
        arq.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        rel = executar(arq, self.tmp / "rec", AGORA, aprovar_fundo_ficticio=True)
        self.assertEqual(rel["status"], "aprovacao_de_teste_recusada")
        self.assertFalse(rel["fixtureFicticia"])

    def test_estilo_v1_reproduz_a_b2(self):
        for estilo in (None, "v1"):                    # padrão (auto → v1 na fixture legada) e v1 explícito
            res = ref.verificar_b2(estilo)
            self.assertEqual(res["erros"], [], res["motivoBytesPng"])
            self.assertEqual(res["captura"]["estilo"], "v1")

    def test_estilo_invalido(self):
        with self.assertRaises(ErroFluxo):
            executar(LEGADA, self.tmp / "x", AGORA, estilo="v3")

    def test_cli_estilo(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main([str(EX / "ficha_casa_cozinha_panela.json"), "--saida", str(self.tmp / "cli"), "--agora", "2026-11-18T12:00:00Z",
                             "--estilo", "v2", "--aprovar-fundo-ficticio"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["slides"], 4)

    def test_menos_de_3_slides_bloqueia(self):
        obj = json.loads((EX / "ficha_ferramentas_furadeira.json").read_text(encoding="utf-8"))
        ficha = {"produto": {"title": "Item Fictício", "store": "Loja Fictícia"}}
        cfg = {"slides": [{"titulo": "CARACTERÍSTICA", "texto": "Corpo em alumínio"}]}
        m = E.montar_slides(ficha, cfg, {"ilustracao": "a", "fundos": ["b", "c", "d"]}, None)
        self.assertEqual(len(m.slides), 2)
        self.assertEqual([b["codigo"] for b in m.bloqueios], ["numero_de_slides"])
        self.assertTrue(obj)


if __name__ == "__main__":
    unittest.main()
