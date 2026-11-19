import copy
import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path

from entrada_segura import classificacao as cl
from entrada_segura.fixtures_registro import CONJUNTOS, ConjuntoFixture
from entrada_segura.politica import PRODUCAO

RAIZ = Path(__file__).resolve().parents[2]
PASTAS_ESTATICAS = ["produtos/exemplos_ficticios", "produtos/exemplos_ficticios_v1_1", "curadoria_b/exemplos_ficticios",
                    "orquestrador_b2/exemplos_ficticios", "exemplos"]


def js(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode()


def lote(*urls, extra=None, nome="a.json"):
    d = {"urls": list(urls)}
    d.update(extra or {})
    return {nome: js(d)}


def conjunto_para(arquivos, id_="sintetico/teste"):
    return ConjuntoFixture(id_, "sintetico", {k: hashlib.sha256(v).hexdigest() for k, v in arquivos.items()})


class ClasseEMotivos(unittest.TestCase):
    def cls(self, arquivos, config=PRODUCAO):
        return cl.classificar(arquivos, config)

    def test_real_se_ha_um_host_nao_reservado(self):
        for urls in (["https://loja.com/p"], ["https://a.example", "https://loja.com.br"], ["https://example.com.evil.com"], ["www.loja.com"]):
            r = self.cls(lote(*urls))
            self.assertEqual(r.classe, cl.REAL, urls)
            self.assertIn("host_nao_reservado", r.motivos)

    def test_hosts_reservados_sem_procedencia_sao_desconhecidos(self):
        r = self.cls(lote("https://a.example/x", "https://b.example.com"))
        self.assertEqual(r.classe, cl.DESCONHECIDO)
        self.assertEqual(r.motivos, ("host_reservado", "procedencia_ausente"))

    def test_ficticio_exige_procedencia_registrada(self):
        arq = lote("https://a.example/x")
        cfg = replace(PRODUCAO, conjuntos=(conjunto_para(arq),))
        r = self.cls(arq, cfg)
        self.assertEqual((r.classe, r.conjunto), (cl.FICTICIO, "sintetico/teste"))
        self.assertEqual(r.motivos, ("host_reservado", "procedencia_registrada"))
        self.assertEqual(r.hosts, ("a.example",))

    def test_um_byte_alterado_extra_ou_faltante_perde_a_procedencia(self):
        arq = {**lote("https://a.example/x"), "b.json": js({"u": "https://b.example"})}
        cfg = replace(PRODUCAO, conjuntos=(conjunto_para(arq),))
        self.assertEqual(self.cls(arq, cfg).classe, cl.FICTICIO)
        alterado = dict(arq); alterado["b.json"] = js({"u": "https://b.example", "x": 1})
        self.assertEqual(self.cls(alterado, cfg).classe, cl.DESCONHECIDO)
        self.assertEqual(self.cls({"a.json": arq["a.json"]}, cfg).classe, cl.DESCONHECIDO)                       # subconjunto
        self.assertEqual(self.cls({**arq, "c.json": js({"u": "https://c.example"})}, cfg).classe, cl.DESCONHECIDO)  # superconjunto
        outro_caminho = {"x/a.json": arq["a.json"], "b.json": arq["b.json"]}
        r = self.cls(outro_caminho, cfg)
        self.assertEqual(r.classe, cl.DESCONHECIDO)
        self.assertIn("conjunto_nao_reconhecido", r.motivos)                                                      # mesmo hash, outro caminho

    def test_combinacao_arbitraria_de_arquivos_reconhecidos_nao_e_confiavel(self):
        a, b = lote("https://a.example"), lote("https://b.example", nome="b.json")
        cfg = replace(PRODUCAO, conjuntos=(conjunto_para(a, "c/a"), conjunto_para(b, "c/b")))
        self.assertEqual(self.cls(a, cfg).classe, cl.FICTICIO)
        self.assertEqual(self.cls(b, cfg).classe, cl.FICTICIO)
        r = self.cls({**a, **b}, cfg)
        self.assertEqual(r.classe, cl.DESCONHECIDO)
        self.assertIn("conjunto_nao_reconhecido", r.motivos)

    def test_hash_registrado_com_host_real_e_potencialmente_real(self):
        arq = lote("https://loja.com/p")
        cfg = replace(PRODUCAO, conjuntos=(conjunto_para(arq),))
        r = self.cls(arq, cfg)
        self.assertEqual(r.classe, cl.REAL)
        self.assertIn("procedencia_registrada", r.motivos)           # sinalizado como erro de registro
        self.assertIsNone(r.conjunto)

    def test_metadados_autodeclarados_sao_ignorados(self):
        extra = {"system": "SuzukiOfertas-AgenteAutomatico", "provider": "CURADORIA", "exportId": "x", "source": {"kind": "curadoria_manual"},
                 "photo": {"usePermission": "confirmada"}, "real_autorizado": True, "authorized": True, "fixture": True, "autor": "Maria"}
        for nome in ("produto_EXEMPLO_A.json", "ficha_valida.json", "fixture_ficticia.json"):
            r = self.cls(lote("https://a.example", extra=extra, nome=nome))
            self.assertEqual(r.classe, cl.DESCONHECIDO, nome)
        r = self.cls(lote("https://loja.com", extra=extra))
        self.assertEqual(r.classe, cl.REAL)

    def test_sem_urls_json_invalido_e_binario(self):
        self.assertEqual(self.cls({"a.json": js({"x": 1})}).motivos, ("sem_urls_avaliaveis", "procedencia_ausente")[:1])
        self.assertEqual(self.cls({"a.json": js({"x": 1})}).classe, cl.DESCONHECIDO)
        r = self.cls({"a.json": b'{"u": "https://a.example", ', "b.json": js({"u": "https://b.example"})})
        self.assertEqual(r.classe, cl.DESCONHECIDO)
        self.assertIn("json_invalido", r.motivos)
        r = self.cls({"a.txt": b"\xff\xfe\x00\x01", "b.json": js({"u": "https://b.example"})})
        self.assertEqual(r.classe, cl.DESCONHECIDO)
        self.assertIn("conteudo_nao_textual", r.motivos)
        self.assertEqual(self.cls({}).classe, cl.DESCONHECIDO)

    def test_jpeg_esperado_nao_e_varrido(self):
        arq = {**lote("https://a.example"), "foto.jpg": b"\xff\xd8\xff\xe0binario\xff"}
        cfg = replace(PRODUCAO, conjuntos=(conjunto_para(arq),))
        self.assertEqual(self.cls(arq, cfg).classe, cl.FICTICIO)

    def test_host_invalido_torna_desconhecido_e_real_prevalece(self):
        r = self.cls(lote("https://a.example", "https://user@b.example"))
        self.assertEqual((r.classe, "host_invalido" in r.motivos), (cl.DESCONHECIDO, True))
        r = self.cls(lote("https://127.0.0.1", "https://loja.com"))
        self.assertEqual(r.classe, cl.REAL)

    def test_urls_em_markdown_e_em_campos_aninhados(self):
        self.assertEqual(self.cls({"LEIA.md": "veja https://loja.com/x para detalhes".encode()}).classe, cl.REAL)
        self.assertEqual(self.cls({"a.json": js({"a": {"b": [{"c": "https://loja.com"}]}})}).classe, cl.REAL)
        self.assertEqual(self.cls({"a.json": js({"sourceRef": "loja.com.br/p"})}).classe, cl.REAL)
        self.assertEqual(self.cls({"a.json": js({"manifest": "manifest.json", "v": "1.0.0"})}).motivos[0], "sem_urls_avaliaveis")

    def test_classificacao_independe_de_autorizacao_flags_e_relogio(self):
        arq = lote("https://loja.com")
        base = self.cls(arq)
        for cfg in (replace(PRODUCAO, dados_reais_habilitado=True, produtos_reais_habilitado=True), replace(PRODUCAO, relogio=lambda: None),
                    replace(PRODUCAO, ancoras=frozenset({"sha256:" + "0" * 64}))):
            self.assertEqual(self.cls(arq, cfg), base)

    def test_motivos_ordenados_e_hosts_sem_urls_completas(self):
        arq = lote("https://z.loja.com/segredo?token=abc#x", "http://a.loja.com/p", "https://m.example")
        r = self.cls(arq)
        self.assertEqual(r.motivos, tuple(m for m in cl.ORDEM_MOTIVOS if m in r.motivos))
        self.assertEqual(r.hosts, ("a.loja.com", "m.example", "z.loja.com"))
        self.assertNotIn("token", json.dumps(r.hosts))

    def test_limite_de_hosts_no_relatorio(self):
        arq = lote(*[f"https://h{i:03d}.loja.com" for i in range(80)])
        r = self.cls(arq)
        self.assertEqual((len(r.hosts), r.total_hosts), (50, 80))


class HttpD5(unittest.TestCase):
    def test_http_com_host_real(self):
        r = cl.classificar(lote("http://loja.com/p"), PRODUCAO)
        self.assertEqual(r.classe, cl.REAL)
        self.assertIn("esquema_nao_https", r.motivos)

    def test_http_reservado_sem_procedencia_e_desconhecido(self):
        r = cl.classificar(lote("http://a.example/x"), PRODUCAO)
        self.assertEqual(r.classe, cl.DESCONHECIDO)
        self.assertIn("esquema_nao_https", r.motivos)

    def test_http_reservado_com_conjunto_sintetico_e_ficticio_com_motivo(self):
        arq = lote("http://a.example/x")
        r = cl.classificar(arq, replace(PRODUCAO, conjuntos=(conjunto_para(arq),)))
        self.assertEqual(r.classe, cl.FICTICIO)
        self.assertEqual(r.motivos, ("host_reservado", "esquema_nao_https", "procedencia_registrada"))

    def test_http_misturado_e_em_sourceref(self):
        r = cl.classificar(lote("https://a.example", "http://b.example"), PRODUCAO)
        self.assertIn("esquema_nao_https", r.motivos)
        r = cl.classificar({"a.json": js({"sourceRef": "http://fonte.example/x"})}, PRODUCAO)
        self.assertIn("esquema_nao_https", r.motivos)
        r = cl.classificar(lote("https://a.example"), PRODUCAO)
        self.assertNotIn("esquema_nao_https", r.motivos)


class RegistroDeFixtures(unittest.TestCase):
    def arquivos_da_pasta(self, pasta: str) -> dict:
        b = RAIZ / pasta
        return {str(p.relative_to(b)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(b.rglob("*")) if p.is_file()}

    def test_todo_arquivo_estatico_pertence_a_algum_conjunto_e_cada_conjunto_e_exato(self):
        por_id = {c.id: c for c in CONJUNTOS}
        self.assertEqual(len(por_id), len(CONJUNTOS))
        for pasta in PASTAS_ESTATICAS:
            todos = self.arquivos_da_pasta(pasta)
            self.assertIn(pasta, por_id, pasta)
            self.assertEqual(dict(por_id[pasta].arquivos), todos, pasta)                       # conjunto da pasta inteira coincide exatamente
            for rel, h in todos.items():
                caminho = f"{pasta}/{rel}"
                self.assertTrue(any(h in c.arquivos.values() for c in CONJUNTOS), caminho)
        for c in CONJUNTOS:
            if c.base.endswith(".json"):
                self.assertEqual(dict(c.arquivos), {Path(c.base).name: hashlib.sha256((RAIZ / c.base).read_bytes()).hexdigest()}, c.id)
            else:
                self.assertEqual(dict(c.arquivos), self.arquivos_da_pasta(c.base), c.id)

    def test_fixtures_estaticas_nao_usam_http(self):
        for pasta in PASTAS_ESTATICAS:
            for p in (RAIZ / pasta).rglob("*"):
                if p.is_file() and not p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    self.assertNotIn(b"http://", p.read_bytes(), str(p))

    def test_hash_da_ficha_historica_registrado(self):
        c = next(c for c in CONJUNTOS if c.id == "curadoria_b/exemplos_ficticios")
        self.assertEqual(c.arquivos["ficha_valida.json"], "68e4dd96bee57e61ddd1e5670153c81381de8035156b5766a01e95099af989a3")

    def test_classificacao_das_fixtures_reais_do_repositorio(self):
        """Constatação para a B3-A2: lotes sem URL, com JSON ilegível ou binário não são reconhecidos (regra da §4.7)."""
        esperado = {"produtos/exemplos_ficticios_v1_1/exportacoes": cl.FICTICIO, "produtos/exemplos_ficticios_v1_1/exportacoes/A": cl.FICTICIO,
                    "curadoria_b/exemplos_ficticios": cl.FICTICIO, "orquestrador_b2/exemplos_ficticios": cl.FICTICIO,
                    "produtos/exemplos_ficticios/troca": cl.DESCONHECIDO, "produtos/exemplos_ficticios/decisoes": cl.DESCONHECIDO,
                    "produtos/exemplos_ficticios_v1_1/fotos": cl.DESCONHECIDO, "exemplos": cl.DESCONHECIDO}
        for pasta, classe in esperado.items():
            b = RAIZ / pasta
            arq = {str(p.relative_to(b)): p.read_bytes() for p in sorted(b.rglob("*")) if p.is_file()}
            self.assertEqual(cl.classificar(arq, PRODUCAO).classe, classe, pasta)
