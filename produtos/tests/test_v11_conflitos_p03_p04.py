"""P-03: política de conflitos A × B (contrato §16.3). P-04: decisão humana inaplicável é sempre registrada."""
import json
import unittest
from datetime import timedelta

from produtos import estados
from produtos.conflitos_v11 import CODIGOS
from produtos.tests.base_v11 import (AGORA, FMT, BaseV11, a_com, a_expirada, b_de, permissao, produto_a, produto_b, uid)

CHAVE = "EXEMPLO_A__A001"
FATO = {"text": "Característica fictícia", "sourceRef": "Página fictícia", "verifiedAt": "2026-11-16T12:00:00Z"}


class Base2(BaseV11):
    def conflito(self, a, b, decisoes=None, permissoes=None, agora=AGORA):
        h = self.humanos(decisoes=decisoes, permissoes=permissoes)
        return self.rodar(a={"a.json": a} if a is not None else None, b={"b.json": b} if b is not None else None,
                          humanos=h, agora=agora)

    def ficha(self, a, b, **kw):
        r, f = self.conflito(a, b, **kw)
        return f[CHAVE], r

    def dec(self, n, decisao="aprovado_para_rascunho", data="2026-11-17T14:30:00Z"):
        return {"provider": "EXEMPLO_A", "productId": "A001", "exportId": uid(n), "decisao": decisao,
                "autor": "Maria Revisora", "data": data, "motivo": "teste"}


class PoliticaABTest(Base2):
    def test_a_valida_prevalece_e_b_fornece_dados_editoriais(self):
        f, r = self.ficha(a_com(1), b_de(4))
        self.assertEqual((f["origem"], f["fonteSelecionada"], f["estado"]), ("A", "A", estados.PENDENTE_REVISAO))
        self.assertIsNone(f["divergenciasAB"])
        self.assertEqual(f["editorialB"]["exportId"], uid(4))
        self.assertEqual(f["preco"]["exibicao"], "R$ 129,90")                          # preço de A, nunca de B
        self.assertEqual(r["conflitosAB"], [{"produto": "EXEMPLO_A/A001", "fonteSelecionada": "A", "divergencias": [],
                                              "estadoDaFonteA": estados.PENDENTE_REVISAO}])

    def test_a_nunca_e_substituida_por_b_mesmo_mais_recente(self):
        f, _ = self.ficha(a_com(1), b_de(4, exportedAt="2026-11-17T14:50:00Z"))
        self.assertEqual((f["origem"], f["versao"]["exportId"]), ("A", uid(1)))

    def test_categoria_de_b_e_so_sugestao_visivel(self):
        a = a_com(1, product__category=None, product__categoryOrigin=None)
        f, _ = self.ficha(a, b_de(4))
        self.assertIsNone(f["produto"]["category"])                                    # A não é preenchida por B
        self.assertEqual(f["editorialB"]["category"], "Casa e Cozinha > Utensílios")

    def test_a_expirada_nao_autoriza_comercial_e_b_continua_como_rascunho_editorial(self):
        f, r = self.ficha(a_expirada(1), b_de(4))
        self.assertEqual((f["origem"], f["fonteSelecionada"], f["estado"]), ("B", "B", estados.CANDIDATO_NAO_VERIFICADO))
        self.assertIsNone(f["preco"]["exibicao"])
        self.assertIs(f["alegacaoComercialPermitida"], False)
        fc = f["fonteComercial"]
        self.assertEqual((fc["fonte"], fc["estadoAutomatico"], fc["alegacaoComercialPermitida"]), ("A", estados.EXPIRADO, False))
        self.assertTrue(any("A expirada" in a or "A expirada".lower() in a.lower() for a in f["avisos"] + f["pendencias"]))
        self.assertEqual(r["conflitosAB"][0]["fonteSelecionada"], "B")

    def test_a_expirada_sem_b_continua_expirado(self):
        f, _ = self.ficha(a_expirada(1), None)
        self.assertEqual(f["estado"], estados.EXPIRADO)

    def test_a_expirada_nao_recai_em_publicacao_mesmo_com_aprovacao_previa_em_a(self):
        d = [self.dec(1, "aprovado_para_publicacao")]
        f, _ = self.ficha(a_expirada(1), b_de(4), decisoes=d)
        self.assertEqual(f["estado"], estados.CANDIDATO_NAO_VERIFICADO)                # aprovação de A não é transferida a B
        self.assertEqual([x["codigo"] for x in f["decisoesInaplicaveis"]], ["fonte_nao_selecionada"])

    def test_a_indisponivel_continua_invalidada_e_nao_recai_em_b(self):
        f, _ = self.ficha(a_com(1, availability="out_of_stock"), b_de(4))
        self.assertEqual((f["origem"], f["estado"]), ("A", estados.INVALIDADO))

    def test_a_sem_foto_humana_continua_incompleta_com_b_ao_lado(self):
        f, _ = self.ficha(a_com(1), b_de(4), permissoes=[])
        self.assertEqual((f["estado"], f["editorialB"]["exportId"]), (estados.INCOMPLETO, uid(4)))

    def test_nunca_ha_aprovacao_automatica(self):
        for a in (a_com(1), a_expirada(1)):
            f, _ = self.ficha(a, b_de(4))
            self.assertNotIn(f["estado"], (estados.APROVADO_RASCUNHO, estados.APROVADO_PUBLICACAO))
            self.assertIsNone(f["decisaoHumana"])

    def test_aprovacao_humana_de_b_vale_como_rascunho_quando_a_expirou(self):
        f, _ = self.ficha(a_expirada(1), b_de(4), decisoes=[self.dec(4)])
        self.assertEqual(f["estado"], estados.APROVADO_RASCUNHO)
        self.assertEqual(f["decisoesInaplicaveis"], [])

    def test_b_nunca_e_aprovada_para_publicacao_no_fallback(self):
        f, _ = self.ficha(a_expirada(1), b_de(4), decisoes=[self.dec(4, "aprovado_para_publicacao")])
        self.assertEqual(f["estado"], estados.CANDIDATO_NAO_VERIFICADO)
        self.assertEqual(f["decisoesInaplicaveis"][0]["codigo"], "fonte_b_sem_publicacao")

    def test_aprovacao_sobre_versao_de_b_nao_vale_quando_a_prevalece(self):
        f, _ = self.ficha(a_com(1), b_de(4), decisoes=[self.dec(4)])
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)
        self.assertEqual(f["decisoesInaplicaveis"][0]["codigo"], "fonte_nao_selecionada")
        self.assertTrue(any("INAPLICÁVEL" in a for a in f["avisos"]))

    def test_rejeicao_humana_vale_mesmo_sobre_a_outra_fonte(self):
        f, _ = self.ficha(a_com(1), b_de(4), decisoes=[self.dec(4, "rejeitado")])
        self.assertEqual(f["estado"], estados.REJEITADO)
        self.assertEqual(f["decisoesInaplicaveis"], [])

    def test_permissao_de_foto_nao_e_substituida_por_nenhuma_fonte(self):
        f, _ = self.ficha(a_expirada(1), b_de(4))                                      # registro humano existe
        self.assertTrue(f["foto"]["utilizavel"])
        f2, _ = self.ficha(a_com(1), b_de(4), permissoes=[])                           # A "confirmou" a foto, mas nada humano
        self.assertFalse(f2["foto"]["utilizavel"])
        self.assertEqual(f2["foto"]["usePermission"], "confirmada")
        f3, _ = self.ficha(a_com(1), b_de(4), permissoes=[permissao(status="negada")])
        self.assertFalse(f3["foto"]["utilizavel"])

    def test_historico_guarda_as_duas_fontes(self):
        _, _ = self.ficha(a_com(1), b_de(4))
        h = json.loads((self.saida / "historico.json").read_text())
        self.assertEqual(sorted(v["fonte"] for v in h[0]["versoes"]), ["agente_publicada", "catalogo_candidato"])


class DivergenciaTest(Base2):
    def test_divergencia_de_identidade_exige_revisao(self):
        for campo, valor in (("title", "Outro Título Fictício"), ("store", "Outra Loja"),
                             ("officialUrl", "https://www.outra.example/p/9")):
            self.setUp()
            f, r = self.ficha(a_com(1), b_de(4, **{f"product__{campo}": valor}))
            self.assertEqual(f["estado"], estados.PENDENTE_REVISAO, campo)
            self.assertEqual(f["divergenciasAB"]["campos"], [campo])
            self.assertTrue(any("Divergência A × B" in a for a in f["avisos"]))
            self.assertEqual(r["conflitosAB"][0]["divergencias"], [campo])

    def test_divergencia_de_caracteristicas(self):
        f, _ = self.ficha(a_com(1, verifiedFacts=[FATO]), b_de(4))
        self.assertEqual(f["divergenciasAB"]["campos"], ["verifiedFacts"])
        f2, _ = self.ficha(a_com(1, verifiedFacts=[FATO]), b_de(4, verifiedFacts=[{**FATO, "verifiedAt": "2026-11-15T10:00:00Z"}]))
        self.assertIsNone(f2["divergenciasAB"])                                        # só a data difere: mesma característica

    def test_divergencia_nao_vaza_dado_de_b_para_a(self):
        f, _ = self.ficha(a_com(1), b_de(4, product__title="Título Divergente de B"))
        self.assertEqual(f["produto"]["title"], "Produto Fictício A001")

    def test_aprovacao_exige_decisao_posterior_as_duas_exportacoes(self):
        b = b_de(4, product__title="Outro Título Fictício", exportedAt="2026-11-17T14:45:00Z")
        antes = self.dec(1, data="2026-11-17T14:30:00Z")                               # anterior ao B divergente
        f, _ = self.ficha(a_com(1), b, decisoes=[antes])
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)
        self.assertEqual(f["decisoesInaplicaveis"][0]["codigo"], "divergencia_ab_pendente_revisao")
        self.setUp()
        depois = self.dec(1, data="2026-11-17T14:55:00Z")                              # revisão já com a divergência
        f2, _ = self.ficha(a_com(1), b, decisoes=[depois])
        self.assertEqual(f2["estado"], estados.APROVADO_RASCUNHO)
        self.assertEqual(f2["decisoesInaplicaveis"], [])

    def test_divergencia_com_b_no_fallback_tambem_exige_revisao(self):
        f, _ = self.ficha(a_expirada(1), b_de(4, product__store="Outra Loja"))
        self.assertEqual((f["origem"], f["estado"]), ("B", estados.PENDENTE_REVISAO))
        self.assertEqual(f["divergenciasAB"]["campos"], ["store"])

    def test_divergencia_nao_mascara_estado_expirado_invalidado_ou_incompleto(self):
        f, _ = self.ficha(a_com(1, availability="out_of_stock"), b_de(4, product__title="Outro Título"))
        self.assertEqual(f["estado"], estados.INVALIDADO)
        self.setUp()
        f2, _ = self.ficha(a_com(1), b_de(4, product__title="Outro Título"), permissoes=[])
        self.assertEqual(f2["estado"], estados.INCOMPLETO)


class DecisoesInaplicaveisP04Test(Base2):
    def a_unica(self, produto, decisoes, **kw):
        r, f = self.rodar(a={"a.json": produto}, humanos=self.humanos(decisoes=decisoes), **kw)
        return f[CHAVE], r

    def codigos(self, f):
        return [d["codigo"] for d in f["decisoesInaplicaveis"]]

    def test_versao_desconhecida(self):
        f, r = self.a_unica(a_com(1), [self.dec(77)])
        self.assertEqual(self.codigos(f), ["versao_desconhecida"])
        self.assertIn("versao_desconhecida", r["decisoesInaplicaveis"][0]["codigo"])
        self.assertTrue(any("decisão humana inaplicável (versao_desconhecida)" in a for a in r["avisos"]))

    def test_preco_e_identidade_mudaram(self):
        a = {"a1.json": a_com(1), "a2.json": a_com(2, exportedAt="2026-11-17T14:00:00Z", price__amountCents=1)}
        r, f = self.rodar(a=a, humanos=self.humanos(decisoes=[self.dec(1)]))
        self.assertEqual(self.codigos(f[CHAVE]), ["preco_mudou"])
        self.setUp()
        a = {"a1.json": a_com(1), "a2.json": a_com(2, exportedAt="2026-11-17T14:00:00Z", product__title="Outro")}
        r, f = self.rodar(a=a, humanos=self.humanos(decisoes=[self.dec(1)]))
        self.assertEqual(self.codigos(f[CHAVE]), ["identidade_mudou"])

    def test_estado_automatico_nao_permite(self):
        f, _ = self.a_unica(a_expirada(1), [self.dec(1)])
        self.assertEqual((f["estado"], self.codigos(f)), (estados.EXPIRADO, ["estado_nao_permite"]))

    def test_b_para_publicacao(self):
        r, fs = self.rodar(b={"b.json": produto_b(4, "B001")},
                           humanos=self.humanos(decisoes=[{**self.dec(4, "aprovado_para_publicacao"), "provider": "EXEMPLO_B",
                                                           "productId": "B001"}]))
        self.assertEqual(self.codigos(fs["EXEMPLO_B__B001"]), ["fonte_b_sem_publicacao"])

    def test_data_futura_e_anterior_a_exportacao(self):
        f, _ = self.a_unica(a_com(1), [self.dec(1, data="2026-11-18T10:00:00Z")])
        self.assertEqual(self.codigos(f), ["data_futura"])
        self.setUp()
        f, _ = self.a_unica(a_com(1), [self.dec(1, data="2026-11-17T09:00:00Z")])
        self.assertEqual(self.codigos(f), ["anterior_a_exportacao"])

    def test_decisao_superada_por_outra_mais_recente_aparece(self):
        decs = [self.dec(1, "aprovado_para_rascunho", "2026-11-17T14:00:00Z"), self.dec(1, "rejeitado", "2026-11-17T14:20:00Z")]
        f, _ = self.a_unica(a_com(1), decs)
        self.assertEqual(f["estado"], estados.REJEITADO)
        self.assertEqual([(d["decisao"], d["codigo"]) for d in f["decisoesInaplicaveis"]],
                         [("aprovado_para_rascunho", "superada_por_decisao_mais_recente")])

    def test_decisao_aplicada_nao_e_listada_como_inaplicavel(self):
        f, r = self.a_unica(a_com(1), [self.dec(1)])
        self.assertEqual((f["estado"], f["decisoesInaplicaveis"], r["decisoesInaplicaveis"]), (estados.APROVADO_RASCUNHO, [], []))

    def test_decisao_sobre_produto_ausente_das_fontes(self):
        d = {**self.dec(1), "productId": "NAO-EXISTE"}
        r, _ = self.rodar(a={"a.json": a_com(1)}, humanos=self.humanos(decisoes=[d]))
        self.assertEqual(r["decisoesSemProduto"], [{"produto": "EXEMPLO_A/NAO-EXISTE", "exportId": uid(1),
                                                    "decisao": "aprovado_para_rascunho", "codigo": "produto_ausente"}])
        self.assertTrue(any("sem produto nas fontes lidas" in a for a in r["avisos"]))

    def test_decisao_de_lote_em_quarentena_fica_sem_produto(self):
        from produtos.tests.base_v11 import gravar_lote
        gravar_lote(self.exp / "A", {"a.json": a_com(1)}, manifesto=False)
        gravar_lote(self.exp / "B", {"b.json": produto_b(4, "B001")})
        r, f = self.rodar(humanos=self.humanos(decisoes=[self.dec(1)]))
        self.assertEqual([x["codigo"] for x in r["decisoesSemProduto"]], ["produto_ausente"])

    def test_nada_e_concedido_e_todos_os_codigos_sao_conhecidos(self):
        casos = [[self.dec(77)], [self.dec(1, data="2026-11-18T10:00:00Z")], [self.dec(1, data="2026-11-17T09:00:00Z")]]
        for decs in casos:
            self.setUp()
            f, _ = self.a_unica(a_com(1), decs)
            self.assertNotIn(f["estado"], (estados.APROVADO_RASCUNHO, estados.APROVADO_PUBLICACAO))
            self.assertTrue(all(d["codigo"] in CODIGOS for d in f["decisoesInaplicaveis"]))

    def test_markdown_e_ficha_mostram_a_ocorrencia(self):
        self.a_unica(a_com(1), [self.dec(77)])
        md = (self.saida / "fichas" / f"{CHAVE}.md").read_text()
        self.assertIn("Decisão inaplicável (`versao_desconhecida`)", md)


if __name__ == "__main__":
    unittest.main()
