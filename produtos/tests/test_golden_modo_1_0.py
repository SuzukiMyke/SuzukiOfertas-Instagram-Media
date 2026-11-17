"""Regressão do modo 1.0 (contrato v1.1 §11): saída idêntica byte a byte aos hashes golden gravados em b317f17."""
import contextlib
import io
import json
import unittest

from produtos.__main__ import main
from produtos.avaliacao import Configuracao
from produtos.pipeline import processar
from produtos.tests.base import AGORA, EXEMPLOS, Base
from produtos.tests.golden_modo_1_0 import ARQUIVO, CENARIOS, COMMIT_BASE, calcular


class GoldenModo10Test(Base):
    def test_hashes_golden_identicos(self):
        golden = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        self.assertEqual(golden["commitBase"], COMMIT_BASE)
        self.assertEqual(set(golden["cenarios"]), set(CENARIOS))
        atual = calcular()
        for nome, arquivos in golden["cenarios"].items():
            self.assertEqual(atual[nome], arquivos, f"modo 1.0 mudou no cenário {nome}")

    def test_golden_e_deterministico(self):
        self.assertEqual(calcular(), calcular())

    def test_contrato_padrao_continua_1_0_e_recusa_1_1_neste_fluxo(self):
        self.assertEqual(Configuracao().contrato, "1.0")
        with self.assertRaises(ValueError):
            processar(EXEMPLOS / "troca", self.saida, AGORA, cfg=Configuracao(contrato="1.1"))

    def _cli(self, *extra):
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = main(["--troca", str(EXEMPLOS / "troca"), "--decisoes", str(EXEMPLOS / "decisoes" / "decisoes_exemplo.json"),
                       "--saida", str(self.saida), "--agora", "2026-11-17T15:00:00Z", *extra])
        return rc, buf.getvalue(), err.getvalue()

    def test_cli_sem_contrato_e_com_contrato_1_0_sao_identicos(self):
        rc0, out0, _ = self._cli()
        rc1, out1, _ = self._cli("--contrato", "1.0")
        self.assertEqual((rc0, out0), (rc1, out1))
        self.assertNotIn('"contrato"', out0)

    def test_argumentos_do_modo_1_1_sem_contrato_1_1_sao_recusados(self):
        rc, _, err = self._cli("--dados", str(self.tmp))
        self.assertEqual(rc, 2)
        self.assertIn("--contrato 1.1", err)


if __name__ == "__main__":
    unittest.main()
