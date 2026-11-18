"""O exportador e a CLI não oferecem caminho para contornar os bloqueios de produtos reais e de dados reais."""
import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from curadoria_b import __main__ as cli_cur
from curadoria_b import exportador, ficha as fch
from produtos import selecao_contrato
from produtos.__main__ import main as cli_receptor
from produtos.tests.base import Base

RAIZ = Path(__file__).resolve().parents[2]
EXEMPLO = RAIZ / "curadoria_b" / "exemplos_ficticios" / "ficha_valida.json"
REAL = {"officialUrl": "https://www.loja-real.com.br/produto/1", "fatos": [{"text": "Capacidade de 5 litros",
        "sourceRef": "https://www.fabricante-real.com.br/manual", "verifiedAt": "2026-11-16T12:00:00Z"}],
        "referencias": [{"label": "Página", "url": "https://www.loja-real.com.br/produto/1"}]}


class BloqueiosCliTest(Base):
    def rodar(self, mod, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = mod(list(args))
            except SystemExit as e:                                   # argparse recusando argumento desconhecido
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def ficha_real(self):
        d = json.loads(EXEMPLO.read_text(encoding="utf-8"))
        d.update(REAL)
        p = self.tmp / "real.json"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return p

    def test_constantes_de_bloqueio_continuam_desabilitadas(self):
        self.assertIs(fch.PRODUTOS_REAIS_HABILITADO, False)
        self.assertIs(selecao_contrato.DADOS_REAIS_HABILITADO, False)

    def test_cli_da_curadoria_nao_tem_opcao_para_habilitar_nada(self):
        import argparse
        capturado = {}
        original = argparse.ArgumentParser.parse_args

        def espiao(self, args=None, namespace=None):
            capturado["opcoes"] = sorted(o for a in self._actions for o in a.option_strings)
            return original(self, args, namespace)
        with mock.patch.object(argparse.ArgumentParser, "parse_args", espiao):
            self.rodar(cli_cur.main, str(EXEMPLO), "--saida", str(self.tmp / "s"), "--agora", "2026-11-17T15:00:00Z")
        self.assertEqual(capturado["opcoes"], sorted(["--agora", "--export-id", "--saida", "-h", "--help"]))
        for flag in ("--reais", "--produtos-reais", "--dados-reais", "--habilitar", "--forcar", "--real"):
            rc, _, _ = self.rodar(cli_cur.main, str(EXEMPLO), "--saida", str(self.tmp / "s2"), flag)
            self.assertEqual(rc, 2, flag)                              # argparse: argumento desconhecido
            self.assertFalse((self.tmp / "s2").exists())

    def test_cli_recusa_dominio_real_e_nao_cria_lote(self):
        rc, _, err = self.rodar(cli_cur.main, str(self.ficha_real()), "--saida", str(self.tmp / "lote"), "--agora", "2026-11-17T15:00:00Z")
        self.assertEqual(rc, 2)
        self.assertIn("produtos reais estão desabilitados", err)
        self.assertFalse((self.tmp / "lote" / "B").exists())

    def test_variaveis_de_ambiente_nao_contornam_o_bloqueio(self):
        env = {"PRODUTOS_REAIS_HABILITADO": "1", "DADOS_REAIS_HABILITADO": "1", "PRODUTOS_REAIS": "true", "HABILITAR": "1"}
        with mock.patch.dict(os.environ, env):
            rc, _, _ = self.rodar(cli_cur.main, str(self.ficha_real()), "--saida", str(self.tmp / "lote"), "--agora", "2026-11-17T15:00:00Z")
            rc2, _, _ = self.rodar(cli_receptor, "--dados-reais", "--contrato", "1.1", "--dados", str(self.tmp), "--saida", str(self.tmp / "o"))
        self.assertEqual((rc, rc2), (2, 3))
        self.assertFalse((self.tmp / "lote" / "B").exists())

    def test_modulos_nao_leem_ambiente_nem_arquivo_de_configuracao(self):
        for arq in (RAIZ / "curadoria_b").glob("*.py"):
            fonte = arq.read_text(encoding="utf-8")
            for p in ("os.environ", "getenv", "configparser", "dotenv"):
                self.assertNotIn(p, fonte, (arq.name, p))

    def test_exportador_nao_importa_nem_altera_a_selecao_de_dados_reais(self):
        fonte = (RAIZ / "curadoria_b" / "exportador.py").read_text(encoding="utf-8") + (RAIZ / "curadoria_b" / "__main__.py").read_text(encoding="utf-8")
        self.assertNotIn("selecao_contrato", fonte)
        self.assertNotIn("DADOS_REAIS_HABILITADO", fonte)
        self.assertNotIn("PRODUTOS_REAIS_HABILITADO =", fonte)

    def test_funcao_exportar_tambem_aplica_o_bloqueio(self):
        from curadoria_b.ficha import ErroFicha
        from produtos.tests.base import AGORA
        with self.assertRaises(ErroFicha):
            exportador.exportar(self.ficha_real(), self.tmp / "lote2", AGORA)
        self.assertFalse((self.tmp / "lote2" / "B").exists())

    def test_receptor_continua_recusando_dados_reais_mesmo_com_lote_da_curadoria(self):
        rc, _, _ = self.rodar(cli_cur.main, str(EXEMPLO), "--saida", str(self.tmp / "lote"), "--agora", "2026-11-17T15:00:00Z")
        self.assertEqual(rc, 0)
        for extra in (["--contrato", "1.1"], ["--contrato", "1.1", "--legado"]):
            rc, out, err = self.rodar(cli_receptor, "--dados-reais", *extra, "--dados", str(self.tmp / "lote"),
                                      "--saida", str(self.tmp / "saida_receptor"))
            self.assertIn(rc, (2, 3))
            self.assertEqual(out, "")
        rc, _, err = self.rodar(cli_receptor, "--dados-reais", "--contrato", "1.1", "--dados", str(self.tmp / "lote"),
                                "--saida", str(self.tmp / "saida_receptor"))
        self.assertEqual(rc, 3)
        self.assertIn("DESABILITADA", err)
        self.assertFalse((self.tmp / "saida_receptor").exists(), "nada foi lido nem gravado")


if __name__ == "__main__":
    unittest.main()
