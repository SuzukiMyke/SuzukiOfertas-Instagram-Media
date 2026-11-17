"""Modo 1.1: validade (teto 24 h), estados, B, decisões humanas, identidade, preço e fatos."""
import unittest
from datetime import timedelta

from produtos import estados
from produtos.avaliacao_v11 import ConfiguracaoV11
from produtos.tests.base_v11 import AGORA, BaseV11, produto_a, produto_b

FMT = "%Y-%m-%dT%H:%M:%SZ"


def a_com(n=1, pid="A001", verificado_ha=timedelta(hours=1), valido_ate=timedelta(hours=4), **over):
    return produto_a(n, pid, price__verifiedAt=(AGORA - verificado_ha).strftime(FMT),
                     price__validUntil=(AGORA + valido_ate).strftime(FMT), **over)


class ConfiguracaoTest(BaseV11):
    def test_teto_de_24h_nao_pode_ser_desativado_nem_aumentado(self):
        for ruim in (None, 25, 24.01, 0, -1, True, "24"):
            with self.assertRaises(ValueError, msg=repr(ruim)):
                ConfiguracaoV11(revalidacao_horas=ruim)
        self.assertEqual(ConfiguracaoV11(revalidacao_horas=24).revalidacao_horas, 24)
        self.assertEqual(ConfiguracaoV11(revalidacao_horas=6).revalidacao_horas, 6)

    def test_outros_parametros_e_contrato(self):
        for kw in (dict(fatos_dias=0), dict(margem_publicacao_min=-1), dict(contrato="1.0")):
            with self.assertRaises(ValueError):
                ConfiguracaoV11(**kw)

    def test_estados_do_modo_1_0_nao_mudaram(self):
        self.assertNotIn(estados.CANDIDATO_NAO_VERIFICADO, estados.TODOS)
        self.assertIn(estados.CANDIDATO_NAO_VERIFICADO, estados.TODOS_V11)
        self.assertEqual(len(estados.TODOS), 8)


class ValidadeTest(BaseV11):
    def estado(self, produto, agora=AGORA, cfg=None):
        _, f = self.rodar(a={"a.json": produto}, agora=agora, cfg=cfg)
        return f["EXEMPLO_A__A001"]

    def test_dentro_da_validade_com_foto_humana_e_pendente_revisao(self):
        self.assertEqual(self.estado(a_com())["estado"], estados.PENDENTE_REVISAO)

    def test_limite_de_validuntil_e_inclusivo(self):
        p = a_com(valido_ate=timedelta(0))
        self.assertEqual(self.estado(p)["estado"], estados.PENDENTE_REVISAO)
        self.assertEqual(self.estado(p, agora=AGORA + timedelta(seconds=1))["estado"], estados.EXPIRADO)

    def test_teto_de_24h_da_verificacao_mesmo_com_validuntil_maior(self):
        p = a_com(verificado_ha=timedelta(hours=24), valido_ate=timedelta(hours=40))
        self.assertEqual(self.estado(p)["estado"], estados.PENDENTE_REVISAO)           # exatamente 24 h: inclusivo
        p2 = a_com(verificado_ha=timedelta(hours=24, seconds=1), valido_ate=timedelta(hours=40))
        f = self.estado(p2)
        self.assertEqual(f["estado"], estados.EXPIRADO)
        self.assertIn("24", f["motivoEstadoAutomatico"])

    def test_janela_menor_que_24h_e_permitida(self):
        p = a_com(verificado_ha=timedelta(hours=2), valido_ate=timedelta(hours=4))
        self.assertEqual(self.estado(p, cfg=ConfiguracaoV11(revalidacao_horas=1))["estado"], estados.EXPIRADO)

    def test_indisponivel_invalida_e_sem_foto_humana_fica_incompleto(self):
        self.assertEqual(self.estado(a_com(availability="out_of_stock"))["estado"], estados.INVALIDADO)
        sem_foto = self.rodar(a={"a.json": a_com()}, humanos=self.humanos(permissoes=[]))[1]["EXEMPLO_A__A001"]
        self.assertEqual(sem_foto["estado"], estados.INCOMPLETO)

    def test_permissao_exportada_pelo_agente_nao_concede_foto(self):
        p = a_com()
        self.assertEqual(p["photo"]["usePermission"], "confirmada")                     # o agente "confirma"...
        f = self.rodar(a={"a.json": p}, humanos=self.humanos(permissoes=[]))[1]["EXEMPLO_A__A001"]
        self.assertFalse(f["foto"]["utilizavel"])                                       # ...mas nada vale sem registro humano
        self.assertEqual(f["foto"]["usePermission"], "confirmada")                      # informativo
        self.assertIn("NÃO concede", f["foto"]["usePermissionObservacao"])
        self.assertEqual(f["estado"], estados.INCOMPLETO)

    def test_expirado_tem_precedencia_sobre_foto_ausente(self):
        f = self.rodar(a={"a.json": a_com(valido_ate=timedelta(hours=-1), verificado_ha=timedelta(hours=3))},
                       humanos=self.humanos(permissoes=[]))[1]["EXEMPLO_A__A001"]
        self.assertEqual(f["estado"], estados.EXPIRADO)


class FonteBTest(BaseV11):
    def test_b_e_candidato_nao_verificado_sem_preco_exibido(self):
        _, f = self.rodar(b={"b.json": produto_b(4, "B001")})
        ficha = f["EXEMPLO_B__B001"]
        self.assertEqual(ficha["estado"], estados.CANDIDATO_NAO_VERIFICADO)
        self.assertIsNone(ficha["preco"]["exibicao"])
        self.assertIs(ficha["alegacaoComercialPermitida"], False)
        self.assertTrue(any("NÃO verificada" in a for a in ficha["avisos"]))

    def test_b_aceita_rascunho_editorial_sem_foto(self):
        h = self.humanos(decisoes=[self.decisao(4, "B001", provider="EXEMPLO_B")])
        f = self.rodar(b={"b.json": produto_b(4, "B001")}, humanos=h)[1]["EXEMPLO_B__B001"]
        self.assertEqual(f["estado"], estados.APROVADO_RASCUNHO)

    def test_b_nunca_e_aprovada_para_publicacao(self):
        h = self.humanos(decisoes=[self.decisao(4, "B001", "aprovado_para_publicacao", provider="EXEMPLO_B")])
        f = self.rodar(b={"b.json": produto_b(4, "B001")}, humanos=h)[1]["EXEMPLO_B__B001"]
        self.assertEqual(f["estado"], estados.CANDIDATO_NAO_VERIFICADO)
        self.assertIn("nunca é aprovada para publicação", f["decisoesIgnoradas"][0]["ignoradaPorque"])

    def test_mudanca_de_preco_em_b_nao_invalida_aprovacao_editorial(self):
        b = {"b1.json": produto_b(4, "B001"),
             "b2.json": produto_b(5, "B001", exportedAt="2026-11-17T14:00:00Z", price__amountCents=1000)}
        h = self.humanos(decisoes=[self.decisao(4, "B001", provider="EXEMPLO_B")])
        f = self.rodar(b=b, humanos=h)[1]["EXEMPLO_B__B001"]
        self.assertEqual(f["estado"], estados.APROVADO_RASCUNHO)

    def test_a_prevalece_sobre_b_para_o_mesmo_provedor_e_id(self):
        b = produto_b(4, "A001")
        b["product"]["provider"] = "EXEMPLO_A"
        resumo, f = self.rodar(a={"a.json": a_com()}, b={"b.json": b})
        self.assertEqual(resumo["produtosEmAeB"], ["EXEMPLO_A/A001"])
        self.assertEqual(f["EXEMPLO_A__A001"]["origem"], "A")


class DecisoesHumanasTest(BaseV11):
    def test_aprovacao_humana_vinculada_a_versao(self):
        h = self.humanos(decisoes=[self.decisao(1, "A001", "aprovado_para_publicacao")])
        f = self.rodar(a={"a.json": a_com()}, humanos=h)[1]["EXEMPLO_A__A001"]
        self.assertEqual(f["estado"], estados.APROVADO_PUBLICACAO)
        self.assertTrue(any("exige autorização própria" in a for a in f["avisos"]))

    def test_sem_decisao_nada_e_aprovado_e_autor_automatico_e_recusado(self):
        d = self.decisao(1, "A001")
        d["autor"] = "bot automatico"
        f = self.rodar(a={"a.json": a_com()}, humanos=self.humanos(decisoes=[d]))
        self.assertEqual(f[1]["EXEMPLO_A__A001"]["estado"], estados.PENDENTE_REVISAO)
        self.assertTrue(any("ignorada" in a for a in f[0]["avisos"]))

    def test_aprovacao_nao_vale_se_estado_automatico_nao_permite(self):
        h = self.humanos(decisoes=[self.decisao(1, "A001")], permissoes=[])
        f = self.rodar(a={"a.json": a_com()}, humanos=h)[1]["EXEMPLO_A__A001"]
        self.assertEqual(f["estado"], estados.INCOMPLETO)

    def test_rejeicao_humana_vale(self):
        h = self.humanos(decisoes=[self.decisao(1, "A001", "rejeitado")])
        self.assertEqual(self.rodar(a={"a.json": a_com()}, humanos=h)[1]["EXEMPLO_A__A001"]["estado"], estados.REJEITADO)

    def test_mudanca_de_preco_invalida_aprovacao_de_a(self):
        a = {"a1.json": a_com(1), "a2.json": a_com(2, exportedAt="2026-11-17T14:00:00Z", price__amountCents=9990)}
        h = self.humanos(decisoes=[self.decisao(1, "A001")])
        f = self.rodar(a=a, humanos=h)[1]["EXEMPLO_A__A001"]
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)
        self.assertTrue(f["aprovacaoInvalidadaPorPreco"])

    def test_mudanca_de_identidade_invalida_aprovacao_em_a_e_em_b(self):
        for letra, prod, n, prov in (("a", produto_a, 1, "EXEMPLO_A"), ("b", produto_b, 4, "EXEMPLO_B")):
            self.setUp()
            v1 = prod(n, "X1") if letra == "b" else a_com(n, "A001")
            v2 = prod(n + 1, "X1", exportedAt="2026-11-17T14:00:00Z", product__title="Outro Título Fictício") if letra == "b" \
                else a_com(n + 1, "A001", exportedAt="2026-11-17T14:00:00Z", product__title="Outro Título Fictício")
            pid = "X1" if letra == "b" else "A001"
            h = self.humanos(decisoes=[self.decisao(n, pid, provider=prov)])
            kw = {"b": {"b1.json": v1, "b2.json": v2}} if letra == "b" else {"a": {"a1.json": v1, "a2.json": v2}}
            f = self.rodar(humanos=h, **kw)[1][f"{prov}__{pid}"]
            self.assertTrue(f["aprovacaoInvalidadaPorIdentidade"], letra)
            self.assertNotIn(f["estado"], (estados.APROVADO_RASCUNHO, estados.APROVADO_PUBLICACAO), letra)
            self.assertEqual(f["mudancaDeIdentidade"]["campos"], ["title"])

    def test_mudanca_de_loja_e_url_oficial_tambem_sao_identidade(self):
        for campo, valor in (("product__store", "Outra Loja"), ("product__officialUrl", "https://www.outra.example/p/1")):
            self.setUp()
            a = {"a1.json": a_com(1), "a2.json": a_com(2, exportedAt="2026-11-17T14:00:00Z", **{campo: valor})}
            h = self.humanos(decisoes=[self.decisao(1, "A001")])
            self.assertTrue(self.rodar(a=a, humanos=h)[1]["EXEMPLO_A__A001"]["aprovacaoInvalidadaPorIdentidade"], campo)

    def test_decisao_de_versao_desconhecida_e_ignorada(self):
        h = self.humanos(decisoes=[self.decisao(77, "A001")])
        f = self.rodar(a={"a.json": a_com()}, humanos=h)[1]["EXEMPLO_A__A001"]
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)


class FatosTest(BaseV11):
    def fato(self, dias, texto="Característica fictícia"):
        return {"text": texto, "sourceRef": "Página oficial fictícia", "verifiedAt": (AGORA - timedelta(days=dias)).strftime(FMT)}

    def test_fatos_frescos_e_antigos(self):
        p = a_com(verifiedFacts=[self.fato(30, "no limite"), self.fato(31, "vencido")])
        f = self.rodar(a={"a.json": p})[1]["EXEMPLO_A__A001"]
        self.assertEqual([x["text"] for x in f["fatosParaUso"]], ["no limite"])
        self.assertEqual([x["text"] for x in f["fatosEmRevisao"]], ["vencido"])
        self.assertFalse(f["regraDeFatosDormente"])

    def test_regra_dormente_sem_fatos(self):
        f = self.rodar(a={"a.json": a_com()})[1]["EXEMPLO_A__A001"]
        self.assertEqual((f["fatosParaUso"], f["fatosEmRevisao"], f["regraDeFatosDormente"]), ([], [], True))

    def test_indicio_de_alteracao_coloca_fatos_em_revisao_antes_dos_30_dias(self):
        a = {"a1.json": a_com(1, verifiedFacts=[self.fato(1)]),
             "a2.json": a_com(2, exportedAt="2026-11-17T14:00:00Z", verifiedFacts=[self.fato(1), self.fato(2, "novo")])}
        f = self.rodar(a=a)[1]["EXEMPLO_A__A001"]
        self.assertEqual((f["fatosParaUso"], len(f["fatosEmRevisao"])), ([], 2))
        self.assertIn("conjunto", f["fatosEmRevisao"][0]["motivoRevisao"])

    def test_mudanca_de_preco_nao_e_indicio_de_alteracao_de_fatos(self):
        a = {"a1.json": a_com(1, verifiedFacts=[self.fato(1)]),
             "a2.json": a_com(2, exportedAt="2026-11-17T14:00:00Z", price__amountCents=100, verifiedFacts=[self.fato(1)])}
        f = self.rodar(a=a)[1]["EXEMPLO_A__A001"]
        self.assertEqual((len(f["fatosParaUso"]), f["fatosEmRevisao"]), (1, []))

    def test_fato_com_data_futura_e_rejeitado_na_validacao(self):
        resumo, f = self.rodar(a={"a.json": a_com(verifiedFacts=[self.fato(-1)])})
        self.assertEqual((resumo["fichas"], resumo["rejeitados"]), (0, 1))


if __name__ == "__main__":
    unittest.main()
