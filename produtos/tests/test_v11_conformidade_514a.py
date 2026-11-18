"""Revisão de conformidade da 5.14-A: (1) impressão digital e decisões, (2) valores das divergências A×B, (3) bloqueios do carrossel."""
import hashlib
import json
import unittest
from datetime import timedelta

from produtos import decisoes as dec_v1
from produtos import estados
from produtos import impressao_v11 as imp
from produtos.carrossel_fragmento_v11 import CarrosselRecusado, ficha_para_carrossel_v11
from produtos.decisoes_v11 import COD_IMPRESSAO, COD_INVALIDA, auditar_arquivo
from produtos.esquema import validar_produto
from produtos.registro import Versao
from produtos.tempo import parse_data
from produtos.tests.base_v11 import AGORA, BaseV11, a_com, a_expirada, b_de, instantaneo, produto_a, produto_b, uid
from produtos.tests.test_v11_carrossel import CAT, CarrosselBase
from produtos.tests.test_v11_p08 import FATO, P08Base, reexporta

CHAVE = "EXEMPLO_A__A001"
RAS, PUB = estados.APROVADO_RASCUNHO, estados.APROVADO_PUBLICACAO


def versao(obj, n=1):
    return Versao(f"v{n}.json", "0" * 64, validar_produto(obj, AGORA).dados, parse_data(obj["exportedAt"]))


# ------------------------------------------------------------------ item 2: valores das divergências A × B
class DivergenciaValoresTest(P08Base):
    def ab(self, a_vers, b_vers, tipo=RAS, data="2026-11-17T14:00:00Z", decisao_n=1):
        a = {f"a{i}.json": v for i, v in enumerate(a_vers, 1)}
        b = {f"b{i}.json": v for i, v in enumerate(b_vers, 1)}
        _, f = self.rodar(a=a, b=b, humanos=self.humanos(decisoes=[self.dec(decisao_n, tipo, data=data)]))
        return f[CHAVE]

    def b_div(self, n, exportado, **over):
        base = {"product__title": "Título Divergente de B", "exportedAt": exportado}
        base.update(over)
        return b_de(n, **base)

    def test_divergencia_preexistente_inalterada_nao_invalida_com_reexportacao_tecnica(self):
        b1 = self.b_div(4, "2026-11-17T13:30:00Z")
        b2 = self.b_div(5, "2026-11-17T14:50:00Z", price__amountCents=1, availability="unknown")   # só preço e disponibilidade de B
        for tipo in (RAS, PUB):
            self.setUp()
            f = self.ab([a_com(1)], [b1, b2], tipo)
            self.assertEqual((f["estado"], f["decisoesInaplicaveis"]), (tipo, []), tipo)

    def test_formatacao_nao_invalida(self):
        b1 = self.b_div(4, "2026-11-17T13:30:00Z")
        casos = {"product__title": "  TÍTULO   divergente de b ", "product__store": " loja   FICTÍCIA ",
                 "product__officialUrl": "HTTPS://WWW.LOJAFICTICIA.EXAMPLE/produto/a001/"}
        for campo, valor in casos.items():
            self.setUp()
            b1 = b_de(4, **{campo: "x" if campo == "product__title" else valor.upper().replace("LOJA", "Outra")},
                      exportedAt="2026-11-17T13:30:00Z")
            # revisão com B divergente no campo; B reexportado com o MESMO valor escrito de outro jeito
            v1 = {"product__title": "Título Divergente", "product__store": "Outra Loja",
                  "product__officialUrl": "https://www.outra.example/p/1"}[campo]
            v2 = {"product__title": "  TÍTULO   divergente ", "product__store": "  OUTRA   loja ",
                  "product__officialUrl": "HTTPS://WWW.OUTRA.EXAMPLE/p/1/"}[campo]
            f = self.ab([a_com(1)], [b_de(4, **{campo: v1}, exportedAt="2026-11-17T13:30:00Z"),
                                     b_de(5, **{campo: v2}, exportedAt="2026-11-17T14:50:00Z")])
            self.assertEqual((f["estado"], f["decisoesInaplicaveis"]), (RAS, []), campo)

    def test_valor_divergente_materialmente_diferente_invalida_rascunho_e_publicacao(self):
        b1, b2 = self.b_div(4, "2026-11-17T13:30:00Z"), self.b_div(5, "2026-11-17T14:50:00Z", product__title="Terceiro Título Distinto")
        for tipo in (RAS, PUB):
            self.setUp()
            f = self.ab([a_com(1)], [b1, b2], tipo)
            ent = self.invalida(f, "divergencia_ab_alterada")
            self.assertEqual((ent["campos"], ent["divergenciasAlteradas"]), (["title"], {"title": "valor_alterado"}))
            self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)

    def test_url_oficial_com_valor_diferente_invalida(self):
        b1 = b_de(4, product__officialUrl="https://www.outra.example/p/1", exportedAt="2026-11-17T13:30:00Z")
        b2 = b_de(5, product__officialUrl="https://www.outra.example/p/2", exportedAt="2026-11-17T14:50:00Z")
        ent = self.invalida(self.ab([a_com(1)], [b1, b2]), "divergencia_ab_alterada")
        self.assertEqual(ent["divergenciasAlteradas"], {"officialUrl": "valor_alterado"})

    def test_campo_novo_e_distinto_de_valor_alterado(self):
        b1 = self.b_div(4, "2026-11-17T13:30:00Z")
        b2 = self.b_div(5, "2026-11-17T14:50:00Z", product__store="Outra Loja")                  # title igual; store NOVO
        ent = self.invalida(self.ab([a_com(1)], [b1, b2]), "divergencia_ab_alterada")
        self.assertEqual(ent["divergenciasAlteradas"], {"store": "novo"})

    def test_reducao_do_conjunto_de_divergencias_continua_valida(self):
        b1 = self.b_div(4, "2026-11-17T13:30:00Z", product__store="Outra Loja")
        b2 = self.b_div(5, "2026-11-17T14:50:00Z")                                                 # a loja convergiu
        f = self.ab([a_com(1)], [b1, b2])
        self.assertEqual((f["estado"], f["impressaoMaterialDecisao"]["divergenciasAtuais"]), (RAS, ["title"]))
        self.setUp()
        b3 = b_de(5, exportedAt="2026-11-17T14:50:00Z")                                            # convergiu totalmente
        f = self.ab([a_com(1)], [b1, b3])
        self.assertEqual((f["estado"], f["impressaoMaterialDecisao"]["divergenciasAtuais"]), (RAS, []))

    def test_caracteristicas_divergentes_valor_e_formatacao(self):
        a = a_com(1, verifiedFacts=[FATO])
        outra = {**FATO, "text": "Característica totalmente outra"}
        b1 = b_de(4, exportedAt="2026-11-17T13:30:00Z", verifiedFacts=[outra])                       # revisada já divergente
        # valor materialmente diferente do fato divergente de B -> invalida
        b2 = b_de(5, exportedAt="2026-11-17T14:50:00Z", verifiedFacts=[{**FATO, "text": "Um terceiro fato bem diferente"}])
        ent = self.invalida(self.ab([a], [b1, b2]), "divergencia_ab_alterada")
        self.assertEqual(ent["divergenciasAlteradas"], {"verifiedFacts": "valor_alterado"})
        # só formatação do mesmo fato (caixa e espaços) -> continua válida
        self.setUp()
        b3 = b_de(5, exportedAt="2026-11-17T14:50:00Z", verifiedFacts=[{**outra, "text": "  CARACTERÍSTICA   totalmente OUTRA "}])
        f = self.ab([a], [b1, b3])
        self.assertEqual((f["estado"], f["decisoesInaplicaveis"]), (RAS, []))

    def test_data_de_verificacao_e_exportid_de_b_nao_contam(self):
        b1 = self.b_div(4, "2026-11-17T13:30:00Z", verifiedFacts=[FATO])
        b2 = self.b_div(5, "2026-11-17T14:50:00Z", verifiedFacts=[{**FATO, "verifiedAt": "2026-11-17T09:00:00Z"}])
        a = a_com(1, verifiedFacts=[{**FATO, "text": "Característica de A"}])
        f = self.ab([a], [b1, b2])
        self.assertEqual(f["estado"], RAS)

    def test_revisada_na_fonte_b_quando_a_expirou_tambem_reconhece_mudanca_de_valor_de_a(self):
        a1 = a_expirada(1, product__title="Título Divergente de A", exportedAt="2026-11-17T12:00:00Z")
        a2 = a_expirada(2, product__title="Outro Título de A Muito Diferente", exportedAt="2026-11-17T14:50:00Z")
        b = b_de(4, exportedAt="2026-11-17T13:00:00Z")
        _, fs = self.rodar(a={"a1.json": a1, "a2.json": a2}, b={"b.json": b},
                           humanos=self.humanos(decisoes=[self.dec(4, RAS, data="2026-11-17T14:00:00Z")]))
        f = fs[CHAVE]
        self.assertEqual(f["origem"], "B")
        self.invalida(f, "divergencia_ab_alterada")

    def test_preco_e_disponibilidade_continuam_pelo_portao_nao_pela_divergencia(self):
        b1 = self.b_div(4, "2026-11-17T13:30:00Z")
        b2 = self.b_div(5, "2026-11-17T14:50:00Z", price__amountCents=1, availability="unknown")
        r = self.ab([a_com(1), reexporta(2, price__amountCents=9990)], [b1, b2], PUB)           # preço de A mudou, aprovação de publicação
        self.invalida(r, "preco_mudou")
        self.setUp()
        self.assertEqual(self.ab([a_com(1), reexporta(2, price__amountCents=9990)], [b1, b2], RAS)["estado"], RAS)  # editorial sobrevive

    def test_utilitarios_de_valor(self):
        v = lambda o, n=1: versao(o, n)
        a = v(a_com(1))
        b = v(b_de(4, product__title="X Diferente", product__officialUrl="https://www.outra.example/p/1/"), 4)
        itens = imp.divergencias_itens(a, b)
        self.assertEqual(sorted(itens), ["officialUrl", "title"])
        self.assertEqual(itens["officialUrl"][1], "https://www.outra.example/p/1")
        self.assertEqual(imp._url("HTTPS://Exemplo.EXAMPLE:443/a/b/#x"), "https://exemplo.example/a/b")
        self.assertNotEqual(imp._url("https://x.example/A"), imp._url("https://x.example/a"))   # caminho é sensível a caixa
        self.assertEqual(imp.divergencia_alterada_itens({}, {}), {})
        self.assertEqual(imp.divergencia_alterada_itens({"title": ("a", "b")}, {"title": ("a", "b")}), {})
        self.assertEqual(imp.divergencia_alterada_itens({"title": ("a", "b"), "store": ("c", "d")}, {"title": ("a", "b")}), {})
        self.assertEqual(imp.divergencia_alterada_itens({"title": ("a", "b")}, {"title": ("a", "z")}), {"title": "valor_alterado"})
        self.assertEqual(imp.divergencia_alterada_itens({}, {"store": ("c", "d")}), {"store": "novo"})


# ------------------------------------------------------------------ item 1: impressão e decisões
class ImpressaoEDecisoesTest(P08Base):
    def escrever_decisoes(self, itens):
        h = self.humanos()
        p = self.hum / "decisoes.json"
        p.write_text(json.dumps({"decisoesVersion": "1.0", "decisoes": itens}))
        return {**h, "decisoes_arquivo": p}

    def test_impressao_fornecida_pelo_arquivo_nunca_e_aceita_mesmo_se_correta(self):
        correta = imp.impressao(versao(a_com(1)), RAS)
        d = {**self.dec(1, RAS), "impressao": correta}
        r, fs = self.rodar(a={"a.json": a_com(1)}, humanos=self.escrever_decisoes([d]))
        f = fs[CHAVE]
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)                      # nada foi aprovado
        self.assertIsNone(f["decisaoHumana"])
        x = f["decisoesInvalidasNoArquivo"][0]
        self.assertEqual((x["indice"], x["codigos"], x["campos"]), (1, [COD_INVALIDA, COD_IMPRESSAO], ["impressao"]))
        self.assertIn("sem validação de procedência", x["motivo"])
        self.assertEqual(r["decisoesArquivo"], {"status": "ok", "invalidas": 1})
        self.assertNotIn(correta, json.dumps(r) + json.dumps(f))                      # o valor fornecido nunca é ecoado

    def test_nomes_alternativos_de_impressao(self):
        for nome in ("fingerprint", "impressaoMaterial", "digest", "hash_material"):
            self.setUp()
            _, fs = self.rodar(a={"a.json": a_com(1)}, humanos=self.escrever_decisoes([{**self.dec(1, RAS), nome: "x" * 8}]))
            self.assertIn(COD_IMPRESSAO, fs[CHAVE]["decisoesInvalidasNoArquivo"][0]["codigos"], nome)
            self.assertEqual(fs[CHAVE]["estado"], estados.PENDENTE_REVISAO)

    def test_campo_extra_comum_e_decisao_invalida_sao_estruturados_sem_o_codigo_de_impressao(self):
        itens = [{**self.dec(1, RAS), "comentario": "x"}, {**self.dec(1, RAS), "data": "ontem"}, "texto solto"]
        r, fs = self.rodar(a={"a.json": a_com(1)}, humanos=self.escrever_decisoes(itens))
        inv = r["decisoesInvalidasNoArquivo"]
        self.assertEqual([x["codigos"] for x in inv], [[COD_INVALIDA], [COD_INVALIDA], [COD_INVALIDA]])
        self.assertEqual([x["produto"] for x in inv], ["EXEMPLO_A/A001", "EXEMPLO_A/A001", None])
        self.assertEqual(len(fs[CHAVE]["decisoesInvalidasNoArquivo"]), 2)
        self.assertTrue(any("não aceita" in a for a in r["avisos"]))

    def test_decisoes_antigas_sem_impressao_continuam_valendo(self):
        r, fs = self.rodar(a={"a1.json": a_com(1), "a2.json": reexporta(2)}, humanos=self.escrever_decisoes([self.dec(1, PUB)]))
        self.assertEqual(fs[CHAVE]["estado"], PUB)
        self.assertEqual((r["decisoesInvalidasNoArquivo"], r["decisoesArquivo"]), ([], {"status": "ok", "invalidas": 0}))
        self.assertEqual(fs[CHAVE]["decisoesInvalidasNoArquivo"], [])

    def test_versao_historica_indisponivel_fica_explicita_e_conservadora(self):
        r, fs = self.rodar(a={"a.json": a_com(2)}, humanos=self.escrever_decisoes([self.dec(99, RAS)]))
        f = fs[CHAVE]
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)
        d = f["decisoesInaplicaveis"][0]
        self.assertEqual((d["codigo"], d["impressaoComparavel"]), ("versao_desconhecida", False))
        self.assertEqual(r["decisoesInaplicaveis"][0]["impressaoComparavel"], False)
        self.assertTrue(any("versao_desconhecida" in a for a in r["avisos"]))

    def test_decisoes_inaplicaveis_preservadas_com_as_chaves_antigas_e_novas(self):
        _, fs = self.rodar(a={"a1.json": a_com(1), "a2.json": reexporta(2, product__title="Outro")},
                           humanos=self.escrever_decisoes([self.dec(1, RAS)]))
        d = fs[CHAVE]["decisoesInaplicaveis"][0]
        for k in ("exportId", "decisao", "autor", "data", "motivo", "codigo"):
            self.assertIn(k, d)
        self.assertEqual((d["codigo"], d["codigos"], d["campos"]), ("identidade_mudou", ["identidade_mudou"], ["title"]))

    def test_impressao_decisao_expoe_o_que_foi_comparado(self):
        _, fs = self.rodar(a={"a1.json": a_com(1), "a2.json": reexporta(2)}, humanos=self.escrever_decisoes([self.dec(1, RAS)]))
        im = fs[CHAVE]["impressaoMaterialDecisao"]
        self.assertEqual((im["impressaoRevisada"], im["impressaoVersao"]), (im["impressaoAtual"], imp.IMPRESSAO_VERSAO))
        self.assertIsNone(im["outraFonteDisponivelNaRevisao"])

    def test_auditoria_status_do_arquivo(self):
        self.assertEqual(auditar_arquivo(None)["status"], "nao_informado")
        self.assertEqual(auditar_arquivo(self.tmp / "nao_existe.json")["status"], "ausente")
        for conteudo in ("{quebrado", "[]", '{"decisoes": 5}'):
            p = self.tmp / "d.json"
            p.write_text(conteudo)
            self.assertEqual(auditar_arquivo(p)["status"], "invalido", conteudo)

    def test_arquivo_de_decisoes_nunca_e_alterado(self):
        h = self.escrever_decisoes([{**self.dec(1, RAS), "impressao": "abc"}])
        gravar = lambda: self.rodar(a={"a.json": a_com(1)}, humanos=h)
        gravar()
        antes = {k: v for k, v in instantaneo(self.hum).items()}
        gravar()
        self.assertEqual(antes, instantaneo(self.hum))

    def test_formato_e_carregador_do_modo_1_0_nao_mudaram(self):
        p = self.tmp / "d.json"
        p.write_text(json.dumps({"decisoesVersion": "1.0", "decisoes": [{**self.dec(1, RAS), "impressao": "abc"}, self.dec(1, RAS)]}))
        c = dec_v1.carregar(p)
        self.assertEqual(len(c.por_produto[("EXEMPLO_A", "A001")]), 1)                # a com campo extra continua ignorada
        self.assertEqual(c.avisos, ["decisão #1 ignorada: campos desconhecidos"])


# ------------------------------------------------------------------ item 3: bloqueios normais do carrossel
class BloqueiosNormaisTest(CarrosselBase):
    def test_lote_misto_sem_tratamento_de_excecao(self):
        _, fs = self.rodar(a={"a.json": a_com(1), "e.json": a_expirada(2, "A002"), "b.json": a_com(3, "A003")},
                           b={"b.json": produto_b(4, "B001")}, humanos=self.humanos(decisoes=[{
                               "provider": "EXEMPLO_A", "productId": "A001", "exportId": uid(1), "decisao": RAS,
                               "autor": "Maria Revisora", "data": "2026-11-17T14:30:00Z", "motivo": "t"}]))
        status = {k: self.gerar(f)["status"] for k, f in sorted(fs.items())}               # nenhuma exceção
        self.assertEqual(status["EXEMPLO_A__A001"], "rascunho")
        self.assertEqual(status["EXEMPLO_B__B001"], "rascunho")
        self.assertEqual(status["EXEMPLO_A__A002"], "bloqueado")                           # expirada
        self.assertEqual(status["EXEMPLO_A__A003"], "bloqueado")                           # pendente de revisão

    def test_relatorio_de_bloqueio_tem_as_mesmas_chaves_do_resultado_normal(self):
        ok = self.gerar(self.ficha_a())
        bl = self.gerar({**self.ficha_a(), "estado": "expirado"}, alegacoes=[{"id": "p", "tipo": "preco", "funcao": "essencial"}])
        self.assertEqual(set(ok), set(bl))
        self.assertIsNone(bl["portao"])
        self.assertRegex(bl["t_publicacao_avaliado"], r"^2026-11-17T15:00:00Z$")

    def test_origem_desconhecida_tambem_e_bloqueio(self):
        r = self.gerar({**self.ficha_a(), "origem": "?"})
        self.assertEqual((r["status"], r["bloqueios"][0]["estados_elegiveis"]), ("bloqueado", []))

    def test_chamada_invalida_continua_sendo_excecao_de_programacao(self):
        f = self.ficha_a()
        for kw in (dict(t_publicacao=AGORA.replace(tzinfo=None)), dict(recurso_visual="foto_qualquer")):
            with self.assertRaises(CarrosselRecusado):
                self.gerar(f, **kw)
        with self.assertRaises(CarrosselRecusado):
            self.gerar({**f, "contrato": "1.0"})
        with self.assertRaises(CarrosselRecusado):
            self.gerar(f, alegacoes=[{"id": "x", "tipo": "preco", "funcao": "talvez"}])

    def test_bloqueio_por_estado_nao_avalia_o_portao_nem_gera_slides(self):
        r = self.gerar({**self.ficha_b(), "estado": "expirado"}, alegacoes=[{"id": "p", "tipo": "preco", "funcao": "essencial"}])
        self.assertEqual((r["carrossel"], r["alegacoes_omitidas"], r["legenda_sugerida"]), (None, [], ""))


if __name__ == "__main__":
    unittest.main()
