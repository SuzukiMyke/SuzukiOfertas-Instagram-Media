"""DT-37: regressão da B2 independente do codificador PNG. Testes reais (determinismo, histórico) e testes de mutação/simulação da lógica."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests import b2r_referencia as ref

REFERENCIA = json.loads(ref.ARQUIVO.read_text(encoding="utf-8"))
# Valores históricos (capturados em ef25672) fixados em literal: o JSON não pode ser regravado para "consertar" uma regressão.
JPEGS_HISTORICOS = ["a858ddf06c55", "76901aae3896", "b52aedeea45f", "dacfe882592f"]


# Ambientes SINTÉTICOS (literais, independentes da máquina que roda a suíte) para exercitar o caminho de comparação de bytes.
AMB_A = {"python": "3.13.0", "pillow": "12.3.0", "zlib": "1.3", "zlibNg": False, "libjpeg": "3.1.4.1", "freetype": "2.14.3", "raqm": "0.10.5",
         "sondaPng": "a1" * 32}
REF_AMB_A = {"capturaOriginal": "sintética (teste)", "reproducaoVerificada": dict(AMB_A)}
AMB_ZLIB_NG = {**AMB_A, "zlib": "1.3.1.zlib-ng", "zlibNg": True, "sondaPng": "b2" * 32}


def ref_b2_coerente(captura: dict) -> dict:
    """Referência sintética CONSISTENTE com ``captura``: mesmos JPEGs, mesmos bytes de PNG e de folha (como se tivessem sido gravados pelo
    codificador do ambiente simulado). Status, fundo, carrossel e nomes continuam os históricos; os hashes históricos não são tocados."""
    r = copy.deepcopy(REFERENCIA["b2"])
    r["slides"] = [[arq, s["jpegSha256"], s["pngSha256"]] for (arq, _, _), s in zip(REFERENCIA["b2"]["slides"], captura["slides"])]
    r["folha"] = captura["folha"]["sha256"]
    return r


class Capturas(unittest.TestCase):
    """Duas execuções reais e independentes do fluxo B2 histórico (mesma fixture, relógio e parâmetros), reutilizadas pelos testes."""
    @classmethod
    def setUpClass(cls):
        cls.c1, cls.c2 = ref.capturar_b2(), ref.capturar_b2()
        cls.amb = ref.impressao_ambiente()

    def comparar(self, captura=None, amb=None, ref_amb=None, ref_conteudo=None):
        return ref.comparar_b2(captura or self.c1, REFERENCIA["b2"], REFERENCIA["b2Conteudo"] if ref_conteudo is None else ref_conteudo, amb or self.amb,
                               REFERENCIA["ambiente"] if ref_amb is None else ref_amb)


class Reais(Capturas):
    def test_determinismo_local_bytes_identicos(self):
        self.assertEqual(ref.comparar_deterministico(self.c1, self.c2), [])
        self.assertEqual(self.c1, self.c2)

    def test_referencia_historica_preservada_no_json(self):
        self.assertEqual([x[1][:12] for x in REFERENCIA["b2"]["slides"]], JPEGS_HISTORICOS)
        self.assertEqual(REFERENCIA["commitBase"], "ef256724578d87b7aa60b457b991f447dd671963")
        self.assertEqual(len(REFERENCIA["b2"]["slides"]), 4)
        self.assertEqual(sorted(REFERENCIA["b2"]), ["carrossel", "folha", "fundo", "slides", "status"])

    def test_conteudo_de_referencia_completo(self):
        cont = REFERENCIA["b2Conteudo"]
        self.assertEqual([c["arquivo"] for c in cont["slides"]], [x[0] for x in REFERENCIA["b2"]["slides"]])
        for c in cont["slides"]:
            self.assertEqual((c["conteudo"]["largura"], c["conteudo"]["altura"], c["conteudo"]["modo"]), (1080, 1350, "RGB"))
        self.assertEqual((cont["folha"]["conteudo"]["modo"], cont["folha"]["conteudo"]["largura"]), ("RGB", 1680))

    def test_head_reproduz_a_referencia_neste_ambiente(self):
        """Funciona em qualquer ambiente: o conteúdo é sempre verificado; os bytes dos PNGs só quando a equivalência está comprovada."""
        r = self.comparar()
        self.assertEqual(r["erros"], [], r["motivoBytesPng"])                      # conteúdo (pixels, dimensões, modo) e JPEGs sempre
        equivalente, _ = ref.ambiente_equivalente(self.amb, REFERENCIA["ambiente"])
        self.assertEqual(r["bytesPngComparados"], equivalente)                      # os bytes só são comparados com equivalência comprovada
        # a verificação é efetiva: um pixel adulterado reprova em qualquer ambiente ...
        c = copy.deepcopy(self.c1)
        c["slides"][0]["pngConteudo"]["pixels"] = "0" * 64
        self.assertTrue(any("slide_01.jpg: pixels" in e for e in self.comparar(c)["erros"]))
        # ... e um byte de PNG adulterado só reprova quando os bytes estão sendo comparados
        c = copy.deepcopy(self.c1)
        c["slides"][1]["pngSha256"] = "0" * 64
        erros = self.comparar(c)["erros"]
        if equivalente:
            self.assertIn("slide_02.jpg: SHA-256 dos bytes do PNG diverge (ambiente de codificação equivalente)", erros)
            self.assertNotIn("dispensada", r["motivoBytesPng"])
        else:
            self.assertEqual(erros, [])
            self.assertTrue(r["motivoBytesPng"].startswith("comparação dos bytes comprimidos dispensada: "), r["motivoBytesPng"])
            self.assertNotIn("mesmo Pillow", r["motivoBytesPng"])

    def test_o_ambiente_atual_e_declarado_equivalente_por_evidencia_medida(self):
        """Não presume o ambiente: classifica-o contra a reprodução verificada e confere que o motivo é coerente com a classificação."""
        verificada = REFERENCIA["ambiente"]["reproducaoVerificada"]
        ok, motivo = ref.ambiente_equivalente(self.amb, REFERENCIA["ambiente"])
        if ok:
            for campo in ("pillow", "zlib", "zlibNg", "sondaPng"):
                self.assertEqual(self.amb[campo], verificada[campo], campo)
        else:
            self.assertTrue(any(self.amb.get(c) != verificada.get(c) for c in ("pillow", "zlib", "zlibNg", "sondaPng")), motivo)
            self.assertIn("codificador diferente", motivo)
        self.assertIn("NÃO REGISTRADA", REFERENCIA["ambiente"]["capturaOriginal"])

    def test_hipotese_o_codificador_muda_bytes_nao_pixels(self):
        """Evidência da hipótese: o MESMO conteúdo salvo com outro nível de compressão (stand-in de outro codificador) muda os bytes do
        PNG e não muda os pixels decodificados."""
        im = Image.new("RGB", (256, 256))
        im.putdata([((x * 7 + y) % 256, (x ^ y) % 256, (x * y) % 256) for y in range(256) for x in range(256)])
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t, "a.png"), Path(t, "b.png")
            im.save(a, "PNG", compress_level=1)
            im.save(b, "PNG", compress_level=9)
            self.assertNotEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(ref.pixels_canonicos(a), ref.pixels_canonicos(b))


class Mutacao(Capturas):
    def mut(self):
        return copy.deepcopy(self.c1)

    def test_1_alteracao_de_um_pixel(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t, "a.png"), Path(t, "b.png")
            im = Image.new("RGB", (64, 64), (1, 45, 107))
            im.save(a, "PNG")
            im.putpixel((10, 10), (1, 45, 108))
            im.save(b, "PNG")
            self.assertNotEqual(ref.pixels_canonicos(a)["pixels"], ref.pixels_canonicos(b)["pixels"])
        c = self.mut()
        c["slides"][2]["pngConteudo"]["pixels"] = "0" * 64
        self.assertTrue(any("pixels decodificados do PNG diverge" in e for e in self.comparar(c)["erros"]))

    def test_1b_pixel_alterado_com_bytes_png_recodificados_ainda_reprova_em_ambiente_diferente(self):
        c = self.mut()
        c["slides"][0]["pngConteudo"]["pixels"] = "f" * 64
        c["slides"][0]["pngSha256"] = "e" * 64
        r = self.comparar(c, amb={**self.amb, "sondaPng": "0" * 64})
        self.assertFalse(r["bytesPngComparados"])
        self.assertTrue(any("slide_01.jpg: pixels" in e for e in r["erros"]))

    def test_2_alteracao_do_conteudo_do_carrossel(self):
        c = self.mut()
        c["carrossel"]["slides"][1]["texto"] += " x"
        self.assertIn("carrossel diverge da referência", self.comparar(c)["erros"])
        c = self.mut()
        c["status"], c["fundo"] = "bloqueado", "0" * 64
        e = self.comparar(c)["erros"]
        self.assertIn("status diverge da referência", e)
        self.assertIn("fundo diverge da referência", e)

    def test_3_alteracao_de_dimensao(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t, "a.png"), Path(t, "b.png")
            Image.new("RGB", (64, 64), (9, 9, 9)).save(a, "PNG")
            Image.new("RGB", (64, 65), (9, 9, 9)).save(b, "PNG")
            self.assertNotEqual(ref.pixels_canonicos(a), ref.pixels_canonicos(b))
        c = self.mut()
        c["slides"][1]["pngConteudo"]["altura"] = 1349
        c["folha"]["conteudo"]["largura"] = 1679
        e = self.comparar(c)["erros"]
        self.assertIn("slide_02.jpg: altura do PNG diverge", e)
        self.assertIn("folha: largura diverge", e)

    def test_4_alteracao_de_modo_de_cor(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t, "a.png"), Path(t, "b.png")
            Image.new("RGB", (32, 32), (1, 2, 3)).save(a, "PNG")
            Image.new("RGB", (32, 32), (1, 2, 3)).convert("RGBA").save(b, "PNG")
            pa, pb = ref.pixels_canonicos(a), ref.pixels_canonicos(b)
            self.assertEqual((pa["modo"], pb["modo"]), ("RGB", "RGBA"))
            self.assertNotEqual(pa["pixels"], pb["pixels"])                  # o modo não é ocultado pela conversão
        c = self.mut()
        c["slides"][3]["pngConteudo"]["modo"] = "RGBA"
        c["folha"]["conteudo"]["modo"] = "P"
        e = self.comparar(c)["erros"]
        self.assertIn("slide_04.jpg: modo de cor do PNG diverge", e)
        self.assertIn("folha: modo de cor diverge", e)

    def test_5_alteracao_de_um_jpeg(self):
        c = self.mut()
        c["slides"][1]["jpegSha256"] = "a" * 64
        self.assertIn("slide_02.jpg: SHA-256 do JPEG diverge", self.comparar(c, amb={**self.amb, "sondaPng": "0" * 64})["erros"])

    def test_5b_nome_ordem_e_quantidade_dos_slides(self):
        c = self.mut()
        c["slides"].reverse()
        self.assertTrue(any("nome, quantidade ou ordem" in e for e in self.comparar(c)["erros"]))
        c = self.mut()
        c["slides"].pop()
        self.assertTrue(any("nome, quantidade ou ordem" in e for e in self.comparar(c)["erros"]))

    def test_6_bytes_png_alterados_com_ambiente_equivalente(self):
        """Ambiente equivalente CONTROLADO (sintético e coerente): não depende do codificador da máquina."""
        coerente = ref_b2_coerente(self.c1)
        ok, _ = ref.ambiente_equivalente(AMB_A, REF_AMB_A)
        self.assertTrue(ok)
        base = ref.comparar_b2(self.c1, coerente, REFERENCIA["b2Conteudo"], AMB_A, REF_AMB_A)
        self.assertEqual(base["erros"], [])                                  # referência coerente: sem alteração, nada a apontar
        self.assertTrue(base["bytesPngComparados"])
        c = self.mut()
        c["slides"][2]["pngSha256"] = "b" * 64
        c["folha"]["sha256"] = "c" * 64
        r = ref.comparar_b2(c, coerente, REFERENCIA["b2Conteudo"], AMB_A, REF_AMB_A)
        self.assertTrue(r["bytesPngComparados"])
        self.assertEqual(sorted(r["erros"]), sorted([
            "slide_03.jpg: SHA-256 dos bytes do PNG diverge (ambiente de codificação equivalente)",
            "folha: SHA-256 dos bytes do PNG diverge (ambiente de codificação equivalente)"]))        # só a alteração de bytes, nada mais

    def test_7_ambiente_diferente_simulado_mantem_a_comparacao_de_pixels(self):
        diferente = {**self.amb, "sondaPng": "d" * 64, "zlib": "1.3.1.zlib-ng", "zlibNg": True}
        c = self.mut()
        for s in c["slides"]:
            s["pngSha256"] = "9" * 64                                        # bytes comprimidos de outro codificador
        c["folha"]["sha256"] = "9" * 64
        r = self.comparar(c, amb=diferente)
        self.assertEqual(r["erros"], [])                                     # bytes dispensados, conteúdo idêntico → passa
        self.assertFalse(r["bytesPngComparados"])
        self.assertIn("dispensada", r["motivoBytesPng"])
        c["slides"][1]["pngConteudo"]["pixels"] = "0" * 64                   # mas um pixel diferente continua reprovando
        self.assertTrue(self.comparar(c, amb=diferente)["erros"])

    def test_8_ambiente_declarado_equivalente_sem_evidencia(self):
        """Versões IGUAIS às da referência (sem diferença de zlib que encerre a análise antes) mas SEM a evidência de codificação."""
        verificada = REF_AMB_A["reproducaoVerificada"]
        self.assertTrue(ref.ambiente_equivalente(AMB_A, REF_AMB_A)[0])               # controle: com a evidência completa, é equivalente
        for campo in ("sondaPng", "pillow", "zlib", "zlibNg"):                       # evidência ausente na REFERÊNCIA
            sem = {"reproducaoVerificada": {k: v for k, v in verificada.items() if k != campo}}
            ok, motivo = ref.ambiente_equivalente(AMB_A, sem)
            self.assertFalse(ok, campo)
            self.assertIn("evidência insuficiente na referência", motivo)
            self.assertIn(campo, motivo)
        for campo in ("sondaPng", "pillow", "zlib", "zlibNg"):                       # evidência ausente no AMBIENTE ATUAL
            ok, motivo = ref.ambiente_equivalente({k: v for k, v in AMB_A.items() if k != campo}, REF_AMB_A)
            self.assertFalse(ok, campo)
            self.assertIn("evidência insuficiente no ambiente atual", motivo)
        ok, motivo = ref.ambiente_equivalente({**AMB_A, "sondaPng": ""}, REF_AMB_A)  # evidência vazia
        self.assertFalse(ok)
        self.assertIn("evidência insuficiente", motivo)
        ok, motivo = ref.ambiente_equivalente({**AMB_A, "sondaPng": "c3" * 32}, REF_AMB_A)   # evidência inválida: mesmas versões, sonda diferente
        self.assertFalse(ok)
        self.assertIn("sondaPng", motivo)
        for referencia in ({}, None, {"reproducaoVerificada": None}, {"reproducaoVerificada": "x"}):
            self.assertFalse(ref.ambiente_equivalente(AMB_A, referencia)[0])
        # consequência: sem evidência os bytes NÃO são comparados (pixels, JPEGs e dimensões continuam valendo)
        coerente = ref_b2_coerente(self.c1)
        sem_sonda = {"reproducaoVerificada": {k: v for k, v in verificada.items() if k != "sondaPng"}}
        c = self.mut()
        c["slides"][0]["pngSha256"] = "b" * 64
        r = ref.comparar_b2(c, coerente, REFERENCIA["b2Conteudo"], AMB_A, sem_sonda)
        self.assertFalse(r["bytesPngComparados"])
        self.assertEqual(r["erros"], [])
        self.assertIn("evidência insuficiente", r["motivoBytesPng"])
        c["slides"][0]["pngConteudo"]["pixels"] = "0" * 64
        self.assertTrue(ref.comparar_b2(c, coerente, REFERENCIA["b2Conteudo"], AMB_A, sem_sonda)["erros"])

    def test_9_falha_de_determinismo_entre_duas_execucoes(self):
        for alterar in (lambda c: c["slides"][0].__setitem__("jpegSha256", "1" * 64),
                        lambda c: c["slides"][1].__setitem__("pngSha256", "2" * 64),
                        lambda c: c["folha"].__setitem__("sha256", "3" * 64),
                        lambda c: c["slides"][2]["pngConteudo"].__setitem__("pixels", "4" * 64)):
            c = self.mut()
            alterar(c)
            self.assertTrue(ref.comparar_deterministico(self.c1, c))

    def test_conteudo_nunca_dispensado(self):
        r = self.comparar(ref_conteudo={})
        self.assertTrue(any("b2Conteudo" in e for e in r["erros"]))
        r = ref.comparar_b2(self.c1, REFERENCIA["b2"], None, self.amb, None)
        self.assertTrue(r["erros"])


class Cenarios(Capturas):
    """Simulações determinísticas A-D da portabilidade (não substituem a execução real em outro ambiente)."""

    def rodar(self, captura, amb, ref_amb):
        return ref.comparar_b2(captura, ref_b2_coerente(self.c1), REFERENCIA["b2Conteudo"], amb, ref_amb)

    def test_cenario_a_codificador_equivalente_com_evidencia_valida(self):
        r = self.rodar(self.c1, AMB_A, REF_AMB_A)
        self.assertEqual(r["erros"], [])
        self.assertTrue(r["bytesPngComparados"])
        c = copy.deepcopy(self.c1)
        c["slides"][3]["pngSha256"] = "d" * 64
        self.assertEqual(self.rodar(c, AMB_A, REF_AMB_A)["erros"], ["slide_04.jpg: SHA-256 dos bytes do PNG diverge (ambiente de codificação equivalente)"])

    def test_cenario_b_codificador_diferente(self):
        c = copy.deepcopy(self.c1)
        for x in c["slides"]:
            x["pngSha256"] = "e" * 64                                        # outro codificador: bytes comprimidos diferentes, mesmo conteúdo
        c["folha"]["sha256"] = "e" * 64
        r = self.rodar(c, AMB_ZLIB_NG, REF_AMB_A)
        self.assertEqual(r["erros"], [])
        self.assertFalse(r["bytesPngComparados"])
        self.assertTrue(r["motivoBytesPng"].startswith("comparação dos bytes comprimidos dispensada: codificador diferente"))
        self.assertIn("zlib", r["motivoBytesPng"])

    def test_cenario_c_aparentemente_equivalente_sem_evidencia(self):
        sem_sonda_ref = {"reproducaoVerificada": {k: v for k, v in AMB_A.items() if k != "sondaPng"}}
        sem_sonda_atual = {k: v for k, v in AMB_A.items() if k != "sondaPng"}
        c = copy.deepcopy(self.c1)
        c["slides"][0]["pngSha256"] = "f" * 64
        for amb, ref_amb in ((AMB_A, sem_sonda_ref), (sem_sonda_atual, REF_AMB_A)):
            r = self.rodar(c, amb, ref_amb)
            self.assertFalse(r["bytesPngComparados"])
            self.assertIn("evidência insuficiente", r["motivoBytesPng"])
            self.assertEqual(r["erros"], [])                                 # versões idênticas não autorizam comparar bytes
            c2 = copy.deepcopy(c)
            c2["slides"][1]["pngConteudo"]["modo"] = "RGBA"
            self.assertIn("slide_02.jpg: modo de cor do PNG diverge", self.rodar(c2, amb, ref_amb)["erros"])

    def test_cenario_d_conteudo_alterado_com_codificador_diferente(self):
        for alterar, esperado in ((lambda c: c["slides"][1]["pngConteudo"].__setitem__("pixels", "0" * 64), "slide_02.jpg: pixels decodificados do PNG diverge"),
                                  (lambda c: c["slides"][0]["pngConteudo"].__setitem__("altura", 1351), "slide_01.jpg: altura do PNG diverge"),
                                  (lambda c: c["folha"]["conteudo"].__setitem__("modo", "L"), "folha: modo de cor diverge"),
                                  (lambda c: c["slides"][2].__setitem__("jpegSha256", "0" * 64), "slide_03.jpg: SHA-256 do JPEG diverge")):
            c = copy.deepcopy(self.c1)
            for x in c["slides"]:
                x["pngSha256"] = "e" * 64
            alterar(c)
            r = self.rodar(c, AMB_ZLIB_NG, REF_AMB_A)
            self.assertFalse(r["bytesPngComparados"])
            self.assertIn(esperado, r["erros"])


if __name__ == "__main__":
    unittest.main()
