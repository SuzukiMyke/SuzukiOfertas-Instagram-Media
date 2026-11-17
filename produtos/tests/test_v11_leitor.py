"""Modo 1.1: manifesto obrigatório por pasta A e B; quarentena de lote (contrato §2/S4)."""
import json
import unittest

from produtos.leitor import ler_pasta
from produtos.leitor_v11 import ler_lote
from produtos.tests.base_v11 import AGORA, BaseV11, gravar_lote, instantaneo, produto_a, produto_b


def lote_a(self, **kw):
    return gravar_lote(self.exp / "A", {"a1.json": produto_a(1, "A001"), "a2.json": produto_a(2, "A002")}, **kw)


class LeitorV11Test(BaseV11):
    def test_lote_integro_e_lido(self):
        lote_a(self)
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual((l.status, l.manifesto_presente, [x.arquivo for x in l.leitura.lidos]), ("ok", True, ["a1.json", "a2.json"]))

    def test_sem_manifesto_quarentena_do_lote_inteiro(self):
        lote_a(self, manifesto=False)
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []))
        self.assertEqual({r.destino for r in l.leitura.rejeitados}, {"quarentena"})
        self.assertEqual(len(l.leitura.rejeitados), 2)
        self.assertIn("manifest.json ausente", l.motivos[0])

    def test_cada_pasta_exige_o_proprio_manifesto(self):
        lote_a(self)
        gravar_lote(self.exp / "B", {"b1.json": produto_b(4, "B001")}, manifesto=False)
        a, b = ler_lote(self.exp / "A", AGORA, "A"), ler_lote(self.exp / "B", AGORA, "B")
        self.assertEqual((a.status, len(a.leitura.lidos)), ("ok", 2))
        self.assertEqual((b.status, b.leitura.lidos), ("quarentena_de_lote", []))

    def test_manifesto_na_raiz_nao_vale_para_as_pastas(self):
        lote_a(self, manifesto=False)
        (self.exp / "manifest.json").write_text(json.dumps({"manifestVersion": "1.0", "count": 0, "files": []}))
        self.assertEqual(ler_lote(self.exp / "A", AGORA, "A").status, "quarentena_de_lote")

    def test_manifesto_ilegivel_invalido_e_simbolico(self):
        for conteudo in ("{truncado", json.dumps({"count": 1}), json.dumps({"count": 1, "files": [{"name": "a1.json"}]})):
            lote_a(self, manifesto=False)
            (self.exp / "A" / "manifest.json").write_text(conteudo)
            l = ler_lote(self.exp / "A", AGORA, "A")
            self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []), conteudo)
        (self.exp / "A" / "manifest.json").unlink()
        (self.exp / "A" / "manifest.json").symlink_to(self.exp / "A" / "a1.json")
        self.assertEqual(ler_lote(self.exp / "A", AGORA, "A").status, "quarentena_de_lote")

    def test_inconsistencias_levam_o_lote_inteiro_a_quarentena(self):
        base = {"manifestVersion": "1.0", "generatedAt": "2026-11-17T12:00:00Z"}
        a1, a2 = (produto_a(1, "A001"), produto_a(2, "A002"))
        import hashlib
        h = lambda o: hashlib.sha256(json.dumps(o, ensure_ascii=False).encode()).hexdigest()
        n = lambda o: len(json.dumps(o, ensure_ascii=False).encode())
        casos = {
            "contagem": {**base, "count": 5, "files": [{"name": "a1.json", "sha256": h(a1), "bytes": n(a1)}, {"name": "a2.json", "sha256": h(a2), "bytes": n(a2)}]},
            "listado_ausente": {**base, "count": 3, "files": [{"name": "a1.json", "sha256": h(a1), "bytes": n(a1)}, {"name": "a2.json", "sha256": h(a2), "bytes": n(a2)},
                                                              {"name": "a3.json", "sha256": "0" * 64, "bytes": 10}]},
            "nao_listado": {**base, "count": 1, "files": [{"name": "a1.json", "sha256": h(a1), "bytes": n(a1)}]},
            "hash": {**base, "count": 2, "files": [{"name": "a1.json", "sha256": "f" * 64, "bytes": n(a1)}, {"name": "a2.json", "sha256": h(a2), "bytes": n(a2)}]},
        }
        for nome, m in casos.items():
            lote_a(self, manifesto=m)
            l = ler_lote(self.exp / "A", AGORA, "A")
            self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []), nome)

    def test_arquivo_alterado_depois_do_manifesto(self):
        lote_a(self)
        with open(self.exp / "A" / "a1.json", "a") as f:
            f.write(" ")
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []))
        self.assertTrue(any("SHA-256 diverge" in m for m in l.motivos))

    def test_pasta_ausente_ou_vazia_nao_e_quarentena(self):
        self.exp.mkdir()
        self.assertEqual(ler_lote(self.exp / "A", AGORA, "A").status, "pasta_ausente")
        (self.exp / "B").mkdir()
        self.assertEqual(ler_lote(self.exp / "B", AGORA, "B").status, "vazio")

    def test_fonte_na_pasta_errada_vai_para_quarentena_do_arquivo(self):
        gravar_lote(self.exp / "A", {"a1.json": produto_a(1, "A001"), "b1.json": produto_b(4, "B001")})
        gravar_lote(self.exp / "B", {"a9.json": produto_a(9, "A009")})
        a, b = ler_lote(self.exp / "A", AGORA, "A"), ler_lote(self.exp / "B", AGORA, "B")
        self.assertEqual(([x.arquivo for x in a.leitura.lidos], [r.arquivo for r in a.leitura.rejeitados]), (["a1.json"], ["b1.json"]))
        self.assertEqual(([x.arquivo for x in b.leitura.lidos], [r.arquivo for r in b.leitura.rejeitados]), ([], ["a9.json"]))

    def test_arquivo_invalido_dentro_de_lote_integro_nao_derruba_os_outros(self):
        gravar_lote(self.exp / "A", {"a1.json": produto_a(1, "A001"), "ruim.json": b"{truncado"})
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual((l.status, [x.arquivo for x in l.leitura.lidos], l.leitura.rejeitados[0].arquivo), ("ok", ["a1.json"], "ruim.json"))

    def test_somente_leitura_nada_na_pasta_muda(self):
        lote_a(self, manifesto=False)
        antes = instantaneo(self.exp)
        ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual(instantaneo(self.exp), antes)

    def test_modo_1_0_continua_aceitando_ausencia_de_manifesto(self):
        """Regressão/compatibilidade: o leitor v1 não mudou (T10 da prova de transporte registrou essa divergência)."""
        lote_a(self, manifesto=False)
        lei = ler_pasta(self.exp / "A", AGORA)
        self.assertEqual((lei.manifesto_presente, len(lei.lidos)), (False, 2))


if __name__ == "__main__":
    unittest.main()
