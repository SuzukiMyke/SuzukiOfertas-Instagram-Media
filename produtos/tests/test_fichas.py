"""Teste 9: fichas JSON/Markdown e pipeline de ponta a ponta (sem rede)."""
import json
import unittest

from produtos import estados, esquema, fichas
from produtos.pipeline import processar
from produtos.tests.base import AGORA, DEL, Base, escrever, produto_a, produto_b, uid

PROIBIDOS = ("telegram", "token", "secret", "password", "senha", "operator", "operador", "cofre", "chat_id", "apikey")


def chaves(obj, acc=None):
    acc = set() if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            chaves(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            chaves(v, acc)
    return acc


class FichasTest(Base):
    def rodar(self, **arquivos):
        for nome, d in arquivos.items():
            escrever(self.troca, nome + ".json", d)
        return processar(self.troca, self.saida, AGORA)

    def ficha(self, base):
        return json.loads((self.saida / "fichas" / f"{base}.json").read_text(encoding="utf-8"))

    def test_gera_json_e_markdown_por_produto(self):
        resumo = self.rodar(a=produto_a(), b=produto_b())
        self.assertEqual(resumo["fichas"], 2)
        for base in ("EXEMPLO_A__A001", "EXEMPLO_B__B001"):
            self.assertTrue((self.saida / "fichas" / f"{base}.json").is_file())
            self.assertTrue((self.saida / "fichas" / f"{base}.md").is_file())
        for nome in ("historico.json", "rejeitados.json", "arquivados.json", "resumo.json"):
            self.assertTrue((self.saida / nome).is_file(), nome)

    def test_conteudo_da_ficha_a(self):
        self.rodar(a=produto_a())
        f = self.ficha("EXEMPLO_A__A001")
        self.assertEqual(f["origem"], "A")
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)
        self.assertEqual(f["preco"]["exibicao"], "R$ 129,90")
        self.assertTrue(f["foto"]["utilizavel"])
        self.assertEqual(f["versao"]["exportId"], uid(1))
        self.assertTrue(any("preço pode mudar" in a.lower() for a in f["avisos"]))
        self.assertTrue(any("fora do vídeo" in a.lower() for a in f["avisos"]))
        self.assertIsNone(f["decisaoHumana"])

    def test_ficha_b_e_sem_foto_autorizada_e_com_pendencias(self):
        self.rodar(b=produto_b())
        f = self.ficha("EXEMPLO_B__B001")
        self.assertEqual(f["origem"], "B")
        self.assertEqual(f["estado"], estados.EXPIRADO)
        self.assertIsNone(f["produto"]["affiliateUrl"])
        self.assertFalse(f["foto"]["utilizavel"])
        self.assertIn("sem foto autorizada", " ".join(f["avisos"]))
        self.assertEqual(f["dadosInsuficientes"], ["foto autorizada"])
        self.assertTrue(f["pendencias"])
        md = (self.saida / "fichas" / "EXEMPLO_B__B001.md").read_text(encoding="utf-8")
        self.assertIn("Origem B", md)
        self.assertIn("sem foto autorizada", md)

    def test_ficha_nao_expoe_campos_proibidos(self):
        proib = produto_a(2, "A002", telegramUpdateId=1)
        self.rodar(a=produto_a(), b=produto_b(), proibido=proib)
        self.assertFalse((self.saida / "fichas" / "EXEMPLO_A__A002.json").exists())
        for p in (self.saida / "fichas").iterdir():            # relatório de rejeitados cita só o NOME do campo
            self.assertNotIn("telegramupdateid", p.read_text(encoding="utf-8").lower(), p.name)
        for p in (self.saida / "fichas").glob("*.json"):
            ks = {k.lower() for k in chaves(json.loads(p.read_text(encoding="utf-8")))}
            for proibido in PROIBIDOS:
                self.assertFalse(any(proibido in k for k in ks), (p.name, proibido))

    def test_ficha_so_contem_dados_vindos_da_lista_de_permissao(self):
        # campo desconhecido dentro de um arquivo válido não existe: o arquivo é rejeitado inteiro
        self.rodar(a=produto_a(extra="x"))
        self.assertEqual(list((self.saida / "fichas").glob("*")), [])
        rej = json.loads((self.saida / "rejeitados.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rej), 1)

    def test_markdown_neutraliza_marcacao_e_html(self):
        d = produto_a(product__title="<script>alert(1)</script> *negrito* [x](http://y) | tabela")
        self.rodar(a=d)
        md = (self.saida / "fichas" / "EXEMPLO_A__A001.md").read_text(encoding="utf-8")
        primeira = md.splitlines()[0]
        self.assertNotIn("<script>", primeira)
        self.assertIn("\\<script\\>", primeira)
        self.assertIn("\\*negrito\\*", primeira)

    def test_reais(self):
        self.assertEqual(fichas.reais(12990), "R$ 129,90")
        self.assertEqual(fichas.reais(5), "R$ 0,05")
        self.assertEqual(fichas.reais(123456789), "R$ 1.234.567,89")

    def test_dados_insuficientes_no_relatorio_de_rejeitados(self):
        self.rodar(faltando=produto_a(product__title=DEL))
        rej = json.loads((self.saida / "rejeitados.json").read_text(encoding="utf-8"))
        self.assertEqual(rej[0]["categoria"], "dados_insuficientes")
        self.assertEqual(rej[0]["camposFaltantes"], ["product.title"])

    def test_resumo_conta_por_estado_e_destino(self):
        self.rodar(a=produto_a(), b=produto_b(), ruim=produto_a(2, "A002", telegramUpdateId=1))
        escrever(self.troca, "trunc.json", "{")
        resumo = processar(self.troca, self.saida, AGORA)
        self.assertEqual(resumo["fichasPorEstado"], {"expirado": 1, "pendente_revisao": 1})
        self.assertEqual(resumo["rejeitadosPorDestino"], {"quarentena": 1, "rejeitado": 1})

    def test_saida_e_deterministica_e_limpa_fichas_antigas(self):
        self.rodar(a=produto_a(), b=produto_b())
        def foto_da_saida():
            return {str(p.relative_to(self.saida)): p.read_bytes() for p in sorted(self.saida.rglob("*")) if p.is_file()}
        primeira = foto_da_saida()
        processar(self.troca, self.saida, AGORA)
        self.assertEqual(foto_da_saida(), primeira)
        (self.troca / "b.json").unlink()                       # produto sumiu da pasta de troca
        processar(self.troca, self.saida, AGORA)
        self.assertFalse((self.saida / "fichas" / "EXEMPLO_B__B001.json").exists())
        self.assertTrue((self.saida / "fichas" / "EXEMPLO_A__A001.json").exists())

    def test_saida_nao_depende_do_relogio_do_sistema(self):
        self.rodar(a=produto_a())
        resumo = json.loads((self.saida / "resumo.json").read_text(encoding="utf-8"))
        self.assertEqual(resumo["geradoEm"], "2026-11-17T15:00:00Z")


if __name__ == "__main__":
    unittest.main()
