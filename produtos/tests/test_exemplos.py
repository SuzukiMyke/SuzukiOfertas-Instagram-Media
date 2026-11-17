"""Exemplos fictícios empacotados + coerência do JSON Schema com o validador."""
import hashlib
import json
import re
import unittest

from produtos import esquema
from produtos.pipeline import processar
from produtos.tests.base import AGORA, EXEMPLOS, RAIZ, Base

TROCA = EXEMPLOS / "troca"
DECISOES = EXEMPLOS / "decisoes" / "decisoes_exemplo.json"
SCHEMA = RAIZ / "produtos" / "schema" / "produto.v1.schema.json"


class ExemplosTest(Base):
    def setUp(self):
        super().setUp()
        self.antes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in TROCA.iterdir() if p.is_file()}
        self.resumo = processar(TROCA, self.saida, AGORA, decisoes_arquivo=DECISOES)

    def estados(self):
        return {f.name.split(".")[0]: json.loads(f.read_text(encoding="utf-8"))["estado"]
                for f in (self.saida / "fichas").glob("*.json")}

    def test_estados_esperados(self):
        self.assertEqual(self.estados(), {
            "EXEMPLO_A__A001": "aprovado_para_rascunho",   # decisão humana de exemplo
            "EXEMPLO_A__A002": "expirado",                 # validUntil vencido
            "EXEMPLO_A__A003": "incompleto",               # foto pendente
            "EXEMPLO_A__A004": "pendente_revisao",         # preço mudou: aprovação da v1 invalidada
            "EXEMPLO_A__A010": "invalidado",               # indisponível
            "EXEMPLO_B__B001": "expirado",                 # B: sem verificação
            "EXEMPLO_B__B002": "expirado",                 # B sem categoria
        })

    def test_rejeitados_esperados(self):
        rej = {r["arquivo"]: r for r in json.loads((self.saida / "rejeitados.json").read_text(encoding="utf-8"))}
        destinos = {a.split("_")[3]: r["destino"] for a, r in rej.items()}
        self.assertEqual(destinos, {"A005": "rejeitado", "A006": "quarentena", "A008": "quarentena",
                                    "A009": "rejeitado", "B003": "quarentena"})
        self.assertIn("campo proibido", rej["produto_EXEMPLO_A_A005_20261117T130500Z.json"]["motivos"][0])
        self.assertIn("truncado", rej["produto_EXEMPLO_A_A006_20261117T130500Z.json"]["motivos"][0])
        self.assertIn("major 2", rej["produto_EXEMPLO_A_A008_20261117T130500Z.json"]["motivos"][0])
        self.assertIn("token", rej["produto_EXEMPLO_A_A009_20261117T130500Z.json"]["motivos"][0])
        self.assertIn("SHA-256", rej["produto_EXEMPLO_B_B003_20261117T120000Z.json"]["motivos"][0])

    def test_ignorados_em_silencio_e_historico_de_a004(self):
        self.assertEqual(sorted(self.resumo["ignoradosEmSilencio"]),
                         [".oculto_A011.json", "produto_EXEMPLO_A_A007_20261117T140000Z.json.tmp"])
        hist = {h["productId"]: h for h in json.loads((self.saida / "historico.json").read_text(encoding="utf-8"))}
        self.assertEqual([v["amountCents"] for v in hist["A004"]["versoes"]], [7990, 8990])
        self.assertEqual([v["situacao"] for v in hist["A004"]["versoes"]], ["vigente", "substituida"])

    def test_a004_aprovacao_invalidada_por_preco(self):
        f = json.loads((self.saida / "fichas" / "EXEMPLO_A__A004.json").read_text(encoding="utf-8"))
        self.assertTrue(f["aprovacaoInvalidadaPorPreco"])
        self.assertIsNone(f["decisaoHumana"])

    def test_exemplos_nao_foram_alterados(self):
        depois = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in TROCA.iterdir() if p.is_file()}
        self.assertEqual(depois, self.antes)

    def test_exemplos_sao_inequivocamente_ficticios(self):
        for p in list(TROCA.iterdir()) + [DECISOES]:
            if not p.is_file():
                continue
            for url in re.findall(r"https?://[^\s\"']+", p.read_text(encoding="utf-8")):
                host = url.split("/")[2]
                self.assertTrue(host.endswith(".example"), (p.name, url))


class EsquemaJsonTest(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_chaves_do_json_schema_coincidem_com_a_lista_de_permissao(self):
        props = self.schema["properties"]
        self.assertEqual(set(props), set(esquema.TOPO))
        self.assertEqual(set(props["source"]["properties"]), set(esquema.CAMPOS["source"]))
        self.assertEqual(set(props["product"]["properties"]), set(esquema.CAMPOS["product"]))
        self.assertEqual(set(props["price"]["properties"]), set(esquema.CAMPOS["price"]))
        self.assertEqual(set(props["photo"]["properties"]), set(esquema.CAMPOS["photo"]))
        self.assertEqual(set(props["verifiedFacts"]["items"]["properties"]), set(esquema.CAMPOS["fact"]))
        self.assertEqual(set(props["publication"]["properties"]), set(esquema.CAMPOS["publication"]))
        self.assertEqual(set(props["references"]["items"]["properties"]), set(esquema.CAMPOS["reference"]))
        self.assertEqual(set(props["eligibility"]["properties"]), set(esquema.CAMPOS["eligibility"]))
        self.assertEqual(set(self.schema["required"]), set(esquema.OBRIGATORIOS[""]))
        for nome in ("source", "product", "price", "publication", "eligibility"):
            self.assertEqual(set(props[nome]["required"]), set(esquema.OBRIGATORIOS[nome]), nome)
        self.assertIs(self.schema["additionalProperties"], False)
        self.assertEqual(self.schema["$defs"]["iso"]["type"], "string")

    def test_schema_version_documentada(self):
        self.assertIn("1.0.0", json.dumps(self.schema))  # título cita o contrato 1.0.0-proposta

    def test_json_schema_aceita_validos_e_recusa_invalidos_quando_jsonschema_existe(self):
        try:
            import jsonschema
        except ImportError:                                   # dependência opcional (só para esta checagem cruzada)
            self.skipTest("jsonschema não instalado")
        v = jsonschema.Draft202012Validator(self.schema)
        jsonschema.Draft202012Validator.check_schema(self.schema)
        for nome in ("produto_EXEMPLO_A_A001_20261117T130500Z.json", "produto_EXEMPLO_B_B001_20261117T120000Z.json",
                     "produto_EXEMPLO_A_A004_20261117T140000Z.json"):
            self.assertEqual(list(v.iter_errors(json.loads((TROCA / nome).read_text(encoding="utf-8")))), [], nome)
        for nome in ("produto_EXEMPLO_A_A005_20261117T130500Z.json", "produto_EXEMPLO_A_A008_20261117T130500Z.json"):
            self.assertTrue(list(v.iter_errors(json.loads((TROCA / nome).read_text(encoding="utf-8")))), nome)
        from produtos.tests.base import produto_a, produto_b
        base = produto_a()
        invalidos = []
        d = produto_a(); d["product"].pop("title"); invalidos.append(d)
        d = produto_a(); d["price"]["amountCents"] = 12.5; invalidos.append(d)
        d = produto_a(); d["price"]["currency"] = "USD"; invalidos.append(d)
        d = produto_a(); d["product"]["officialUrl"] = "http://x.lojaficticia.example/"; invalidos.append(d)
        d = produto_b(); d["publication"]["state"] = "publicada"; invalidos.append(d)
        d = produto_b(); d["eligibility"]["agentPublicationEligible"] = True; invalidos.append(d)
        d = produto_a(); d["publication"]["state"] = "nao_publicada"; invalidos.append(d)
        for i, d in enumerate(invalidos):
            self.assertTrue(list(v.iter_errors(d)), f"caso {i}")
        self.assertEqual(list(v.iter_errors(base)), [])
        self.assertEqual(list(v.iter_errors(produto_b())), [])


if __name__ == "__main__":
    unittest.main()
