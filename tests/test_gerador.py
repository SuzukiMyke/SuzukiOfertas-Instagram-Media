"""Testes locais (sem rede, sem IA). Rodar: python3.12 -m unittest discover -s tests -v

As imagens de teste são sintéticas (ruído/gradiente feitos com Pillow) e
criadas em pasta temporária; nada é gravado no repositório.
"""
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from gerador import flux
from gerador.carrossel import ErroCarrossel, carregar, gerar
from gerador.catalogo import Catalogo
from gerador.importar import ErroImportacao, importar
from gerador.render import cobrir
from gerador.selecao import ErroSelecao, selecionar


def imagem_sintetica(w, h, semente=1, modo="RGB"):
    rnd = random.Random(semente)
    im = Image.new("RGB", (w, h))
    px = [(int(255 * x / w), int(255 * y / h), rnd.randrange(256))
          for y in range(h) for x in range(w)]
    im.putdata(px)
    return im.convert(modo) if modo != "RGB" else im


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.raiz = self.tmp / "repo"
        self.entrada = self.tmp / "entrada"
        self.entrada.mkdir()
        self.cat = Catalogo(self.raiz)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def salvar(self, nome, w=1024, h=1024, semente=1, fmt="JPEG", modo="RGB", **kw):
        p = self.entrada / nome
        imagem_sintetica(w, h, semente, modo).save(p, fmt, **kw)
        return p


class TestImportacao(Base):
    def test_jpg_png_webp(self):
        ids = []
        for nome, fmt, modo in [("a.jpg", "JPEG", "RGB"), ("b.png", "PNG", "RGBA"), ("c.webp", "WEBP", "RGB")]:
            p = self.salvar(nome, 1200, 900, semente=len(ids) + 1, fmt=fmt, modo=modo)
            fid, nova = importar(p, catalogo=self.cat)
            self.assertTrue(nova)
            ids.append(fid)
            meta = self.cat.obter(fid)
            # original preservado byte a byte
            self.assertEqual((self.raiz / meta["caminho_original"]).read_bytes(), p.read_bytes())
            # versão interna JPEG sem deformar
            with Image.open(self.raiz / meta["caminho_github"]) as im:
                self.assertEqual((im.format, im.size), ("JPEG", (1200, 900)))
            self.assertEqual(meta["aprovacao"]["status"], "pendente")
            for campo in ("id", "provedor", "nome_arquivo_original", "sha256_original", "largura",
                          "altura", "data", "origem", "restricoes_uso", "caminho_github"):
                self.assertIn(campo, meta)
        self.assertEqual(ids, ["nb-0001", "nb-0002", "nb-0003"])
        # catálogo persistido em disco e recarregável
        self.assertEqual(sorted(Catalogo(self.raiz).fotos), ids)

    def test_duplicata_por_hash(self):
        p = self.salvar("a.jpg")
        fid1, _ = importar(p, catalogo=self.cat)
        copia = self.entrada / "outro_nome.jpg"
        shutil.copy(p, copia)
        fid2, nova = importar(copia, catalogo=self.cat)
        self.assertEqual((fid1, nova), (fid2, False))
        self.assertEqual(len(self.cat.fotos), 1)

    def test_rejeita_invalidas(self):
        falso = self.entrada / "texto.jpg"
        falso.write_text("não sou imagem")
        pequena = self.salvar("p.jpg", 600, 400)
        gif = self.salvar("g.gif", 1024, 1024, fmt="GIF")
        cortada = self.salvar("c.jpg", 1024, 1024)
        cortada.write_bytes(cortada.read_bytes()[:4000])
        for p in (falso, pequena, gif, cortada, self.entrada / "nao_existe.png"):
            with self.subTest(p=p.name), self.assertRaises(ErroImportacao):
                importar(p, catalogo=self.cat)
        self.assertEqual(self.cat.fotos, {})

    def test_orientacao_exif(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # rotacionar 90°
        p = self.salvar("r.jpg", 1200, 800, exif=exif.tobytes())
        fid, _ = importar(p, catalogo=self.cat)
        self.assertEqual((self.cat.obter(fid)["largura"], self.cat.obter(fid)["altura"]), (800, 1200))

    def test_aprovacao_exige_nome(self):
        fid, _ = importar(self.salvar("a.jpg"), catalogo=self.cat)
        with self.assertRaises(ValueError):
            self.cat.definir_aprovacao(fid, "aprovada", "")
        self.cat.definir_aprovacao(fid, "aprovada", "Myke", "ok no celular")
        ap = self.cat.obter(fid)["aprovacao"]
        self.assertEqual((ap["status"], ap["por"]), ("aprovada", "Myke"))
        self.assertTrue(ap["data"])

    def test_aprovado_na_importacao(self):
        fid, _ = importar(self.salvar("a.jpg"), catalogo=self.cat, aprovado_por="Myke")
        self.assertEqual(self.cat.obter(fid)["aprovacao"]["status"], "aprovada")


class TestSelecaoComposicao(Base):
    def preparar(self, n=3, aprovar=True):
        ids = []
        for i in range(n):
            fid, _ = importar(self.salvar(f"f{i}.jpg", 1024, 1024, semente=i + 10), catalogo=self.cat,
                              aprovado_por="Teste" if aprovar else None)
            ids.append(fid)
        return ids

    def test_pendente_bloqueada(self):
        ids = self.preparar(1, aprovar=False)
        with self.assertRaises(ErroSelecao):
            selecionar([{"foto": ids[0]}], self.cat)
        self.assertEqual(selecionar([{"foto": ids[0]}], self.cat, permitir_pendentes=True), ids)

    def test_rejeitada_e_ausente(self):
        ids = self.preparar(2)
        self.cat.definir_aprovacao(ids[0], "rejeitada", "Teste")
        with self.assertRaises(ErroSelecao):
            selecionar([{"foto": ids[0]}], self.cat, permitir_pendentes=True)
        (self.raiz / self.cat.obter(ids[1])["caminho_github"]).unlink()
        with self.assertRaises(ErroSelecao):
            selecionar([{"foto": ids[1]}], self.cat)
        with self.assertRaises(ErroSelecao):
            selecionar([{"foto": "nb-9999"}], self.cat)

    def test_sem_repeticao_automatica(self):
        ids = self.preparar(3)
        self.assertEqual(selecionar([{"foto": "auto"}] * 3, self.cat), ids)
        with self.assertRaises(ErroSelecao):
            selecionar([{"foto": "auto"}] * 4, self.cat)
        with self.assertRaises(ErroSelecao):
            selecionar([{"foto": ids[0]}, {"foto": ids[0]}], self.cat)
        self.assertEqual(selecionar([{"foto": ids[0]}, {"foto": ids[0], "reutilizar": True}], self.cat),
                         [ids[0], ids[0]])

    def test_cobrir_nao_deforma(self):
        im = Image.new("RGB", (2000, 1000), "white")
        im.paste((0, 0, 0), (900, 400, 1100, 600))  # quadrado 200×200 no centro
        out = cobrir(im, 1080, 1350)
        self.assertEqual(out.size, (1080, 1350))
        bbox = Image.eval(out.convert("L"), lambda v: 255 if v < 128 else 0).getbbox()
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        self.assertLessEqual(abs(w - h), 2)  # continua quadrado

    def test_carrossel_tres_layouts(self):
        ids = self.preparar(3)
        cfg = {"id": "teste", "slides": [
            {"layout": "foto_topo", "foto": ids[0], "titulo": "5 ERROS QUE FAZEM",
             "destaque": "VOCÊ GASTAR MAIS!", "texto": "Descubra como evitar desperdícios nas compras online."},
            {"layout": "cartao", "foto": "auto", "titulo": "ERRO 1:", "destaque": "COMPRAR POR IMPULSO",
             "texto": "Espere 24 horas antes de finalizar."},
            {"layout": "foto_cheia", "foto": "auto", "titulo": "ERRO 2:", "destaque": "IGNORAR O FRETE"},
        ]}
        r = gerar(cfg, self.cat, self.tmp / "saida")
        self.assertEqual(r["problemas"], [])
        self.assertEqual(r["status"], "pronto")
        self.assertEqual([s["foto"] for s in r["slides"]], ids)
        for s in r["slides"]:
            with Image.open(self.tmp / "saida" / s["arquivo"]) as im:
                self.assertEqual((im.format, im.size), ("JPEG", (1080, 1350)))
        man = json.loads((self.tmp / "saida" / "manifest.json").read_text())
        self.assertEqual(len(man["slides"]), 3)

    def test_validacao_detecta_foto_lisa(self):
        p = self.entrada / "lisa.png"
        Image.new("RGB", (1024, 1024), (1, 45, 107)).save(p)
        fid, _ = importar(p, catalogo=self.cat, aprovado_por="Teste")
        r = gerar({"id": "x", "slides": [{"layout": "foto_topo", "foto": fid, "titulo": "TESTE"}]},
                  self.cat, self.tmp / "s")
        self.assertEqual(r["status"], "reprovado")
        self.assertTrue(any("foto não aparece" in p for p in r["problemas"]))

    def test_texto_longo_demais(self):
        ids = self.preparar(1)
        cfg = {"id": "x", "slides": [{"layout": "foto_cheia", "foto": ids[0],
                                      "titulo": "PALAVRA " * 40}]}
        with self.assertRaises(ValueError):
            gerar(cfg, self.cat, self.tmp / "s")

    def test_config_invalida(self):
        p = self.tmp / "c.json"
        for cfg in ({"id": "x", "slides": [{"layout": "nao_existe", "titulo": "A"}]},
                    {"id": "x", "slides": [{"layout": "cartao", "titulo": "A"}] * 11},
                    {"id": "x", "slides": [{"layout": "cartao"}]},
                    {"id": "x", "slides": [{"layout": "cartao", "titulo": "A", "preco": "R$ 1"}]}):
            p.write_text(json.dumps(cfg))
            with self.subTest(cfg=str(cfg)[:60]), self.assertRaises(ErroCarrossel):
                carregar(p)

    def test_exemplo_versionado_e_valido(self):
        carregar(Path(__file__).resolve().parent.parent / "exemplos" / "carrossel_exemplo.json")


class TestFluxSemRede(Base):
    def falsa_api(self, prompt):
        import io
        buf = io.BytesIO()
        imagem_sintetica(256, 256).save(buf, "JPEG")
        self.prompts.append(prompt)
        return buf.getvalue(), 172.8

    def setUp(self):
        super().setUp()
        self.prompts = []

    def test_exige_confirmacao(self):
        with self.assertRaises(RuntimeError):
            flux.gerar("x", confirmar=False, catalogo=self.cat, chamar_api=self.falsa_api)
        self.assertEqual(self.prompts, [])

    def test_registra_e_protege_cota(self):
        fid = flux.gerar("a desk", confirmar=True, catalogo=self.cat, chamar_api=self.falsa_api)
        meta = self.cat.obter(fid)
        self.assertEqual((fid, meta["consumo_neuronios"], meta["aprovacao"]["status"]),
                         ("flux-0001", 172.8, "pendente"))
        self.assertIn("no logos", self.prompts[0])
        antigo = flux.LIMITE_DIARIO
        flux.LIMITE_DIARIO = 300
        try:
            with self.assertRaises(flux.ErroCota):
                flux.gerar("b", confirmar=True, catalogo=self.cat, chamar_api=self.falsa_api)
        finally:
            flux.LIMITE_DIARIO = antigo
        self.assertEqual(len(self.prompts), 1)


if __name__ == "__main__":
    unittest.main()
