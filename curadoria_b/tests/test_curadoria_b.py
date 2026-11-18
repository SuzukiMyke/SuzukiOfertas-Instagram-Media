"""Pacote curadoria_b: ficha humana -> exportação B (contrato 1.1), manifesto estrito, receptor 1.1, bloqueios e determinismo."""
import contextlib
import copy
import hashlib
import io
import json
import re
import unittest
import uuid
from pathlib import Path
from unittest import mock

from curadoria_b import __main__ as cli
from curadoria_b import exportador, ficha as fch
from curadoria_b.exportador import ErroExportacao, construir_lote, exportar
from curadoria_b.ficha import ErroFicha, ler_ficha, para_exportacao
from produtos import estados
from produtos.leitor import ler_pasta
from produtos.leitor_v11 import ler_lote
from produtos.manifesto_v11 import MAX_ARQUIVOS, ler_manifesto_estrito
from produtos.pipeline_v11 import processar_v11
from produtos.selecao_contrato import DADOS_REAIS_HABILITADO
from produtos.tests.base import AGORA, Base

RAIZ = Path(__file__).resolve().parents[2]
EXEMPLO = RAIZ / "curadoria_b" / "exemplos_ficticios" / "ficha_valida.json"
EXPORT_ID = "00000000-0000-4000-8000-000000000011"
DEL = object()


def ficha(**over):
    d = json.loads(EXEMPLO.read_text(encoding="utf-8"))
    for k, v in over.items():
        partes = k.split("__")
        alvo = d
        for p in partes[:-1]:
            alvo = alvo[int(p)] if isinstance(alvo, list) else alvo[p]
        if v is DEL:
            alvo.pop(partes[-1], None)
        else:
            alvo[partes[-1]] = v
    return d


class Base2(Base):
    def setUp(self):
        super().setUp()
        self.saida_dir = self.tmp / "lote"

    def gravar(self, obj, nome="ficha.json"):
        p = self.tmp / nome
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return p

    def exportar(self, obj=None, saida=None, **kw):
        return exportar(self.gravar(obj if obj is not None else ficha()), saida or self.saida_dir, AGORA,
                        export_id=kw.pop("export_id", EXPORT_ID), **kw)

    def erros(self, obj):
        with self.assertRaises(ErroFicha) as c:
            self.exportar(obj)
        self.assertFalse((self.saida_dir / "B").exists(), "nenhum lote pode ser disponibilizado")
        return " | ".join(c.exception.erros)


class FichaValidaTest(Base2):
    def test_exemplo_ficticio_exporta_lote_integro(self):
        r = self.exportar()
        b = self.saida_dir / "B"
        self.assertEqual(sorted(p.name for p in b.iterdir()), ["manifest.json", "produto_CURADORIA_C001_20261117T150000Z.json"])
        self.assertEqual((r["estado"], r["validacao"], r["exportId"]), ("candidato_nao_verificado", "ok", EXPORT_ID))
        dados = (b / r["arquivo"]).read_bytes()
        self.assertEqual((r["sha256"], r["bytes"]), (hashlib.sha256(dados).hexdigest(), len(dados)))
        self.assertFalse(list(self.saida_dir.glob(".staging_*")), "pasta de preparo removida")

    def test_objeto_exportado_segue_o_contrato_1_1(self):
        self.exportar()
        d = json.loads(next((self.saida_dir / "B").glob("produto_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(d["source"], {"kind": "curadoria_manual", "system": "SuzukiOfertas-Instagram-Curadoria"})
        self.assertEqual(d["product"]["provider"], "CURADORIA")
        self.assertEqual(d["price"], {"amountCents": None, "currency": "BRL", "originalAmountCents": None, "verifiedAt": None,
                                      "validUntil": None, "verification": "desconhecida"})
        self.assertEqual((d["availability"], d["publication"]["state"], d["eligibility"]),
                         ("unknown", "nao_publicada", {"agentPublicationEligible": False,
                                                       "blockReason": "curadoria_manual_sem_verificacao_comercial"}))
        self.assertIsNone(d["product"]["affiliateUrl"])
        self.assertEqual(d["schemaVersion"], "1.0.0")
        self.assertNotIn("fichaCuradoriaVersion", json.dumps(d))
        self.assertEqual(set(d), {"schemaVersion", "exportId", "exportedAt", "source", "product", "price", "availability",
                                  "verifiedFacts", "publication", "references", "eligibility"})

    def test_manifesto_estrito_e_integro(self):
        r = self.exportar()
        mf, erros = ler_manifesto_estrito(self.saida_dir / "B" / "manifest.json", AGORA)
        self.assertEqual(erros, [])
        self.assertEqual((mf.versao, mf.count, list(mf.itens)), ("1.0", 1, [r["arquivo"]]))
        self.assertEqual(mf.itens[r["arquivo"]], {"sha256": r["sha256"], "bytes": r["bytes"]})
        self.assertLessEqual(mf.count, MAX_ARQUIVOS)
        bruto = json.loads((self.saida_dir / "B" / "manifest.json").read_text())
        self.assertEqual(set(bruto), {"manifestVersion", "generatedAt", "count", "files"})
        self.assertEqual(set(bruto["files"][0]), {"name", "sha256", "bytes"})

    def test_compativel_com_o_receptor_1_1_e_preserva_candidato_nao_verificado(self):
        self.exportar()
        l = ler_lote(self.saida_dir / "B", AGORA, "B")
        self.assertEqual((l.status, len(l.leitura.lidos), l.leitura.rejeitados), ("ok", 1, []))
        resumo = processar_v11(self.saida_dir, self.tmp / "out", AGORA)
        self.assertEqual(resumo["fichasPorEstado"], {"candidato_nao_verificado": 1})
        f = json.loads((self.tmp / "out" / "fichas" / "CURADORIA__C001.json").read_text(encoding="utf-8"))
        self.assertEqual((f["estado"], f["fonte"], f["origem"], f["preco"]["amountCents"], f["alegacaoComercialPermitida"]),
                         (estados.CANDIDATO_NAO_VERIFICADO, "curadoria_manual", "B", None, False))
        self.assertEqual(len(f["fatosParaUso"]), 2)

    def test_modo_1_0_rejeita_o_lote_exportado(self):
        self.exportar()
        lei = ler_pasta(self.saida_dir / "B", AGORA)
        self.assertEqual(lei.lidos, [])
        self.assertTrue(lei.rejeitados)

    def test_reexportacao_deterministica(self):
        a, b = self.tmp / "a", self.tmp / "b"
        ra, rb = self.exportar(saida=a), self.exportar(saida=b)
        self.assertEqual(ra["sha256"], rb["sha256"])
        for nome in ("manifest.json", ra["arquivo"]):
            self.assertEqual((a / "B" / nome).read_bytes(), (b / "B" / nome).read_bytes())
        c = self.exportar(saida=self.tmp / "c", export_id="00000000-0000-4000-8000-000000000012")
        self.assertNotEqual(c["sha256"], ra["sha256"])

    def test_export_id_padrao_e_uuid_e_invalido_e_recusado(self):
        r = exportar(self.gravar(ficha()), self.tmp / "x", AGORA)
        self.assertEqual(str(uuid.UUID(r["exportId"])), r["exportId"])
        with self.assertRaises(ErroExportacao):
            exportar(self.gravar(ficha()), self.tmp / "y", AGORA, export_id="nao-e-uuid")

    def test_categoria_opcional(self):
        self.exportar(ficha(category=DEL))
        d = json.loads(next((self.saida_dir / "B").glob("produto_*.json")).read_text(encoding="utf-8"))
        self.assertEqual((d["product"]["category"], d["product"]["categoryOrigin"]), (None, None))


class FichaInvalidaTest(Base2):
    def test_campos_obrigatorios_ausentes(self):
        for campo in ("fichaCuradoriaVersion", "id", "title", "store", "officialUrl", "fatos", "referencias"):
            self.assertIn(f"{campo}: campo obrigatório ausente", self.erros(ficha(**{campo: DEL})), campo)

    def test_campos_desconhecidos_em_todos_os_niveis(self):
        self.assertIn("campo desconhecido", self.erros(ficha(extra="x")))
        self.assertIn("fatos[0].extra", self.erros(ficha(fatos__0__extra="x")))
        self.assertIn("referencias[0].extra", self.erros(ficha(referencias__0__extra="x")))
        for campo in ("sourceRef", "verifiedAt", "text"):
            self.assertIn(f"fatos[0].{campo}: campo obrigatório ausente", self.erros(ficha(**{f"fatos__0__{campo}": DEL})))

    def test_dados_incompletos_e_tipos(self):
        for k, v in (("id", ""), ("id", "com espaço"), ("id", 5), ("title", "   "), ("title", None), ("store", ""),
                     ("officialUrl", None), ("category", ""), ("fatos", []), ("fatos", "texto"), ("referencias", "x"),
                     ("fichaCuradoriaVersion", "2.0")):
            self.erros(ficha(**{k: v}))
        self.erros("[]")
        self.erros("{truncado")
        self.erros(ficha(fatos=[ficha()["fatos"][0]] * 21))

    def test_campos_comerciais_proibidos_na_entrada_humana(self):
        for campo in ("price", "preco", "amountCents", "availability", "disponibilidade", "estoque", "affiliateUrl", "afiliado",
                      "desconto", "frete", "promocao", "cupom"):
            m = self.erros(ficha(**{campo: 1}))
            self.assertIn("campo comercial proibido", m, campo)
            self.assertEqual(list(self.tmp.glob("lote*")), [] if not self.saida_dir.exists() else [self.saida_dir])

    def test_alegacoes_comerciais_e_titulo_alta(self):
        for t in ("Panela em promoção", "Panela com frete grátis", "Menor preço do ano", "Panela 30% OFF", "Em estoque"):
            self.assertIn("alegação comercial", self.erros(ficha(title=t)), t)
        self.assertIn("ALTA", self.erros(ficha(title="Panela Original Premium")))
        self.assertIn("alegação comercial", self.erros(ficha(fatos__0__text="Disponível em estoque")))

    def test_links_inadequados(self):
        ruins = ["http://www.lojaficticia.example/p", "https://bit.ly/abc", "https://u:s@www.lojaficticia.example/p",
                 "https://www.lojaficticia.example:8443/p", "https://203.0.113.9/p", "https://localhost/p",
                 "https://www.lojaficticia.example/p?utm_source=x", "https://", "javascript:alert(1)"]
        for url in ruins:
            self.erros(ficha(officialUrl=url))
            self.erros(ficha(fatos__0__sourceRef=url))
            self.erros(ficha(referencias__0__url=url))
        self.erros(ficha(fatos__0__sourceRef="manual do fabricante"))            # sourceRef tem de ser URL HTTPS

    def test_fato_com_data_futura_ou_invalida(self):
        for v in ("2026-12-31T00:00:00Z", "ontem", "2026-11-16", None):
            self.erros(ficha(fatos__0__verifiedAt=v))

    def test_mensagens_nao_ecoam_valores(self):
        m = self.erros(ficha(officialUrl="https://bit.ly/SEGREDO-NAO-VAZAR", title="Frete grátis SEGREDO-NAO-VAZAR"))
        self.assertNotIn("SEGREDO-NAO-VAZAR", m)


class ProdutosReaisTest(Base2):
    def test_bloqueios_continuam_desabilitados(self):
        self.assertIs(fch.PRODUTOS_REAIS_HABILITADO, False)
        self.assertIs(DADOS_REAIS_HABILITADO, False)

    def test_dominios_reservados_aceitos(self):
        for host in ("www.loja.example", "a.b.invalid", "loja.test", "example.com", "www.example.org", "x.example.net"):
            self.assertTrue(fch.dominio_reservado(host), host)
            self.exportar(ficha(officialUrl=f"https://{host}/p"), saida=self.tmp / host)

    def test_dominios_com_aparencia_de_comercio_real_sao_rejeitados_sem_rede(self):
        for host in ("www.amazon.com.br", "www.magazineluiza.com.br", "shopee.com.br", "www.exemplo.com.br", "example.com.evil.io",
                     "notexample.com", "lojaficticia.example.com.br"):
            self.assertFalse(fch.dominio_reservado(host), host)
            self.assertIn("produtos reais estão desabilitados", self.erros(ficha(officialUrl=f"https://{host}/p")), host)
        self.assertIn("fatos[0].sourceRef: domínio não reservado", self.erros(ficha(fatos__0__sourceRef="https://www.fabricante.com.br/m")))
        self.assertIn("referencias[0].url: domínio não reservado", self.erros(ficha(referencias__0__url="https://www.loja.com/x")))

    def test_a_chave_realmente_governa_o_bloqueio(self):
        real = ficha(officialUrl="https://www.loja-real.com.br/p", fatos__0__sourceRef="https://fabricante-real.com.br/m",
                     referencias__0__url="https://www.loja-real.com.br/p")
        with mock.patch.object(fch, "PRODUTOS_REAIS_HABILITADO", True):          # só no teste; o valor do código NÃO muda
            ler_ficha(real, AGORA)
        self.assertIs(fch.PRODUTOS_REAIS_HABILITADO, False)
        with self.assertRaises(ErroFicha):
            ler_ficha(real, AGORA)


class IntegridadeTest(Base2):
    def test_manifesto_ou_produto_adulterado_vai_para_quarentena(self):
        self.exportar()
        b = self.saida_dir / "B"
        produto = next(b.glob("produto_*.json"))
        original = produto.read_bytes()
        produto.write_bytes(original + b" ")
        l = ler_lote(b, AGORA, "B")
        self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []))
        produto.write_bytes(original)
        mf = b / "manifest.json"
        m = json.loads(mf.read_text())
        m["files"][0]["bytes"] += 1
        mf.write_text(json.dumps(m))
        self.assertEqual(ler_lote(b, AGORA, "B").status, "quarentena_de_lote")
        mf.unlink()
        self.assertEqual(ler_lote(b, AGORA, "B").status, "quarentena_de_lote")

    def test_b_existente_nunca_e_sobrescrito(self):
        self.exportar()
        antes = {p.name: p.read_bytes() for p in (self.saida_dir / "B").iterdir()}
        with self.assertRaises(ErroExportacao):
            self.exportar(export_id="00000000-0000-4000-8000-000000000013")
        self.assertEqual(antes, {p.name: p.read_bytes() for p in (self.saida_dir / "B").iterdir()})
        self.assertFalse(list(self.saida_dir.glob(".staging_*")))

    def test_falha_na_validacao_nao_deixa_lote_parcial_e_limpa_so_o_que_criou(self):
        self.saida_dir.mkdir()
        (self.saida_dir / "outro.txt").write_text("não é meu")
        (self.saida_dir / "pasta_alheia").mkdir()
        with mock.patch.object(exportador, "ler_lote", side_effect=RuntimeError("falha simulada")):
            with self.assertRaises(RuntimeError):
                self.exportar()
        self.assertEqual(sorted(p.name for p in self.saida_dir.iterdir()), ["outro.txt", "pasta_alheia"])
        self.assertEqual((self.saida_dir / "outro.txt").read_text(), "não é meu")

    def test_receptor_que_recusa_o_lote_levanta_e_limpa(self):
        class Falso:
            status, motivos, leitura = "quarentena_de_lote", ["simulado"], mock.Mock(lidos=[], rejeitados=[])
        with mock.patch.object(exportador, "ler_lote", return_value=Falso()):
            with self.assertRaises(ErroExportacao):
                self.exportar()
        self.assertFalse((self.saida_dir / "B").exists())
        self.assertFalse(list(self.saida_dir.glob(".staging_*")))

    def test_preparo_preexistente_nao_e_apagado(self):
        preparo = self.saida_dir / f".staging_{EXPORT_ID[:8]}"
        preparo.mkdir(parents=True)
        (preparo / "alheio.txt").write_text("x")
        with self.assertRaises(FileExistsError):
            self.exportar()
        self.assertTrue((preparo / "alheio.txt").exists())

    def test_ficha_original_nunca_e_alterada(self):
        p = self.gravar(ficha())
        antes = p.read_bytes()
        exportar(p, self.saida_dir, AGORA, export_id=EXPORT_ID)
        self.assertEqual(p.read_bytes(), antes)

    def test_construir_lote_e_puro(self):
        a, b = construir_lote(ler_ficha(ficha(), AGORA), EXPORT_ID, AGORA), construir_lote(ler_ficha(ficha(), AGORA), EXPORT_ID, AGORA)
        self.assertEqual(a, b)


class CliTest(Base2):
    def rodar(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(list(args))
        return rc, out.getvalue(), err.getvalue()

    def test_cli_sucesso(self):
        rc, out, _ = self.rodar(str(EXEMPLO), "--saida", str(self.saida_dir), "--agora", "2026-11-17T15:00:00Z", "--export-id", EXPORT_ID)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["estado"], "candidato_nao_verificado")

    def test_cli_erros(self):
        rc, _, err = self.rodar(str(self.gravar(ficha(price=1))), "--saida", str(self.saida_dir), "--agora", "2026-11-17T15:00:00Z")
        self.assertEqual(rc, 2)
        self.assertIn("campo comercial proibido", err)
        self.assertEqual(self.rodar(str(EXEMPLO), "--saida", str(self.saida_dir), "--agora", "ontem")[0], 2)
        self.assertEqual(self.rodar(str(self.tmp / "nao_existe.json"), "--saida", str(self.saida_dir), "--agora", "2026-11-17T15:00:00Z")[0], 2)
        self.assertFalse((self.saida_dir / "B").exists())


class SemRedeTest(Base2):
    PACOTE = RAIZ / "curadoria_b"

    def test_nenhum_modulo_usa_rede_processos_ou_ambiente(self):
        for arq in self.PACOTE.glob("*.py"):
            fonte = arq.read_text(encoding="utf-8")
            for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", fonte, re.M):
                alvo = (m.group(1) or m.group(2)).replace(" ", "")
                for mod in alvo.split(","):
                    for proibido in ("urllib.request", "http.client", "socket", "requests", "subprocess", "ssl", "ftplib", "smtplib",
                                     "sqlite3", "webbrowser"):
                        self.assertFalse(mod == proibido or mod.startswith(proibido + "."), (arq.name, mod))
            for padrao in ("os.environ", "getenv", "urlopen", "Popen", "os.system"):
                self.assertNotIn(padrao, fonte, (arq.name, padrao))

    def test_exportacao_completa_roda_com_a_rede_bloqueada(self):
        with self.assertRaises(AssertionError):
            import socket
            socket.create_connection(("exemplo.example", 443))
        self.exportar()                                    # Base.setUp bloqueia toda conexão; qualquer tentativa falharia

    def exportar(self):
        return exportar(self.gravar(ficha()), self.saida_dir, AGORA, export_id=EXPORT_ID)

    def gravar(self, obj):
        p = self.tmp / "f.json"
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return p


if __name__ == "__main__":
    unittest.main()
