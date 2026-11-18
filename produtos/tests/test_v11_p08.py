"""P-08: invalidação seletiva de aprovações por impressão digital material (contrato §17.4, DT-20)."""
import json
import unittest
from datetime import timedelta

from produtos import estados
from produtos import impressao_v11 as imp
from produtos.conflitos_v11 import CODIGOS
from produtos.decisoes import carregar
from produtos.esquema import validar_produto
from produtos.prepublicacao import BLOQUEAR, LIBERAR, avaliar_portao
from produtos.registro import Versao
from produtos.tempo import parse_data
from produtos.tests.base_v11 import AGORA, BaseV11, a_com, b_de, instantaneo, produto_a, produto_b, uid

CHAVE = "EXEMPLO_A__A001"
RAS, PUB = estados.APROVADO_RASCUNHO, estados.APROVADO_PUBLICACAO
FATO = {"text": "Característica fictícia", "sourceRef": "Página fictícia", "verifiedAt": "2026-11-16T12:00:00Z"}


def reexporta(n=2, **over):
    """Nova exportação SEM mudança material de A001: muda só exportId, exportedAt, verifiedAt, validUntil, checkedAt, publishedAt."""
    base = dict(exportedAt="2026-11-17T14:50:00Z", photo__checkedAt="2026-11-17T14:40:00Z")
    base.update(over)
    return a_com(n, verificado_ha=timedelta(minutes=30), valido_ate=timedelta(hours=5), **base)


def versao(obj, n=1):
    return Versao(f"v{n}.json", "0" * 64, validar_produto(obj, AGORA).dados, parse_data(obj["exportedAt"]))


class P08Base(BaseV11):
    def dec(self, n, tipo=RAS, pid="A001", provider="EXEMPLO_A", data="2026-11-17T14:30:00Z"):
        return {"provider": provider, "productId": pid, "exportId": uid(n), "decisao": tipo, "autor": "Maria Revisora",
                "data": data, "motivo": "teste"}

    def ficha(self, a1, a2, tipo, **kw):
        _, f = self.rodar(a={"a1.json": a1, "a2.json": a2}, humanos=self.humanos(decisoes=[self.dec(1, tipo)]), **kw)
        return f[CHAVE]

    def invalida(self, f, codigo):
        self.assertEqual(f["decisoesInaplicaveis"][0]["codigo"], codigo, f["decisoesInaplicaveis"])
        self.assertNotIn(f["estado"], (RAS, PUB))
        return f["decisoesInaplicaveis"][0]


class ReexportacaoSemMudancaTest(P08Base):
    def test_nova_exportacao_sem_mudanca_material_mantem_a_aprovacao(self):
        for tipo in (RAS, PUB):
            self.setUp()
            f = self.ficha(a_com(1), reexporta(2), tipo)
            self.assertEqual(f["estado"], tipo, tipo)
            self.assertEqual((f["decisoesInaplicaveis"], f["invalidacoesMateriais"]), ([], []))
            im = f["impressaoMaterialDecisao"]
            self.assertEqual(im["impressaoRevisada"], im["impressaoAtual"])
            self.assertEqual((im["versaoRevisada"], im["versaoVigente"]), (uid(1), uid(2)))
            self.assertEqual(f["versao"]["exportId"], uid(2))                          # a ficha já está na versão nova

    def test_reexportacao_posterior_a_decisao_tambem_mantem(self):
        f = self.ficha(a_com(1), reexporta(2, exportedAt="2026-11-17T14:59:00Z"), RAS)
        self.assertEqual(f["estado"], RAS)

    def test_reexportacao_b_sem_mudanca_mantem_rascunho(self):
        b1, b2 = produto_b(4, "B001"), produto_b(5, "B001", exportedAt="2026-11-17T14:50:00Z")
        d = self.dec(4, RAS, "B001", "EXEMPLO_B")
        _, f = self.rodar(b={"b1.json": b1, "b2.json": b2}, humanos=self.humanos(decisoes=[d]))
        self.assertEqual(f["EXEMPLO_B__B001"]["estado"], RAS)

    def test_metadados_nao_entram_na_impressao(self):
        v1, v2 = versao(a_com(1)), versao(reexporta(2), 2)
        for tipo in (RAS, PUB):
            self.assertEqual(imp.impressao(v1, tipo), imp.impressao(v2, tipo))
        self.assertEqual(imp.diferencas(v1, v2, PUB), [])


class CamposMateriaisTest(P08Base):
    def _campo(self, tipo, codigo, **mudanca):
        self.setUp()
        f = self.ficha(a_com(1), reexporta(2, **mudanca), tipo)
        return self.invalida(f, codigo), f

    def test_identidade_invalida_rascunho_e_publicacao(self):
        for tipo in (RAS, PUB):
            for campo, valor in (("title", "Outro Título Fictício"), ("store", "Outra Loja"),
                                 ("officialUrl", "https://www.outra.example/p/9")):
                ent, f = self._campo(tipo, "identidade_mudou", **{f"product__{campo}": valor})
                self.assertEqual(ent["campos"], [campo])
                self.assertTrue(f["aprovacaoInvalidadaPorIdentidade"])

    def test_fonte_mudou_em_b(self):
        b1, b2 = produto_b(4, "B001"), produto_b(5, "B001", exportedAt="2026-11-17T14:50:00Z", source__kind="api_candidato")
        d = self.dec(4, RAS, "B001", "EXEMPLO_B")
        _, fs = self.rodar(b={"b1.json": b1, "b2.json": b2}, humanos=self.humanos(decisoes=[d]))
        self.assertEqual(self.invalida(fs["EXEMPLO_B__B001"], "fonte_mudou")["campos"], ["fonte"])

    def test_fatos_mudaram_invalida_ambos_os_tipos(self):
        for tipo in (RAS, PUB):
            ent, _ = self._campo(tipo, "fatos_mudaram", verifiedFacts=[FATO])
            self.assertEqual(ent["campos"], ["fatos"])

    def test_fonte_de_comprovacao_mudou_com_o_mesmo_fato(self):
        a1 = a_com(1, verifiedFacts=[FATO])
        a2 = reexporta(2, verifiedFacts=[{**FATO, "sourceRef": "Outra página fictícia"}])
        for tipo in (RAS, PUB):
            self.setUp()
            f = self.ficha(a1, a2, tipo)
            ent = self.invalida(f, "fonte_comprovacao_mudou")
            self.assertEqual(ent["codigos"], ["fonte_comprovacao_mudou"])              # só a fonte; o texto do fato não mudou

    def test_so_a_data_de_verificacao_do_fato_mudar_nao_invalida(self):
        a2 = reexporta(2, verifiedFacts=[{**FATO, "verifiedAt": "2026-11-17T10:00:00Z"}])
        f = self.ficha(a_com(1, verifiedFacts=[FATO]), a2, PUB)
        self.assertEqual(f["estado"], PUB)

    def test_preco_so_invalida_publicacao_nunca_o_rascunho(self):
        for mud in (dict(price__amountCents=9990), dict(price__originalAmountCents=20000)):
            self.setUp()
            f = self.ficha(a_com(1), reexporta(2, **mud), PUB)
            self.invalida(f, "preco_mudou")
            self.assertTrue(f["aprovacaoInvalidadaPorPreco"])
            self.setUp()
            self.assertEqual(self.ficha(a_com(1), reexporta(2, **mud), RAS)["estado"], RAS)     # editorial != validade comercial

    def test_disponibilidade_so_invalida_publicacao(self):
        ent, _ = self._campo(PUB, "disponibilidade_mudou", availability="unknown")
        self.assertEqual(ent["campos"], ["disponibilidade"])
        self.setUp()
        self.assertEqual(self.ficha(a_com(1), reexporta(2, availability="unknown"), RAS)["estado"], RAS)

    def test_varias_mudancas_listam_todos_os_codigos_na_ordem_fixa(self):
        a2 = reexporta(2, product__title="Outro", price__amountCents=1, availability="unknown", verifiedFacts=[FATO])
        ent = self.invalida(self.ficha(a_com(1), a2, PUB), "identidade_mudou")
        self.assertEqual(ent["codigos"], ["identidade_mudou", "fatos_mudaram", "preco_mudou", "disponibilidade_mudou"])

    def test_codigos_novos_estao_no_vocabulario(self):
        for c in ("fatos_mudaram", "fonte_comprovacao_mudou", "disponibilidade_mudou", "fonte_mudou", "divergencia_ab_alterada",
                  "identidade_mudou", "preco_mudou"):
            self.assertIn(c, CODIGOS)
            self.assertIn(c, imp.CODIGOS_IMPRESSAO)

    def test_aprovacao_invalidada_volta_ao_estado_automatico_nunca_a_aprovado(self):
        f = self.ficha(a_com(1), reexporta(2, product__title="Outro"), RAS)
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)
        self.assertIsNone(f["decisaoHumana"])
        self.assertTrue(any("INAPLICÁVEL" in a for a in f["avisos"]))


class DivergenciaABTest(P08Base):
    def rodar_ab(self, a_vers, b_vers, decisao):
        a = {f"a{i}.json": v for i, v in enumerate(a_vers, 1)}
        b = {f"b{i}.json": v for i, v in enumerate(b_vers, 1)}
        _, f = self.rodar(a=a, b=b, humanos=self.humanos(decisoes=[decisao]))
        return f[CHAVE]

    def test_divergencia_inalterada_mantem_mesmo_com_reexportacoes(self):
        b1 = b_de(4, product__title="Título Divergente", exportedAt="2026-11-17T13:30:00Z")
        b2 = b_de(5, product__title="Título Divergente", exportedAt="2026-11-17T14:50:00Z")
        d = self.dec(1, RAS, data="2026-11-17T14:00:00Z")                            # revisada já com a divergência
        f = self.rodar_ab([a_com(1), reexporta(2)], [b1, b2], d)
        self.assertEqual((f["estado"], f["decisoesInaplicaveis"]), (RAS, []))
        self.assertEqual(f["impressaoMaterialDecisao"]["divergenciasNaRevisao"], ["title"])

    def test_mesmo_campo_divergente_com_valor_materialmente_diferente_invalida(self):
        # revisão 5.14-A (comportamento alterado): antes só o NOME do campo contava; agora o par de valores revisado também
        b1 = b_de(4, product__title="Título Divergente", exportedAt="2026-11-17T13:30:00Z")
        b2 = b_de(5, product__title="Outro Título Divergente", exportedAt="2026-11-17T14:50:00Z")
        f = self.rodar_ab([a_com(1)], [b1, b2], self.dec(1, RAS, data="2026-11-17T14:00:00Z"))
        ent = self.invalida(f, "divergencia_ab_alterada")
        self.assertEqual(ent["divergenciasAlteradas"], {"title": "valor_alterado"})

    def test_divergencia_que_diminui_mantem(self):
        b1 = b_de(4, product__title="Título Divergente", product__store="Outra Loja", exportedAt="2026-11-17T13:30:00Z")
        b2 = b_de(5, product__title="Título Divergente", exportedAt="2026-11-17T14:50:00Z")      # só o título diverge agora
        f = self.rodar_ab([a_com(1)], [b1, b2], self.dec(1, RAS, data="2026-11-17T14:00:00Z"))
        self.assertEqual((f["estado"], f["impressaoMaterialDecisao"]["divergenciasAtuais"]), (RAS, ["title"]))

    def test_campo_novo_divergente_invalida(self):
        b1 = b_de(4, product__title="Título Divergente", exportedAt="2026-11-17T13:30:00Z")
        b2 = b_de(5, product__title="Título Divergente", product__store="Outra Loja", exportedAt="2026-11-17T14:50:00Z")
        f = self.rodar_ab([a_com(1)], [b1, b2], self.dec(1, RAS, data="2026-11-17T14:00:00Z"))
        ent = self.invalida(f, "divergencia_ab_alterada")
        self.assertEqual(ent["campos"], ["store"])
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)

    def test_b_que_aparece_depois_da_decisao_com_divergencia_invalida_e_sem_divergencia_mantem(self):
        d = self.dec(1, RAS, data="2026-11-17T14:00:00Z")
        div = b_de(4, product__title="Título Divergente", exportedAt="2026-11-17T14:30:00Z")
        self.invalida(self.rodar_ab([a_com(1)], [div], d), "divergencia_ab_alterada")
        self.setUp()
        igual = b_de(4, exportedAt="2026-11-17T14:30:00Z")
        self.assertEqual(self.rodar_ab([a_com(1)], [igual], d)["estado"], RAS)

    def test_aprovacao_com_divergencia_na_revisao_vale_para_b_tambem(self):
        a = a_expirada_antiga = a_com(1)
        b = b_de(4, product__title="Título Divergente", exportedAt="2026-11-17T13:30:00Z")
        f = self.rodar_ab([a], [b], {**self.dec(1, RAS, data="2026-11-17T14:00:00Z")})
        self.assertEqual(f["estado"], RAS)

    def test_fatos_divergentes_novos_invalidam(self):
        b = b_de(4, exportedAt="2026-11-17T13:30:00Z")
        a2 = reexporta(2, verifiedFacts=[FATO])                                     # A ganha fato que B não tem -> mudou fatos E divergência
        f = self.rodar_ab([a_com(1), a2], [b], self.dec(1, RAS, data="2026-11-17T14:00:00Z"))
        ent = self.invalida(f, "fatos_mudaram")
        self.assertEqual(ent["codigos"], ["fatos_mudaram", "divergencia_ab_alterada"])


class DecisoesAntigasTest(P08Base):
    def test_decisao_sem_versao_revisada_nas_fontes_e_tratada_de_forma_explicita_e_conservadora(self):
        _, f = self.rodar(a={"a.json": a_com(2)}, humanos=self.humanos(decisoes=[self.dec(99)]))
        f = f[CHAVE]
        self.assertEqual(f["estado"], estados.PENDENTE_REVISAO)
        self.assertEqual([d["codigo"] for d in f["decisoesInaplicaveis"]], ["versao_desconhecida"])
        self.assertIn("impressão digital", f["decisoesInaplicaveis"][0]["motivo"])

    def test_decisao_antiga_sem_impressao_continua_valida_quando_a_versao_revisada_existe(self):
        # decisoes.json não guarda impressão (formato inalterado): ela é recalculada da versão revisada
        f = self.ficha(a_com(1), reexporta(2), RAS)
        self.assertEqual(f["estado"], RAS)

    def test_campo_impressao_no_arquivo_de_decisoes_nao_e_aceito_e_fica_visivel(self):
        d = {**self.dec(1), "impressao": "abc"}
        r, _ = self.rodar(a={"a.json": a_com(1)}, humanos=self.humanos(decisoes=[d]))
        self.assertTrue(any("decisão #1 ignorada" in a for a in r["avisos"]))

    def test_formato_do_arquivo_de_decisoes_nao_mudou(self):
        p = self.tmp / "d.json"
        p.write_text(json.dumps({"decisoesVersion": "1.0", "decisoes": [self.dec(1)]}))
        self.assertEqual(len(carregar(p).por_produto[("EXEMPLO_A", "A001")]), 1)

    def test_decisao_anterior_a_exportacao_revisada_continua_inaplicavel(self):
        _, f = self.rodar(a={"a.json": a_com(1)}, humanos=self.humanos(decisoes=[self.dec(1, data="2026-11-17T09:00:00Z")]))
        self.assertEqual(f[CHAVE]["decisoesInaplicaveis"][0]["codigo"], "anterior_a_exportacao")


class DeterminismoTest(BaseV11):
    def test_independente_da_ordem_de_campos_e_listas_e_da_caixa_do_texto(self):
        fatos = [{**FATO, "text": "Fato Um"}, {**FATO, "text": "Fato Dois", "sourceRef": "Fonte B"}]
        a = a_com(1, verifiedFacts=fatos)
        b = json.loads(json.dumps(a))
        b["verifiedFacts"] = list(reversed(b["verifiedFacts"]))
        b["verifiedFacts"][0]["text"] = "  fato   DOIS "
        b["product"] = dict(reversed(list(b["product"].items())))
        b["product"]["title"] = "  PRODUTO   Fictício A001 "
        b["exportId"] = uid(2)
        b["exportedAt"] = "2026-11-17T14:50:00Z"
        for tipo in (RAS, PUB):
            self.assertEqual(imp.impressao(versao(a), tipo), imp.impressao(versao(b, 2), tipo), tipo)

    def test_muda_quando_algo_material_muda_e_e_especifica_por_tipo(self):
        base = versao(a_com(1))
        preco = versao(a_com(2, price__amountCents=1), 2)
        self.assertEqual(imp.impressao(base, RAS), imp.impressao(preco, RAS))          # rascunho ignora preço
        self.assertNotEqual(imp.impressao(base, PUB), imp.impressao(preco, PUB))
        self.assertNotEqual(imp.impressao(base, RAS), imp.impressao(base, PUB))        # tipos distintos nunca colidem
        titulo = versao(a_com(3, product__title="Outro"), 3)
        self.assertNotEqual(imp.impressao(base, RAS), imp.impressao(titulo, RAS))

    def test_impressao_e_sha256_estavel(self):
        h = imp.impressao(versao(a_com(1)), PUB)
        self.assertRegex(h, r"^[0-9a-f]{64}$")
        self.assertEqual(h, imp.impressao(versao(a_com(1)), PUB))

    def test_rejeicao_nao_tem_impressao(self):
        with self.assertRaises(ValueError):
            imp.impressao(versao(a_com(1)), estados.REJEITADO)

    def test_componentes_por_tipo(self):
        self.assertEqual(imp.componentes_do_tipo(RAS), ("identidade", "fonte", "fatos", "fonte_comprovacao"))
        self.assertEqual(imp.componentes_do_tipo(PUB)[-2:], ("preco", "disponibilidade"))

    def test_divergencias_utilitarios(self):
        self.assertEqual(imp.divergencia_alterada(["title"], ["title"]), [])
        self.assertEqual(imp.divergencia_alterada(["title", "store"], ["title"]), [])
        self.assertEqual(imp.divergencia_alterada(["title"], ["title", "officialUrl"]), ["officialUrl"])
        self.assertEqual(imp.divergencia_alterada([], ["verifiedFacts"]), ["verifiedFacts"])


class PreservacaoTest(P08Base):
    def test_arquivos_de_decisoes_e_exportacoes_nao_sao_alterados(self):
        h = self.humanos(decisoes=[self.dec(1)])
        antes = None
        self.rodar(a={"a1.json": a_com(1), "a2.json": reexporta(2)}, humanos=h)
        antes = instantaneo(self.tmp)
        antes = {k: v for k, v in antes.items() if not k.startswith("saida")}
        from produtos.pipeline_v11 import processar_v11
        processar_v11(self.exp, self.saida, AGORA, **h)
        depois = {k: v for k, v in instantaneo(self.tmp).items() if not k.startswith("saida")}
        self.assertEqual(antes, depois)

    def test_historico_preserva_as_duas_versoes(self):
        self.ficha(a_com(1), reexporta(2), RAS)
        hist = json.loads((self.saida / "historico.json").read_text())
        self.assertEqual({v["exportId"] for v in hist[0]["versoes"]}, {uid(1), uid(2)})

    def test_decisoes_inaplicaveis_antigas_continuam_com_os_mesmos_codigos(self):
        decs = [self.dec(1, RAS, data="2026-11-17T14:00:00Z"), self.dec(1, "rejeitado", data="2026-11-17T14:20:00Z")]
        _, f = self.rodar(a={"a.json": a_com(1)}, humanos=self.humanos(decisoes=decs))
        self.assertEqual([d["codigo"] for d in f[CHAVE]["decisoesInaplicaveis"]], ["superada_por_decisao_mais_recente"])

    def test_resumo_lista_a_invalidacao_material(self):
        r, _ = self.rodar(a={"a1.json": a_com(1), "a2.json": reexporta(2, product__title="Outro")},
                          humanos=self.humanos(decisoes=[self.dec(1)]))
        self.assertEqual(r["decisoesInaplicaveis"][0]["codigo"], "identidade_mudou")


class AprovacaoNaoEValidadeComercialTest(P08Base):
    def test_aprovacao_de_publicacao_nao_estende_a_janela_de_24h(self):
        a = a_com(1)
        h = self.humanos(decisoes=[self.dec(1, PUB)])
        _, f = self.rodar(a={"a.json": a}, humanos=h)
        self.assertEqual(f[CHAVE]["estado"], PUB)
        _, f2 = self.rodar(a={"a.json": a}, humanos=h, agora=AGORA + timedelta(hours=6))      # janela vencida
        self.assertEqual(f2[CHAVE]["estado"], estados.EXPIRADO)
        self.assertEqual(f2[CHAVE]["decisoesInaplicaveis"][0]["codigo"], "estado_nao_permite")

    def test_portao_continua_bloqueando_fora_da_janela_mesmo_com_aprovacao_e_sem_mudanca_material(self):
        _, f = self.rodar(a={"a1.json": a_com(1), "a2.json": reexporta(2)}, humanos=self.humanos(decisoes=[self.dec(1, PUB)]))
        ficha = f[CHAVE]
        self.assertEqual(ficha["estado"], PUB)
        alegacao = [{"id": "p", "tipo": "preco", "funcao": "essencial", "tem_variante_sem": False}]
        ok = avaliar_portao(ficha, preco_aprovado_centavos=ficha["preco"]["amountCents"], t_publicacao=AGORA, alegacoes=alegacao)
        fora = avaliar_portao(ficha, preco_aprovado_centavos=ficha["preco"]["amountCents"],
                              t_publicacao=AGORA + timedelta(hours=8), alegacoes=alegacao)
        self.assertEqual((ok["acao"], fora["acao"]), (LIBERAR, BLOQUEAR))


if __name__ == "__main__":
    unittest.main()
