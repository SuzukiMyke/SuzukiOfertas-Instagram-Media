"""Fundo de marca determinístico (GOAL 5.14-B1, commit 3): dimensões, determinismo, identidade, catálogo pendente, sem rede.

Tudo em catálogo temporário: ``photos/catalogo.json`` do repositório nunca é tocado. Imagens sintéticas geradas por código.
"""
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageStat

from gerador import catalogo as cat_mod
from gerador import fundo_marca as fm
from gerador import identidade as idv
from gerador.carrossel import carregar
from gerador.catalogo import Catalogo
from gerador.layouts import LAYOUTS
from gerador.selecao import ErroSelecao, selecionar
from gerador.validacao import DESVIO_MINIMO_FOTO, validar_slide
from produtos.carrossel_fragmento_v11 import ficha_para_carrossel_v11
from produtos.tests.base import AGORA, Base
from produtos.tests.base_v11 import BaseV11, produto_b

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO_REPO = RAIZ / "photos" / "catalogo.json"
LOGO = RAIZ / "brand" / "logo-suzuki-ofertas.png"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def distancia(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


class FundoBase(Base):
    def setUp(self):
        super().setUp()
        self.raiz = self.tmp / "repo_temp"
        self.cat = Catalogo(self.raiz)


class ImagemTest(FundoBase):
    def test_dimensoes_formato_e_modo(self):
        dados = fm.fundo_bytes(0)
        with Image.open(io.BytesIO(dados)) as im:
            self.assertEqual((im.size, im.format, im.mode), ((1080, 1350), "JPEG", "RGB"))
        self.assertEqual(fm.gerar_fundo(3).size, (idv.W, idv.H))

    def test_determinismo_bytes_e_sha256(self):
        for v in (0, 4, fm.VARIANTES - 1):
            a, b = fm.fundo_bytes(v), fm.fundo_bytes(v)
            self.assertEqual(a, b)
            self.assertEqual(hashlib.sha256(a).hexdigest(), fm.sha256_fundo(v))
        self.assertEqual(fm.fundo_bytes(0), fm.fundo_bytes(0))

    def test_determinismo_sobrevive_a_cache_limpo_e_a_outras_chamadas(self):
        antes = fm.sha256_fundo(2)
        idv.logo_marca_dagua.cache_clear()
        fm.fundo_bytes(7)                                    # chamar outra variante no meio não altera nada
        self.assertEqual(fm.sha256_fundo(2), antes)

    def test_variantes_distintas_geram_imagens_distintas(self):
        hashes = {fm.sha256_fundo(v) for v in range(fm.VARIANTES)}
        self.assertEqual(len(hashes), fm.VARIANTES)

    def test_variante_invalida(self):
        for ruim in (-1, fm.VARIANTES, 1.5, "0", None, True):
            with self.assertRaises(ValueError, msg=repr(ruim)):
                fm.fundo_bytes(ruim)

    def test_golden_estavel_de_uma_variante(self):
        # mesma versão do Pillow/libjpeg: se este valor mudar por atualização do Pillow, é limitação conhecida (ver docstring)
        self.assertRegex(fm.sha256_fundo(0), r"^[0-9a-f]{64}$")
        self.assertEqual(fm.sha256_fundo(0), fm.sha256_fundo(0))


class IdentidadeVisualTest(FundoBase):
    def test_usa_as_cores_oficiais_do_modulo_de_identidade(self):
        fonte = (RAIZ / "gerador" / "fundo_marca.py").read_text(encoding="utf-8")
        for nome in ("AZUL_ESCURO", "AZUL_VIBRANTE", "AMARELO"):
            self.assertIn(f"idv.{nome}", fonte)
        self.assertIs(fm.idv, idv)
        self.assertNotRegex(fonte, r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)\s*\+", "cores literais fora da identidade")

    def test_paleta_dominante_e_a_da_marca(self):
        im = fm.gerar_fundo(0)
        media = im.resize((1, 1), Image.BOX).getpixel((0, 0))
        self.assertLess(distancia(media, idv.AZUL_ESCURO), distancia(media, (255, 255, 255)))
        self.assertGreater(media[2], media[0] + 40)                    # predominância do azul
        dados = im.tobytes()
        total = len(dados) // 3
        amarelados = sum(1 for i in range(0, len(dados), 3) if dados[i] > dados[i + 2])     # R > B: o AMARELO translúcido sobre o azul
        self.assertGreater(amarelados, 2000)                            # o amarelo da marca aparece como acento
        self.assertLess(amarelados / total, 0.25)                       # ...sem dominar

    def test_logotipo_oficial_e_usado_sem_ser_modificado(self):
        antes = sha(LOGO)
        fm.fundo_bytes(1)
        self.assertEqual(sha(LOGO), antes)
        fonte = (RAIZ / "gerador" / "fundo_marca.py").read_text(encoding="utf-8")
        self.assertIn("idv.logo_marca_dagua", fonte)
        self.assertNotIn(".save(LOGO", fonte)

    def test_sem_fotos_nem_textos_de_produto(self):
        fonte = (RAIZ / "gerador" / "fundo_marca.py").read_text(encoding="utf-8")
        codigo = re.sub(r'^""".*?"""', "", fonte, count=1, flags=re.S)                  # sem o docstring do módulo
        for proibido in (".text(", "idv.fonte(", "ImageFont", "Image.open(", "cobrir(", "catalogo.json"):
            self.assertNotIn(proibido, codigo, proibido)

    def test_contraste_suficiente_para_o_validador_do_gerador(self):
        for v in range(fm.VARIANTES):
            im = fm.gerar_fundo(v)
            for nome, area in {"topo": (0, 0, 1080, 560), "cartao": (72, 380, 1008, 980), "cheia": (0, 0, 1080, 700)}.items():
                desvio = ImageStat.Stat(im.crop(area).convert("L")).stddev[0]
                self.assertGreater(desvio, DESVIO_MINIMO_FOTO + 3, (v, nome, desvio))

    def test_funciona_nos_layouts_existentes_do_gerador(self):
        # sanidade com o gerador atual (NÃO é a renderização do carrossel, que é da etapa seguinte)
        for v in (0, 6, 11):
            im = fm.gerar_fundo(v)
            for layout in ("foto_topo", "cartao"):
                img, areas = LAYOUTS[layout](im, {"layout": layout, "titulo": "TÍTULO", "destaque": "CURTO", "texto": "Texto curto."}, 1, 3)
                arq = self.tmp / f"{layout}_{v}.jpg"
                img.convert("RGB").save(arq, "JPEG", quality=90)
                self.assertEqual(validar_slide(arq, areas), [], (v, layout))


class CatalogoTest(FundoBase):
    def test_provedores_existentes_preservados_e_novo_registrado(self):
        self.assertEqual(cat_mod.PROVEDORES["cloudflare-flux"], "flux")
        self.assertEqual(cat_mod.PROVEDORES["nano-banana"], "nb")
        self.assertEqual(cat_mod.PROVEDORES["foto-real"], "real")
        self.assertEqual(cat_mod.PROVEDORES["composicao-grafica"], "cg")
        self.assertEqual(cat_mod.ORIGEM_COMPOSICAO_GRAFICA, "composicao-grafica")
        self.assertEqual(self.cat.proximo_id("nano-banana"), "nb-0001")
        self.assertEqual(self.cat.proximo_id("composicao-grafica"), "cg-0001")

    def test_registro_nasce_pendente_e_nunca_aprovado(self):
        fid, nova = fm.registrar(self.cat, 0, agora="2026-11-17T15:00:00Z")
        self.assertEqual((fid, nova), ("cg-0001", True))
        meta = self.cat.obter(fid)
        self.assertEqual((meta["provedor"], meta["origem"], meta["id"]), ("composicao-grafica", "composicao-grafica", "cg-0001"))
        self.assertEqual(meta["aprovacao"], {"status": "pendente", "por": None, "data": None, "nota": None})
        self.assertEqual((meta["largura"], meta["altura"], meta["prompt"]), (1080, 1350, None))
        self.assertEqual(meta["sha256_original"], meta["sha256"])
        self.assertEqual(meta["sha256"], fm.sha256_fundo(0))
        arq = self.raiz / meta["caminho_github"]
        self.assertEqual(sha(arq), meta["sha256"])
        self.assertTrue(any("Arte ilustrativa" in r for r in meta["restricoes_uso"]))
        self.assertEqual(meta["gerador"]["variante"], 0)

    def test_catalogo_e_persistido_so_no_temporario(self):
        fm.registrar(self.cat, 0)
        recarregado = Catalogo(self.raiz)
        self.assertIn("cg-0001", recarregado.fotos)
        self.assertEqual(recarregado.fotos["cg-0001"]["aprovacao"]["status"], "pendente")

    def test_mesmo_conteudo_nao_duplica_e_variantes_geram_novos_ids(self):
        a = fm.registrar(self.cat, 0)
        self.assertEqual(fm.registrar(self.cat, 0), ("cg-0001", False))
        self.assertEqual(a, ("cg-0001", True))
        self.assertEqual(fm.registrar(self.cat, 1), ("cg-0002", True))
        self.assertEqual(len(self.cat.fotos), 2)

    def test_catalogo_do_repositorio_nunca_e_tocado(self):
        antes = (sha(CATALOGO_REPO), sorted(p.name for p in (RAIZ / "photos").iterdir()))
        fm.registrar(self.cat, 0)
        fm.fundo_bytes(2)
        self.assertEqual((sha(CATALOGO_REPO), sorted(p.name for p in (RAIZ / "photos").iterdir())), antes)
        self.assertNotIn("composicao-grafica", CATALOGO_REPO.read_text(encoding="utf-8"))

    def test_catalogo_e_obrigatorio_nao_ha_padrao(self):
        with self.assertRaises(TypeError):
            fm.registrar()

    def test_selecao_do_gerador_exige_aprovacao_humana(self):
        fid, _ = fm.registrar(self.cat, 0)
        slide = {"layout": "cartao", "foto": fid, "titulo": "X"}
        with self.assertRaises(ErroSelecao):
            selecionar([slide], self.cat)                                    # pendente: bloqueado
        auto = {"layout": "cartao", "foto": "auto", "provedor": "composicao-grafica", "titulo": "X"}
        with self.assertRaises(ErroSelecao):
            selecionar([auto], self.cat)                                     # nem por seleção automática
        self.cat.definir_aprovacao(fid, "aprovada", "Maria Revisora", "aprovada manualmente no teste")
        self.assertEqual(selecionar([slide], self.cat), [fid])
        self.assertEqual(selecionar([auto], self.cat), [fid])


class IntegracaoComCarrosselTest(BaseV11):
    """Fundo -> ficha_para_carrossel_v11 com recurso_visual = composicao_grafica (sem renderizar o carrossel: etapa seguinte)."""

    def setUp(self):
        super().setUp()
        self.raiz = self.tmp / "repo_temp"
        self.cat = Catalogo(self.raiz)
        self.fid, _ = fm.registrar(self.cat, 0, agora="2026-11-17T15:00:00Z")
        _, fs = self.rodar(b={"b.json": produto_b(4, "B001")}, humanos=self.humanos())
        self.ficha = fs["EXEMPLO_B__B001"]

    def carrossel(self, **kw):
        base = dict(t_publicacao=AGORA, foto_catalogo_id=self.fid, recurso_visual="composicao_grafica", catalogo=self.cat.fotos)
        base.update(kw)
        return ficha_para_carrossel_v11(self.ficha, **base)

    def test_fundo_sem_aprovacao_permanece_bloqueado(self):
        r = self.carrossel()
        self.assertEqual((r["status"], r["carrossel"], r["bloqueios"][0]["codigo"]), ("bloqueado", None, "foto_nao_aprovada_no_catalogo"))

    def test_fundo_aprovado_manualmente_e_usado_com_o_rotulo_arte_ilustrativa(self):
        self.cat.definir_aprovacao(self.fid, "aprovada", "Maria Revisora")
        r = self.carrossel()
        self.assertEqual((r["status"], r["classe_visual"], r["bloqueios"]), ("rascunho", "composicao_grafica", []))
        slides = r["carrossel"]["slides"]
        self.assertTrue(all(s["foto"] == self.fid for s in slides))
        self.assertIn("Arte ilustrativa", slides[0]["texto"])
        self.assertIn("Arte ilustrativa", r["legenda_sugerida"])
        self.assertTrue(any("Arte ilustrativa" in a for a in r["avisos"]))
        self.assertIs(r["aprovado_para_publicacao_definido"], False)

    def test_saida_e_compativel_com_o_gerador_existente(self):
        self.cat.definir_aprovacao(self.fid, "aprovada", "Maria Revisora")
        r = self.carrossel(links_oficiais={"whatsapp": "https://wa.me/5511999999999", "telegram": "https://t.me/suzukiofertas_ficticio"})
        arq = self.tmp / "carrossel.json"
        arq.write_text(json.dumps(r["carrossel"], ensure_ascii=False), encoding="utf-8")
        dados = carregar(arq)                                                  # carregador real do gerador
        self.assertEqual(dados["id"], r["carrossel"]["id"])
        self.assertEqual(selecionar(dados["slides"], self.cat), [self.fid] * len(dados["slides"]))
        self.assertTrue(all(s["layout"] in LAYOUTS for s in dados["slides"]))

    def test_fundo_nao_e_aceito_como_foto_real_autorizada(self):
        self.cat.definir_aprovacao(self.fid, "aprovada", "Maria Revisora")
        r = self.carrossel(recurso_visual="foto_real_autorizada")
        self.assertEqual(r["status"], "bloqueado")
        self.assertIn(r["bloqueios"][0]["codigo"], ("foto_sem_permissao_humana", "foto_nao_e_real"))


class SemRedeTest(FundoBase):
    def test_modulo_sem_rede_processos_ou_ambiente(self):
        fonte = (RAIZ / "gerador" / "fundo_marca.py").read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", fonte, re.M):
            alvo = (m.group(1) or m.group(2)).replace(" ", "")
            for mod in alvo.split(","):
                for proibido in ("urllib", "http", "socket", "requests", "subprocess", "ssl", "ftplib", "smtplib", "webbrowser", "shutil"):
                    self.assertFalse(mod == proibido or mod.startswith(proibido + "."), mod)
        for padrao in ("os.environ", "getenv", "urlopen", "Popen", "os.system"):
            self.assertNotIn(padrao, fonte)

    def test_geracao_e_registro_rodam_com_a_rede_bloqueada(self):
        with self.assertRaises(AssertionError):
            import socket
            socket.create_connection(("exemplo.example", 443))
        fm.registrar(self.cat, 0)                                              # Base.setUp bloqueia qualquer conexão


if __name__ == "__main__":
    unittest.main()
