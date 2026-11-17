"""P-01: manifesto estrito (manifestVersion, generatedAt, count, files[name, sha256, bytes]) por lote A e B."""
import copy
import json
import unittest
from datetime import timedelta

from produtos.leitor import ler_pasta
from produtos.leitor_v11 import ler_lote
from produtos.manifesto_v11 import MAX_ARQUIVOS, ler_manifesto_estrito
from produtos.tests.base_v11 import AGORA, BaseV11, gravar_lote, instantaneo, manifesto_valido, produto_a, produto_b

ARQS = {"a1.json": produto_a(1, "A001"), "a2.json": produto_a(2, "A002")}


class ManifestoEstritoTest(BaseV11):
    def manifesto(self, m, nome="manifest.json"):
        p = self.tmp / nome
        p.write_text(m if isinstance(m, str) else json.dumps(m))
        return p

    def erros(self, m):
        mf, erros = ler_manifesto_estrito(self.manifesto(m), AGORA)
        self.assertIsNone(mf, m)
        self.assertTrue(erros)
        return " | ".join(erros)

    def test_manifesto_valido(self):
        mf, erros = ler_manifesto_estrito(self.manifesto(manifesto_valido(ARQS)), AGORA)
        self.assertEqual((erros, mf.versao, mf.count, sorted(mf.itens)), ([], "1.0", 2, ["a1.json", "a2.json"]))

    def test_cada_campo_obrigatorio_ausente(self):
        for campo in ("manifestVersion", "generatedAt", "count", "files"):
            m = manifesto_valido(ARQS)
            del m[campo]
            self.assertIn(campo, self.erros(m), campo)
        for campo in ("name", "sha256", "bytes"):
            m = manifesto_valido(ARQS)
            del m["files"][0][campo]
            self.assertIn(f"files[0].{campo}", self.erros(m), campo)

    def test_campos_desconhecidos_em_qualquer_nivel(self):
        m = manifesto_valido(ARQS, extra="x")
        self.assertIn("campo desconhecido", self.erros(m))
        m = manifesto_valido(ARQS)
        m["files"][1]["mtime"] = 1
        self.assertIn("files[1]: campo desconhecido", self.erros(m))

    def test_manifest_version(self):
        for ruim in (1, 1.0, None, "", "abc", "1", "1.", "2.0", "0.9", "1.0.0.0", ["1.0"]):
            self.assertIn("manifestVersion", self.erros(manifesto_valido(ARQS, manifestVersion=ruim)), repr(ruim))
        for ok in ("1.0", "1.2", "1.0.3"):
            self.assertIsNotNone(ler_manifesto_estrito(self.manifesto(manifesto_valido(ARQS, manifestVersion=ok)), AGORA)[0], ok)

    def test_generated_at(self):
        for ruim in (None, 0, "ontem", "2026-11-17", "2026-11-17T12:00:00", "2026-11-17T12:00:00-03:00", "2026-13-01T00:00:00Z"):
            self.assertIn("generatedAt", self.erros(manifesto_valido(ARQS, generatedAt=ruim)), repr(ruim))

    def test_generated_at_futuro_com_tolerancia(self):
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        self.assertIn("futuro", self.erros(manifesto_valido(ARQS, generatedAt=(AGORA + timedelta(minutes=6)).strftime(fmt))))
        ok = manifesto_valido(ARQS, generatedAt=(AGORA + timedelta(minutes=5)).strftime(fmt))
        self.assertIsNotNone(ler_manifesto_estrito(self.manifesto(ok), AGORA)[0])

    def test_count(self):
        for ruim in (True, False, -1, "2", 2.0, None):
            self.assertIn("count", self.erros(manifesto_valido(ARQS, count=ruim)), repr(ruim))
        self.assertIn("diverge", self.erros(manifesto_valido(ARQS, count=3)))

    def test_files_e_itens(self):
        self.assertIn("files", self.erros(manifesto_valido(ARQS, files={"a": 1})))
        self.assertIn("files[0]", self.erros(manifesto_valido(ARQS, files=["a1.json"], count=1)))
        m = manifesto_valido({f"a{i}.json": b"{}" for i in range(MAX_ARQUIVOS + 1)})
        self.assertIn("mais de", self.erros(m))

    def test_nomes_invalidos(self):
        for ruim in ("sub/a.json", "..\\a.json", "../a.json", ".oculto.json", "a.txt", "manifest.json", "", "a​.json",
                     "a\n.json", "x" * 201 + ".json", 5, None):
            m = manifesto_valido(ARQS)
            m["files"][0]["name"] = ruim
            self.assertIn("files[0].name", self.erros(m), repr(ruim))

    def test_nome_duplicado(self):
        m = manifesto_valido(ARQS)
        m["files"][1]["name"] = "a1.json"
        self.assertIn("duplicado", self.erros(m))

    def test_sha256_e_bytes(self):
        for ruim in (None, "", "abc", "g" * 64, "a" * 63, "a" * 65, 7):
            m = manifesto_valido(ARQS)
            m["files"][0]["sha256"] = ruim
            self.assertIn("sha256", self.erros(m), repr(ruim))
        for ruim in (None, "10", -1, True, 1.5, 256 * 1024 + 1):
            m = manifesto_valido(ARQS)
            m["files"][0]["bytes"] = ruim
            self.assertIn("bytes", self.erros(m), repr(ruim))
        m = manifesto_valido(ARQS)
        m["files"][0]["sha256"] = m["files"][0]["sha256"].upper()                     # maiúsculas são normalizadas
        self.assertIsNotNone(ler_manifesto_estrito(self.manifesto(m), AGORA)[0])

    def test_formato_estrutural(self):
        for ruim in ("{truncado", "[]", '"texto"', "null", '{"files": [], "files": []}', "﻿{}"):
            self.assertIn("manifesto", self.erros(ruim), ruim)
        grande = self.tmp / "grande.json"
        grande.write_text(" " * (256 * 1024 + 1))
        self.assertIn("maior", ler_manifesto_estrito(grande, AGORA)[1][0])

    def test_mensagens_nao_vazam_valores(self):
        m = manifesto_valido(ARQS)
        m["files"][0]["sha256"] = "SEGREDO-NAO-VAZAR"
        m["extraSEGREDO"] = "x"
        self.assertNotIn("SEGREDO-NAO-VAZAR", self.erros(m))


class LoteComManifestoEstritoTest(BaseV11):
    def lote(self, **over):
        gravar_lote(self.exp / "A", ARQS, manifesto=manifesto_valido(ARQS, **over))
        return ler_lote(self.exp / "A", AGORA, "A")

    def test_lote_conforme_e_lido(self):
        l = self.lote()
        self.assertEqual((l.status, len(l.leitura.lidos)), ("ok", 2))

    def test_campos_faltando_ou_invalidos_poem_o_lote_inteiro_em_quarentena(self):
        for over in (dict(manifestVersion="2.0"), dict(generatedAt="x"), dict(count=3), dict(extra=1)):
            l = self.lote(**over)
            self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []), over)
            self.assertEqual(len(l.leitura.rejeitados), 2)
            self.assertIn("fora do formato do contrato 1.1", l.motivos[0])
        gravar_lote(self.exp / "A", ARQS, manifesto={k: v for k, v in manifesto_valido(ARQS).items() if k != "generatedAt"})
        self.assertEqual(ler_lote(self.exp / "A", AGORA, "A").status, "quarentena_de_lote")

    def test_bytes_divergente_do_conteudo_real(self):
        m = manifesto_valido(ARQS)
        m["files"][0]["bytes"] += 1
        gravar_lote(self.exp / "A", ARQS, manifesto=m)
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []))
        self.assertTrue(any("bytes diverge" in x for x in l.motivos))
        self.assertFalse(any("SHA-256" in x for x in l.motivos))                      # só o bytes divergiu

    def test_sha_e_bytes_divergentes_sao_reportados_juntos(self):
        gravar_lote(self.exp / "A", ARQS)
        with open(self.exp / "A" / "a1.json", "a") as f:
            f.write(" ")
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertTrue(any("bytes diverge" in x for x in l.motivos) and any("SHA-256" in x for x in l.motivos))

    def test_count_diverge_dos_arquivos_presentes(self):
        m = manifesto_valido({"a1.json": ARQS["a1.json"]})                             # manifesto de 1 arquivo, pasta com 2
        gravar_lote(self.exp / "A", ARQS, manifesto=m)
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertTrue(any("count diverge dos arquivos presentes" in x for x in l.motivos))
        self.assertTrue(any("não listado" in x for x in l.motivos))

    def test_cada_lote_tem_o_seu_manifesto_estrito(self):
        gravar_lote(self.exp / "A", ARQS)
        sem_bytes = manifesto_valido({"b.json": produto_b(4, "B001")})
        del sem_bytes["files"][0]["bytes"]
        gravar_lote(self.exp / "B", {"b.json": produto_b(4, "B001")}, manifesto=sem_bytes)
        self.assertEqual(ler_lote(self.exp / "A", AGORA, "A").status, "ok")
        self.assertEqual(ler_lote(self.exp / "B", AGORA, "B").status, "quarentena_de_lote")

    def test_manifesto_do_formato_antigo_e_recusado_no_1_1_mas_aceito_no_1_0(self):
        antigo = {"manifestVersion": "1.0", "count": 2, "files": [{"name": n, "sha256": manifesto_valido(ARQS)["files"][i]["sha256"]}
                                                                  for i, n in enumerate(ARQS)]}
        gravar_lote(self.exp / "A", ARQS, manifesto=antigo)
        self.assertEqual(ler_lote(self.exp / "A", AGORA, "A").status, "quarentena_de_lote")
        self.assertEqual(len(ler_pasta(self.exp / "A", AGORA).lidos), 2)               # modo 1.0 inalterado

    def test_arquivos_de_origem_ficam_intactos_na_quarentena(self):
        gravar_lote(self.exp / "A", ARQS, manifesto=manifesto_valido(ARQS, count=9))
        antes = instantaneo(self.exp)
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual(l.status, "quarentena_de_lote")
        self.assertEqual(instantaneo(self.exp), antes)

    def test_pipeline_registra_quarentena_do_lote_com_motivo_do_formato(self):
        gravar_lote(self.exp / "A", ARQS, manifesto=manifesto_valido(ARQS, manifestVersion="9.9"))
        gravar_lote(self.exp / "B", {"b.json": produto_b(4, "B001")})
        r, f = self.rodar()
        self.assertEqual(r["lotes"]["A"]["status"], "quarentena_de_lote")
        self.assertIn("manifestVersion", " ".join(r["lotes"]["A"]["motivos"]))
        self.assertEqual(set(f), {"EXEMPLO_B__B001"})


if __name__ == "__main__":
    unittest.main()
