"""Teste 4: pasta de troca — tmp ignorado, manifesto, truncado, originais intactos."""
import hashlib
import json
import os
import unittest

from produtos.leitor import ler_pasta
from produtos.pipeline import processar
from produtos.tests.base import AGORA, Base, escrever, produto_a, produto_b


def instantaneo(pasta):
    """Nome -> (sha256, mtime_ns, modo) de tudo na pasta (para provar que nada foi tocado)."""
    snap = {}
    for p in sorted(pasta.rglob("*")):
        st = p.lstat()
        snap[str(p.relative_to(pasta))] = (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None,
                                           st.st_mtime_ns, st.st_mode)
    return snap


def manifesto(pasta, ajustes=None, **extra):
    itens = []
    for p in sorted(pasta.glob("*.json")):
        if p.name == "manifest.json" or p.name.startswith("."):
            continue
        h = (ajustes or {}).get(p.name, hashlib.sha256(p.read_bytes()).hexdigest())
        itens.append({"name": p.name, "sha256": h})
    obj = {"manifestVersion": "1.0", "count": len(itens), "files": itens}
    obj.update(extra)
    escrever(pasta, "manifest.json", obj)


class LeitorTest(Base):
    def test_le_validos_em_ordem_deterministica(self):
        escrever(self.troca, "produto_b.json", produto_b())
        escrever(self.troca, "produto_a.json", produto_a())
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual([l.arquivo for l in lei.lidos], ["produto_a.json", "produto_b.json"])
        self.assertEqual(lei.rejeitados, [])
        self.assertFalse(lei.manifesto_presente)

    def test_ignora_tmp_ocultos_nao_json_e_subpastas(self):
        escrever(self.troca, "produto_a.json", produto_a())
        escrever(self.troca, "produto_x.json.tmp", produto_a(2, "A002"))
        escrever(self.troca, ".oculto.json", produto_a(3, "A003"))
        escrever(self.troca, "notas.txt", "x")
        escrever(self.troca, "PRODUTO.JSON", produto_a(4, "A004"))        # extensão diferente (.JSON)
        (self.troca / "sub").mkdir()
        escrever(self.troca / "sub", "produto_z.json", produto_a(5, "A005"))
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual([l.arquivo for l in lei.lidos], ["produto_a.json"])
        self.assertEqual(lei.rejeitados, [])
        self.assertEqual(sorted(lei.ignorados), [".oculto.json", "PRODUTO.JSON", "notas.txt", "produto_x.json.tmp", "sub"])

    def test_link_simbolico_e_ignorado(self):
        alvo = escrever(self.tmp, "fora.json", produto_a())
        os.symlink(alvo, self.troca / "link.json")
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual(lei.lidos, [])
        self.assertIn("link.json", lei.ignorados)

    def test_json_truncado_vai_para_quarentena(self):
        completo = json.dumps(produto_a())
        escrever(self.troca, "truncado.json", completo[: len(completo) // 2])
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual(lei.lidos, [])
        self.assertEqual(lei.rejeitados[0].destino, "quarentena")
        self.assertIn("truncado", lei.rejeitados[0].motivos[0])

    def test_json_estrito_chave_duplicada_nan_e_utf8(self):
        escrever(self.troca, "dup.json", '{"schemaVersion":"1.0.0","schemaVersion":"1.0.0","exportId":"x"}')
        escrever(self.troca, "nan.json", '{"schemaVersion": NaN}')
        (self.troca / "latin.json").write_bytes('{"a": "ç"}'.encode("latin-1"))
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual(sorted(r.arquivo for r in lei.rejeitados), ["dup.json", "latin.json", "nan.json"])
        self.assertTrue(all(r.destino == "quarentena" for r in lei.rejeitados))

    def test_arquivo_grande_demais_e_recusado(self):
        escrever(self.troca, "grande.json", "x" * (300 * 1024))
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual(lei.rejeitados[0].destino, "quarentena")

    def test_manifesto_correto_aceita(self):
        escrever(self.troca, "a.json", produto_a())
        manifesto(self.troca)
        lei = ler_pasta(self.troca, AGORA)
        self.assertTrue(lei.manifesto_presente)
        self.assertEqual([l.arquivo for l in lei.lidos], ["a.json"])
        self.assertEqual(lei.avisos, [])

    def test_manifesto_com_hash_errado_vai_para_quarentena(self):
        escrever(self.troca, "a.json", produto_a())
        escrever(self.troca, "b.json", produto_b())
        manifesto(self.troca, ajustes={"b.json": "0" * 64})
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual([l.arquivo for l in lei.lidos], ["a.json"])
        self.assertEqual([(r.arquivo, r.destino) for r in lei.rejeitados], [("b.json", "quarentena")])
        self.assertIn("SHA-256", lei.rejeitados[0].motivos[0])

    def test_arquivo_nao_listado_no_manifesto_fica_em_quarentena(self):
        escrever(self.troca, "a.json", produto_a())
        manifesto(self.troca)
        escrever(self.troca, "novo.json", produto_b())                      # chegou depois do manifesto
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual([r.arquivo for r in lei.rejeitados], ["novo.json"])
        self.assertIn("não listado", lei.rejeitados[0].motivos[0])

    def test_manifesto_invalido_poe_tudo_em_quarentena(self):
        escrever(self.troca, "a.json", produto_a())
        escrever(self.troca, "manifest.json", "{quebrado")
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual(lei.lidos, [])
        self.assertEqual([r.destino for r in lei.rejeitados], ["quarentena"])
        self.assertTrue(lei.avisos)

    def test_manifesto_avisa_arquivo_ausente_e_contagem(self):
        escrever(self.troca, "a.json", produto_a())
        manifesto(self.troca)
        m = json.loads((self.troca / "manifest.json").read_text())
        m["files"].append({"name": "sumiu.json", "sha256": "1" * 64})
        escrever(self.troca, "manifest.json", m)
        lei = ler_pasta(self.troca, AGORA)
        self.assertEqual(len(lei.lidos), 1)
        self.assertTrue(any("sumiu.json" in a for a in lei.avisos))
        self.assertTrue(any("contagem" in a for a in lei.avisos))

    def test_pasta_inexistente(self):
        with self.assertRaises(FileNotFoundError):
            ler_pasta(self.tmp / "nao_existe", AGORA)

    def test_arquivos_originais_ficam_intactos(self):
        escrever(self.troca, "a.json", produto_a())
        escrever(self.troca, "x.json.tmp", "{")
        escrever(self.troca, "trunc.json", "{")
        escrever(self.troca, "proibido.json", produto_a(2, "A002", telegramUpdateId=1))
        manifesto(self.troca, ajustes={"a.json": "0" * 64})
        antes = instantaneo(self.troca)
        ler_pasta(self.troca, AGORA)
        processar(self.troca, self.saida, AGORA)
        self.assertEqual(instantaneo(self.troca), antes)
        self.assertFalse(list(self.troca.glob("*quarentena*")))

    def test_saida_dentro_da_troca_e_recusada(self):
        escrever(self.troca, "a.json", produto_a())
        with self.assertRaises(ValueError):
            processar(self.troca, self.troca / "saida", AGORA)
        with self.assertRaises(ValueError):
            processar(self.troca, self.troca, AGORA)
        with self.assertRaises(ValueError):                                # saída que contém a troca como 'fichas'
            processar(self.troca.parent, self.troca.parent, AGORA)

    def test_relatorio_de_rejeitados_nao_copia_conteudo(self):
        escrever(self.troca, "proibido.json", produto_a(telegramUpdateId=987654321))
        processar(self.troca, self.saida, AGORA)
        rel = (self.saida / "rejeitados.json").read_text(encoding="utf-8")
        self.assertNotIn("987654321", rel)
        self.assertIn("campo proibido", rel)


if __name__ == "__main__":
    unittest.main()
