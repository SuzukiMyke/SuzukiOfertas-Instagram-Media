"""P-02: seleção explícita de contrato para a futura entrada de dados reais; CLI 1.0 preservado."""
import contextlib
import io
import unittest

from produtos import selecao_contrato as sc
from produtos.__main__ import main
from produtos.tests.base import EXEMPLOS, Base


class SelecaoTest(Base):
    def test_dados_reais_exigem_contrato_sem_padrao(self):
        with self.assertRaises(sc.SelecaoInvalida) as c:
            sc.selecionar(None, False, True)
        self.assertIn("--contrato", str(c.exception))

    def test_contrato_1_0_com_dados_reais_exige_legado(self):
        with self.assertRaises(sc.SelecaoInvalida):
            sc.selecionar("1.0", False, True)
        self.assertEqual(sc.selecionar("1.0", True, True), {"contrato": "1.0", "legado": True, "dadosReais": True})

    def test_contrato_1_1_com_dados_reais_e_valido_e_legado_nao_combina_com_1_1(self):
        self.assertEqual(sc.selecionar("1.1", False, True)["contrato"], "1.1")
        for dr in (True, False):
            with self.assertRaises(sc.SelecaoInvalida):
                sc.selecionar("1.1", True, dr)

    def test_contrato_desconhecido(self):
        for ruim in ("2.0", "", "1", "1.1.0"):
            with self.assertRaises(sc.SelecaoInvalida):
                sc.selecionar(ruim)

    def test_fora_de_dados_reais_nada_muda(self):
        self.assertEqual(sc.selecionar(None), {"contrato": "1.0", "legado": False, "dadosReais": False})
        self.assertEqual(sc.selecionar("1.0")["contrato"], "1.0")
        self.assertEqual(sc.selecionar("1.1")["contrato"], "1.1")

    def test_processamento_real_esta_desabilitado_nesta_etapa(self):
        self.assertIs(sc.DADOS_REAIS_HABILITADO, False)


class CliP02Test(Base):
    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_dados_reais_sem_contrato_ou_1_0_sem_legado_sao_recusados(self):
        self.assertEqual(self.cli("--dados-reais", "--saida", str(self.saida))[0], 2)
        rc, _, err = self.cli("--dados-reais", "--contrato", "1.0", "--saida", str(self.saida))
        self.assertEqual(rc, 2)
        self.assertIn("--legado", err)

    def test_legado_com_1_1_e_recusado(self):
        self.assertEqual(self.cli("--legado", "--contrato", "1.1", "--dados", str(self.tmp), "--saida", str(self.saida))[0], 2)

    def test_selecao_valida_ainda_nao_processa_dados_reais(self):
        for extra in (("--contrato", "1.1", "--dados", str(self.tmp / "nao_existe")), ("--contrato", "1.0", "--legado")):
            rc, out, err = self.cli("--dados-reais", "--saida", str(self.saida), *extra)
            self.assertEqual(rc, 3, extra)
            self.assertIn("DESABILITADA", err)
            self.assertEqual(out, "")
            self.assertFalse(self.saida.exists(), "nada pode ser lido nem gravado")

    def test_cli_1_0_atual_continua_igual_com_e_sem_legado(self):
        base = ["--troca", str(EXEMPLOS / "troca"), "--decisoes", str(EXEMPLOS / "decisoes" / "decisoes_exemplo.json"),
                "--agora", "2026-11-17T15:00:00Z"]
        r0 = self.cli(*base, "--saida", str(self.tmp / "s0"))
        r1 = self.cli(*base, "--legado", "--saida", str(self.tmp / "s1"))
        r2 = self.cli(*base, "--contrato", "1.0", "--legado", "--saida", str(self.tmp / "s2"))
        self.assertEqual((r0[0], r1[0], r2[0]), (0, 0, 0))
        self.assertEqual(r0[1], r1[1])
        self.assertEqual(r0[1], r2[1])


if __name__ == "__main__":
    unittest.main()
