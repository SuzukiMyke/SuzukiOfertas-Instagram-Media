"""Separação entre os contratos 1.0 e 1.1 quanto ao provedor ``CURADORIA`` e à fonte ``curadoria_manual`` (verificação final da B1)."""
import unittest

from produtos.esquema import SISTEMA_CURADORIA, validar_produto
from produtos.leitor import ler_pasta
from produtos.leitor_v11 import ler_lote
from produtos.pipeline import processar
from produtos.tests.base import AGORA, Base
from produtos.tests.base_v11 import gravar_lote, produto_a, produto_b
from produtos.tests.test_v11_curadoria import curadoria


def agente(tipo):
    return produto_a(1, "A001", product__provider="CURADORIA") if tipo == "A" else produto_b(4, "B001", product__provider="CURADORIA")


class ProviderCuradoriaTest(Base):
    def test_modo_1_0_continua_aceitando_provider_curadoria_nas_fontes_do_agente(self):
        for tipo in "AB":
            for kw in ({}, {"contrato": "1.0"}):
                r = validar_produto(agente(tipo), AGORA, **kw)
                self.assertTrue(r.ok, (tipo, kw, r.erros))
                self.assertEqual(r.dados["product"]["provider"], "CURADORIA")
                self.assertEqual(r.dados["source"]["system"], "SuzukiOfertas-AgenteAutomatico")

    def test_resultado_do_1_0_e_identico_ao_de_outro_provedor_exceto_o_nome(self):
        for tipo in "AB":
            a = validar_produto(agente(tipo), AGORA).dados
            b = (validar_produto(produto_a(1, "A001"), AGORA) if tipo == "A" else validar_produto(produto_b(4, "B001"), AGORA)).dados
            a["product"]["provider"] = b["product"]["provider"]
            self.assertEqual(a, b)

    def test_pipeline_e_leitor_do_modo_1_0_processam_provider_curadoria(self):
        self.troca.joinpath("a.json").write_text(__import__("json").dumps(agente("A")))
        self.assertEqual(len(ler_pasta(self.troca, AGORA).lidos), 1)
        r = processar(self.troca, self.saida, AGORA)
        self.assertEqual((r["fichas"], r["rejeitados"]), (1, 0))

    def test_contrato_1_1_reserva_o_provider_exclusivamente_para_a_curadoria_manual(self):
        for tipo in "AB":
            r = validar_produto(agente(tipo), AGORA, contrato="1.1")
            self.assertFalse(r.ok)
            self.assertTrue(any("reservado exclusivamente" in e for e in r.erros), r.erros)
        self.assertTrue(validar_produto(curadoria(), AGORA, contrato="1.1").ok)

    def test_leitor_1_1_recusa_fonte_do_agente_com_provider_reservado(self):
        gravar_lote(self.exp_b, {"b.json": agente("B")})
        l = ler_lote(self.exp_b, AGORA, "B")
        self.assertEqual(([x.arquivo for x in l.leitura.lidos], [r.destino for r in l.leitura.rejeitados]), ([], ["rejeitado"]))

    def test_curadoria_manual_exige_o_provider_reservado_no_1_1(self):
        for ruim in ("EXEMPLO_B", "curadoria", "CURADORIA2"):
            self.assertFalse(validar_produto(curadoria(product__provider=ruim), AGORA, contrato="1.1").ok, ruim)

    @property
    def exp_b(self):
        return self.tmp / "exp" / "B"


class FonteCuradoriaNoModo10Test(Base):
    def test_modo_1_0_continua_rejeitando_a_fonte_curadoria_manual(self):
        for contrato in ({}, {"contrato": "1.0"}):
            r = validar_produto(curadoria(), AGORA, **contrato)
            self.assertFalse(r.ok)
            e = " | ".join(r.erros)
            self.assertIn("source.kind", e)
            self.assertIn("source.system", e)

    def test_modo_1_0_rejeita_cada_elemento_da_curadoria_isoladamente(self):
        # kind sozinho, system sozinho e preço nulo sozinho (com o resto válido para o agente)
        self.assertFalse(validar_produto(produto_b(4, "B001", source__kind="curadoria_manual"), AGORA).ok)
        self.assertFalse(validar_produto(produto_b(4, "B001", source__system=SISTEMA_CURADORIA), AGORA).ok)
        self.assertFalse(validar_produto(produto_b(4, "B001", price__amountCents=None), AGORA).ok)

    def test_modo_1_0_rejeita_curadoria_com_provider_reservado_pela_fonte_e_nao_pelo_nome(self):
        r = validar_produto(curadoria(), AGORA)
        self.assertFalse(any("provider" in e for e in r.erros), r.erros)          # o provider em si é aceito no 1.0

    def test_leitor_do_modo_1_0_rejeita_o_arquivo_de_curadoria(self):
        self.troca.joinpath("c.json").write_text(__import__("json").dumps(curadoria()))
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual((lei.lidos, [r.destino for r in lei.rejeitados]), ([], ["rejeitado"]))


if __name__ == "__main__":
    unittest.main()
