"""Modo 1.1 ponta a ponta: pipeline, CLI, somente leitura (S2), fragmento (§8.8) e garantias estáticas."""
import contextlib
import io
import json
import re
import shutil
import unittest
from pathlib import Path

from produtos import estados
from produtos.__main__ import main
from produtos.avaliacao_v11 import ConfiguracaoV11
from produtos.pipeline_v11 import processar_v11
from produtos.reel_fragmento import FragmentoRecusado
from produtos.reel_fragmento_v11 import ficha_para_fragmento_v11
from produtos.tests.base import AGORA, EXEMPLOS
from produtos.tests.base_v11 import BaseV11, FOTO_SHA, gravar_lote, instantaneo, produto_a, produto_b

EX11 = EXEMPLOS.parent / "exemplos_ficticios_v1_1"
PACOTE = Path(__file__).resolve().parents[1]


def args_ex11(saida, *extra):
    return ["--contrato", "1.1", "--dados", str(EX11 / "exportacoes"), "--decisoes", str(EX11 / "decisoes" / "decisoes.json"),
            "--permissoes", str(EX11 / "decisoes" / "permissoes_fotos.json"), "--termos", str(EX11 / "decisoes" / "termos_programas.json"),
            "--fotos-dir", str(EX11 / "fotos"), "--saida", str(saida), "--agora", "2026-11-17T15:00:00Z", *extra]


class ExemploCompletoTest(BaseV11):
    def rodar_exemplo(self, **kw):
        return processar_v11(EX11 / "exportacoes", self.saida, AGORA, decisoes_arquivo=EX11 / "decisoes" / "decisoes.json",
                             permissoes_arquivo=EX11 / "decisoes" / "permissoes_fotos.json",
                             termos_arquivo=EX11 / "decisoes" / "termos_programas.json", fotos_dir=EX11 / "fotos", **kw)

    def test_exemplo_fictício_completo(self):
        antes = instantaneo(EX11)
        r = self.rodar_exemplo(commits_lidos={"dados": "abc1234", "decisoes": "def5678", "fotos": "0123456789abcdef"})
        self.assertEqual(r["contrato"], "1.1")
        self.assertEqual(r["fichasPorEstado"], {"aprovado_para_rascunho": 2, "incompleto": 1})
        self.assertEqual({l: r["lotes"][l]["status"] for l in "AB"}, {"A": "ok", "B": "ok"})
        self.assertTrue(all(r["lotes"][l]["manifestoPresente"] for l in "AB"))
        self.assertEqual(r["commitsLidos"], {"dados": "abc1234", "decisoes": "def5678", "fotos": "0123456789abcdef"})
        self.assertIn("nao_verificavel", r["verificacoes"]["autoriaDeCommit"])
        self.assertIn("inexistente", r["verificacoes"]["reverificacaoNoMomentoDaPublicacao"])
        self.assertEqual(r["parametros"]["tetoRevalidacaoHoras"], 24)
        self.assertEqual(instantaneo(EX11), antes, "as entradas (somente leitura) foram alteradas")

    def test_saida_so_na_pasta_de_saida_e_deterministica(self):
        self.rodar_exemplo()
        a = instantaneo(self.saida)
        shutil.rmtree(self.saida)
        self.rodar_exemplo()
        self.assertEqual({k: v[0] for k, v in a.items()}, {k: v[0] for k, v in instantaneo(self.saida).items()})

    def test_ficha_a_com_foto_humana_e_b_sem_preco(self):
        self.rodar_exemplo()
        a = json.loads((self.saida / "fichas" / "EXEMPLO_A__A001.json").read_text())
        b = json.loads((self.saida / "fichas" / "EXEMPLO_B__B001.json").read_text())
        self.assertEqual((a["contrato"], a["fichaVersion"], a["foto"]["utilizavel"], a["foto"]["termoId"]), ("1.1", "1.1.0", True, "T-FICT-001"))
        self.assertIsNone(b["preco"]["exibicao"])
        self.assertEqual(b["estado"], estados.APROVADO_RASCUNHO)
        self.assertIn("1.1", (self.saida / "fichas" / "EXEMPLO_A__A001.md").read_text())

    def test_lote_sem_manifesto_nao_gera_fichas_e_aparece_no_relatorio(self):
        gravar_lote(self.exp / "A", {"a.json": produto_a(1, "A001")}, manifesto=False)
        gravar_lote(self.exp / "B", {"b.json": produto_b(4, "B001")})
        r, f = self.rodar()
        self.assertEqual(set(f), {"EXEMPLO_B__B001"})
        self.assertEqual(r["lotes"]["A"]["status"], "quarentena_de_lote")
        rej = json.loads((self.saida / "rejeitados.json").read_text())
        self.assertEqual([(x["lote"], x["destino"]) for x in rej], [("A", "quarentena")])

    def test_saida_dentro_ou_acima_de_qualquer_entrada_e_recusada(self):
        h = self.humanos()
        gravar_lote(self.exp / "A", {"a.json": produto_a(1, "A001")})
        for ruim in (self.exp / "saida", self.fotos / "x", self.tmp, self.hum / "decisoes.json"):
            with self.assertRaises(ValueError, msg=str(ruim)):
                processar_v11(self.exp, ruim, AGORA, **h)

    def test_commits_invalidos_sao_recusados(self):
        gravar_lote(self.exp / "A", {"a.json": produto_a(1, "A001")})
        for ruim in ({"outro": "abc1234"}, {"dados": "não-é-hex"}, {"dados": "abc"}, {"dados": 123}):
            with self.assertRaises(ValueError):
                processar_v11(self.exp, self.saida, AGORA, commits_lidos=ruim)

    def test_configuracao_do_modo_1_0_nao_e_aceita_no_modo_1_1(self):
        from produtos.avaliacao import Configuracao
        with self.assertRaises(ValueError):
            processar_v11(EX11 / "exportacoes", self.saida, AGORA, cfg=Configuracao())

    def test_sem_arquivos_humanos_nada_e_aprovado_nem_ha_foto(self):
        gravar_lote(self.exp / "A", {"a.json": produto_a(1, "A001")})
        r = processar_v11(self.exp, self.saida, AGORA)
        self.assertEqual(r["fichasPorEstado"], {"incompleto": 1})
        self.assertIn("nao_informado", r["verificacoes"]["repositorioDeFotos"])


class CliV11Test(BaseV11):
    def cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_cli_1_1(self):
        rc, out, _ = self.cli(args_ex11(self.saida, "--commit-dados", "abc1234"))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["commitsLidos"], {"dados": "abc1234"})

    def test_cli_1_1_exige_dados_e_recusa_janela_maior_que_24h(self):
        self.assertEqual(self.cli(["--contrato", "1.1", "--saida", str(self.saida)])[0], 2)
        rc, _, err = self.cli(args_ex11(self.saida, "--revalidacao-horas", "48"))
        self.assertEqual(rc, 2)
        self.assertIn("24", err)

    def test_cli_1_1_com_saida_dentro_da_entrada_e_recusada(self):
        rc, _, err = self.cli(args_ex11(EX11 / "exportacoes" / "saida"))
        self.assertEqual(rc, 2)
        self.assertFalse((EX11 / "exportacoes" / "saida").exists())


class FragmentoV11Test(BaseV11):
    FOTO_REPO = "produtos/exemplos_ficticios_v1_1/fotos/fotos"

    def ficha(self):
        r = processar_v11(EX11 / "exportacoes", self.saida, AGORA, decisoes_arquivo=EX11 / "decisoes" / "decisoes.json",
                          permissoes_arquivo=EX11 / "decisoes" / "permissoes_fotos.json",
                          termos_arquivo=EX11 / "decisoes" / "termos_programas.json", fotos_dir=EX11 / "fotos")
        return json.loads((self.saida / "fichas" / "EXEMPLO_A__A001.json").read_text()), r

    def foto_local(self, ficha):
        return f"{self.FOTO_REPO}/{ficha['foto']['fotoSha256']}.jpg"

    def test_fragmento_com_hash_confere_e_licenca_vem_do_termo(self):
        f, _ = self.ficha()
        r = ficha_para_fragmento_v11(f, self.foto_local(f))
        lic = r["fragmento"]["scenes"][0]["source"]["license"]
        self.assertIn("T-FICT-001", lic)
        self.assertNotIn("termo-ficticio-001", lic)                  # nunca a referência vinda do arquivo do agente
        self.assertNotIn("price", r["fragmento"]["scenes"][0])

    def test_hash_do_arquivo_local_diverge(self):
        f, _ = self.ficha()
        with self.assertRaises(FragmentoRecusado) as c:
            ficha_para_fragmento_v11(f, "produtos/exemplos_ficticios_v1_1/fotos/evidencias/termo_ficticio_001.txt")
        self.assertIn("diverge", str(c.exception))

    def test_recusas(self):
        f, _ = self.ficha()
        for mod, msg in ((lambda x: x.update(contrato="1.0"), "1.1"),
                         (lambda x: x["foto"].update(utilizavel=False), "sem foto"),
                         (lambda x: x.update(estado=estados.PENDENTE_REVISAO), "aprovação humana")):
            c = json.loads(json.dumps(f))
            mod(c)
            with self.assertRaises(FragmentoRecusado, msg=msg):
                ficha_para_fragmento_v11(c, self.foto_local(f))
        for ruim in (None, "/etc/passwd", "../x.jpg", "produtos/nao_existe.jpg"):
            with self.assertRaises(FragmentoRecusado):
                ficha_para_fragmento_v11(f, ruim)

    def test_b_sem_foto_autorizada_nao_gera_fragmento(self):
        _, _ = self.ficha()
        b = json.loads((self.saida / "fichas" / "EXEMPLO_B__B001.json").read_text())
        with self.assertRaises(FragmentoRecusado):
            ficha_para_fragmento_v11(b, f"{self.FOTO_REPO}/{FOTO_SHA}.jpg")


class GarantiasEstaticasV11Test(BaseV11):
    NOVOS = ("leitor_v11", "avaliacao_v11", "fichas_v11", "pipeline_v11", "permissoes", "prepublicacao",
             "politica_titulos", "reel_fragmento_v11")
    SOMENTE_LEITURA = ("leitor_v11", "avaliacao_v11", "permissoes", "prepublicacao", "politica_titulos", "reel_fragmento_v11")

    def test_modulos_de_leitura_nao_escrevem_nem_apagam(self):
        for m in self.SOMENTE_LEITURA:
            fonte = (PACOTE / f"{m}.py").read_text(encoding="utf-8")
            for proibido in (".write_text", ".write_bytes", ".unlink", ".rename", ".replace(", ".mkdir", "open(", "rmtree", ".touch"):
                self.assertNotIn(proibido, fonte, (m, proibido))

    def test_novos_modulos_sem_rede_ambiente_ou_termos_proibidos(self):
        for m in self.NOVOS:
            fonte = (PACOTE / f"{m}.py").read_text(encoding="utf-8")
            for p in ("os.environ", "getenv", "os.system", "Popen", "urlopen", "subprocess", "socket", "requests", "token", "senha"):
                self.assertNotRegex(fonte, rf"(?<![A-Za-z]){re.escape(p)}", (m, p))

    def test_arquivos_do_modo_1_0_nao_foram_reescritos(self):
        for m, trecho in (("pipeline", 'cfg.contrato != "1.0"'), ("avaliacao", 'contrato: str = "1.0"')):
            self.assertIn(trecho, (PACOTE / f"{m}.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
