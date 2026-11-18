"""B2R, commit 1: opções retrocompatíveis (fundo ``marca``, rodapé ``grande``, constantes e helpers de validação).

Os valores de REFERÊNCIA (``tests/b2r_referencia.json``) foram capturados no commit-base ``ef25672`` antes de qualquer edição; com os
parâmetros PADRÃO o comportamento anterior tem de ser idêntico, byte a byte, no mesmo ambiente (mesmo Pillow/libjpeg).
"""
import hashlib
import inspect
import json
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageChops, ImageDraw

from gerador import fundo_marca as fm
from gerador import identidade as idv
from gerador import render as r
from gerador import validacao as v
from gerador.catalogo import Catalogo
from produtos.tests.base import Base
from tests import b2r_referencia as ref

REFERENCIA = json.loads(ref.ARQUIVO.read_text(encoding="utf-8"))


def sha(b):
    return hashlib.sha256(b).hexdigest()


class RegressaoDosCaminhosAntigosTest(Base):
    def test_referencia_vem_do_commit_base(self):
        self.assertEqual(REFERENCIA["commitBase"], "ef256724578d87b7aa60b457b991f447dd671963")

    def test_fundos_das_12_variantes_identicos_ao_anterior(self):
        for var in range(fm.VARIANTES):
            esperado = REFERENCIA["fundos"][str(var)]
            self.assertEqual(sha(fm.fundo_bytes(var)), esperado, var)                    # padrão
            self.assertEqual(sha(fm.fundo_bytes(var, marca=True)), esperado, var)         # marca=True explícito
            self.assertEqual(fm.sha256_fundo(var), esperado)
            self.assertEqual(fm.sha256_fundo(var, marca=True), esperado)

    def test_layouts_antigos_identicos_ao_anterior(self):
        atual = json.loads(json.dumps(ref.hashes_layouts_antigos(), sort_keys=True))
        self.assertEqual(atual, REFERENCIA["layouts"])

    def test_slides_do_b2_antigo_identicos_ao_anterior(self):
        atual = json.loads(json.dumps(ref.hashes_b2_antigo(), sort_keys=True))
        self.assertEqual(atual, REFERENCIA["b2"])

    def test_golden_do_modo_1_0(self):
        from produtos.tests.golden_modo_1_0 import ARQUIVO, calcular
        self.assertEqual(calcular(), json.loads(ARQUIVO.read_text(encoding="utf-8"))["cenarios"])

    def test_constantes_antigas_de_identidade_nao_mudaram(self):
        self.assertEqual((idv.W, idv.H, idv.MARGEM, idv.AZUL_ESCURO, idv.AZUL_VIBRANTE, idv.AMARELO, idv.VERMELHO, idv.BRANCO,
                          idv.TEXTO_SUAVE, idv.LOGO_LADO),
                         (1080, 1350, 72, (1, 45, 107), (3, 78, 231), (254, 198, 24), (246, 2, 19), (255, 255, 255), (230, 236, 248), 120))

    def test_assinaturas_anteriores_preservadas(self):
        self.assertEqual(list(inspect.signature(fm.gerar_fundo).parameters), ["variante", "marca"])
        for f, antigos in ((fm.fundo_bytes, ["variante"]), (fm.sha256_fundo, ["variante"]),
                           (fm.registrar, ["catalogo", "variante", "descricao", "agora"]), (r.rodape, ["base", "numero", "total"])):
            ps = list(inspect.signature(f).parameters.values())
            self.assertEqual([p.name for p in ps[:len(antigos)]], antigos)
            self.assertTrue(all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in ps[len(antigos):]), f)
        self.assertIs(inspect.signature(fm.gerar_fundo).parameters["marca"].default, True)
        self.assertIs(inspect.signature(r.rodape).parameters["grande"].default, False)


class FundoSemMarcaTest(Base):
    def test_sem_marca_nao_tem_logo_e_o_resto_e_identico(self):
        com, sem = fm.gerar_fundo(3), fm.gerar_fundo(3, marca=False)
        self.assertNotEqual(sha(fm.fundo_bytes(3)), sha(fm.fundo_bytes(3, marca=False)))
        diff = ImageChops.difference(com, sem).getbbox()
        self.assertIsNotNone(diff)
        logo = idv.logo_marca_dagua(420, 0.12)
        esperado = ((idv.W - logo.width) // 2, idv.H - logo.height - 150, (idv.W + logo.width) // 2, idv.H - 150)
        self.assertTrue(diff[0] >= esperado[0] and diff[1] >= esperado[1] and diff[2] <= esperado[2] and diff[3] <= esperado[3])
        self.assertEqual((sem.size, sem.mode), ((1080, 1350), "RGB"))

    def test_determinismo_e_validacao(self):
        for var in (0, 5, 11):
            self.assertEqual(fm.fundo_bytes(var, marca=False), fm.fundo_bytes(var, marca=False))
        self.assertEqual(len({fm.sha256_fundo(var, marca=False) for var in range(fm.VARIANTES)}), fm.VARIANTES)
        for ruim in (None, 0, 1, "sim"):
            with self.assertRaises(ValueError):
                fm.gerar_fundo(0, marca=ruim)

    def test_contraste_visual_continua_suficiente_sem_marca(self):
        from PIL import ImageStat
        for var in range(fm.VARIANTES):
            im = fm.gerar_fundo(var, marca=False)
            for area in ((0, 0, 1080, 560), (72, 380, 1008, 980)):
                self.assertGreater(ImageStat.Stat(im.crop(area).convert("L")).stddev[0], 15, (var, area))

    def test_registro_sem_marca_e_pendente_e_distinto(self):
        cat = Catalogo(self.tmp / "cat")
        a = fm.registrar(cat, 0, agora="2026-11-17T15:00:00Z")
        b = fm.registrar(cat, 0, agora="2026-11-17T15:00:00Z", marca=False)
        self.assertEqual((a, b), (("cg-0001", True), ("cg-0002", True)))
        self.assertEqual(fm.registrar(cat, 0, marca=False), ("cg-0002", False))               # idempotente
        ma, mb = cat.obter("cg-0001"), cat.obter("cg-0002")
        self.assertNotIn("marca", ma["gerador"])                                              # registro antigo idêntico ao anterior
        self.assertEqual(mb["gerador"]["marca"], False)
        self.assertEqual((ma["aprovacao"]["status"], mb["aprovacao"]["status"]), ("pendente", "pendente"))
        self.assertEqual((mb["provedor"], mb["origem"]), ("composicao-grafica", "composicao-grafica"))
        self.assertEqual(mb["sha256"], fm.sha256_fundo(0, marca=False))
        self.assertNotEqual(ma["sha256"], mb["sha256"])


class RodapeGrandeTest(Base):
    def fundo(self):
        return Image.new("RGBA", (idv.W, idv.H), idv.AZUL_ESCURO + (255,))

    def test_padrao_nao_mudou(self):
        base = self.fundo()
        caixa = r.rodape(base, 2, 4)
        self.assertEqual(caixa, (idv.W - idv.MARGEM - 120 + 10, idv.H - 44 - 120, idv.W - idv.MARGEM + 10, idv.H - 44))

    def test_grande_tem_logo_de_160px_inteiro_dentro_da_margem(self):
        base = self.fundo()
        x0, y0, x1, y1 = r.rodape(base, 2, 4, grande=True)
        self.assertEqual((x1 - x0, y1 - y0), (160, 160))
        m = idv.MARGEM_SEGURANCA
        self.assertTrue(x0 >= m and y0 >= m and x1 <= idv.W - m and y1 <= idv.H - m, (x0, y0, x1, y1))
        esperado = self.fundo()
        esperado.alpha_composite(idv.logo_marca_dagua(160, 1.0), (x0, y0))
        self.assertEqual(base.crop((x0, y0, x1, y1)).tobytes(), esperado.crop((x0, y0, x1, y1)).tobytes())     # logo inteiro, sem cortes

    def test_contador_tem_pelo_menos_38px(self):
        tamanhos = []
        original = idv.fonte
        with mock.patch.object(idv, "fonte", lambda tipo, tam: (tamanhos.append(tam), original(tipo, tam))[1]):
            r.rodape(self.fundo(), 1, 3, grande=True)
        self.assertTrue(tamanhos and min(tamanhos) >= 38, tamanhos)
        self.assertGreaterEqual(idv.CONTADOR_GRANDE, 38)

    def test_sem_contador_quando_ha_um_unico_slide(self):
        a, b = self.fundo(), self.fundo()
        r.rodape(a, 1, 1, grande=True)
        r.rodape(b, None, None, grande=True)
        self.assertEqual(a.tobytes(), b.tobytes())


class ConstantesEHelpersTest(unittest.TestCase):
    def test_constantes_novas(self):
        self.assertEqual((idv.MARGEM_SEGURANCA, idv.LOGO_GRANDE, idv.FONTE_TITULO_MIN, idv.FONTE_TEXTO_MIN, idv.FONTE_ROTULO_MIN,
                          idv.FONTE_CONTADOR_MIN, idv.CONTRASTE_MIN, idv.ROTULO_ARTE), (72, 160, 72, 44, 36, 36, 4.5, "Arte ilustrativa"))

    def test_razao_de_contraste_wcag(self):
        self.assertAlmostEqual(v.razao_contraste((255, 255, 255), (0, 0, 0)), 21.0, places=1)
        self.assertAlmostEqual(v.razao_contraste((255, 255, 255), (255, 255, 255)), 1.0, places=2)
        self.assertGreater(v.razao_contraste(idv.BRANCO, idv.AZUL_ESCURO), 12)
        self.assertGreater(v.razao_contraste(idv.AMARELO, idv.AZUL_ESCURO), 8)
        self.assertLess(v.razao_contraste(idv.AMARELO, idv.BRANCO), 2)

    def test_contraste_efetivo_aprova_painel_controlado_e_reprova_fundo_claro_ou_variavel(self):
        ok = Image.new("RGB", (500, 200), idv.AZUL_ESCURO)
        ImageDraw.Draw(ok).rectangle((60, 60, 440, 140), fill=idv.BRANCO)
        self.assertGreater(v.contraste_efetivo(ok, (20, 20, 480, 180), idv.BRANCO)["razao"], 4.5)
        claro = Image.new("RGB", (500, 200), (235, 235, 235))
        self.assertLess(v.contraste_efetivo(claro, (20, 20, 480, 180), idv.BRANCO)["razao"], 4.5)
        # fundo escuro com uma mancha clara atrás do texto: a mediana seria "escura". A heurística não consegue separar um fundo quase igual à cor
        # do texto de um glifo; por isso os layouts usam a medição EXATA: render sem texto + pior pixel do fundo na caixa do texto.
        misto = Image.new("RGB", (500, 200), idv.AZUL_ESCURO)
        ImageDraw.Draw(misto).rectangle((20, 20, 480, 100), fill=(240, 240, 240))
        exato = v.contraste_sobre_fundo(misto, (20, 20, 480, 180), idv.BRANCO)
        self.assertLess(exato["razao"], 4.5)
        self.assertGreater(v.contraste_sobre_fundo(Image.new("RGB", (500, 200), idv.AZUL_ESCURO), (20, 20, 480, 180), idv.BRANCO)["razao"], 12)
        self.assertGreater(v.contraste_sobre_fundo(Image.new("RGB", (500, 200), idv.AMARELO), (20, 20, 480, 180), idv.AZUL_ESCURO)["razao"], 8)

    def test_maior_area_vazia(self):
        r1 = v.maior_area_vazia([], 1080, 1350, 72)
        self.assertAlmostEqual(r1["fracao"], (936 * 1206) / (1080 * 1350), delta=0.02)
        cheio = v.maior_area_vazia([(0, 0, 1080, 1350)], 1080, 1350, 72)
        self.assertEqual(cheio["px"], 0)
        meio = v.maior_area_vazia([(0, 0, 1080, 700)], 1080, 1350, 72)
        self.assertLess(meio["fracao"], r1["fracao"])

    def test_validar_slide_antigo_continua_com_a_mesma_assinatura(self):
        self.assertEqual(list(inspect.signature(v.validar_slide).parameters), ["arquivo", "areas"])


if __name__ == "__main__":
    unittest.main()
