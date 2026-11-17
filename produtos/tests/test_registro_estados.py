"""Testes 5, 6, 7 (foto) e 8: deduplicação, expiração, foto utilizável e estados/decisões humanas."""
import json
import unittest
from datetime import timedelta

from produtos import avaliacao, decisoes, estados, fotos, registro
from produtos.avaliacao import Configuracao
from produtos.leitor import Lido
from produtos.tests.base import AGORA, DEL, Base, escrever, mod, produto_a, produto_b, t, uid
from produtos.esquema import validar_produto


def lido(d, nome="x.json"):
    r = validar_produto(d, AGORA)
    assert r.ok, r.erros
    return Lido(nome, "0" * 64, r.dados)


def avaliar(ds, decs=(), agora=AGORA, cfg=None, arquivo_dias=30):
    reg = registro.montar([lido(d, f"{i:02d}.json") for i, d in enumerate(ds)], agora, arquivo_dias=arquivo_dias)
    chave = next(iter(reg.produtos))
    return reg, avaliacao.avaliar(reg.produtos[chave], list(decs), agora, cfg or Configuracao())


def decisao(export_id, quem="Revisor Exemplo", tipo=estados.APROVADO_RASCUNHO, data="2026-11-17T14:00:00Z",
            pid="A001", prov="EXEMPLO_A", motivo="conferido (fictício)"):
    return {"provider": prov, "productId": pid, "exportId": export_id, "decisao": tipo, "autor": quem,
            "data": data, "motivo": motivo}


class Decs(Base):
    def decs(self, *itens):
        escrever(self.tmp, "decisoes.json", {"decisoesVersion": "1.0", "decisoes": list(itens)})
        return decisoes.carregar(self.tmp / "decisoes.json")


class DeduplicacaoTest(Base):
    def test_mantem_o_mais_recente_e_preserva_historico(self):
        v1 = produto_a(1, "A001", exportedAt="2026-11-17T10:00:00Z")
        v2 = produto_a(2, "A001", exportedAt="2026-11-17T14:00:00Z", price__amountCents=11990)
        v3 = produto_a(3, "A001", exportedAt="2026-11-17T12:00:00Z")
        reg, _ = avaliar([v1, v2, v3])
        prod = reg.produtos[("EXEMPLO_A", "A001")]
        self.assertEqual(prod.vigente.export_id, uid(2))
        self.assertEqual([v.export_id for v in prod.versoes], [uid(2), uid(3), uid(1)])
        hist = reg.historico()[0]["versoes"]
        self.assertEqual([h["situacao"] for h in hist], ["vigente", "substituida", "substituida"])
        self.assertEqual([h["amountCents"] for h in hist], [11990, 12990, 12990])

    def test_chave_e_provider_mais_id(self):
        a = produto_a(1, "A001")
        b = produto_a(2, "A001", product__provider="EXEMPLO_C")
        reg = registro.montar([lido(a), lido(b)], AGORA)
        self.assertEqual(len(reg.produtos), 2)

    def test_empate_de_exported_at_e_deterministico(self):
        v1 = produto_a(1, "A001")
        v2 = produto_a(2, "A001")
        for ordem in ([v1, v2], [v2, v1]):
            reg = registro.montar([lido(d) for d in ordem], AGORA)
            self.assertEqual(reg.produtos[("EXEMPLO_A", "A001")].vigente.export_id, uid(2))

    def test_mesmo_export_id_em_dois_arquivos_e_registrado(self):
        a, b = lido(produto_a(1)), lido(produto_a(1))
        b.arquivo = "copia.json"
        reg = registro.montar([a, b], AGORA)
        self.assertEqual(len(reg.duplicatas_export_id), 1)
        self.assertEqual(reg.duplicatas_export_id[0]["descartado"], "copia.json")

    def test_arquivamento_por_idade_e_parametro(self):
        velho = produto_a(1, "A001", exportedAt="2026-10-01T10:00:00Z", price__verifiedAt="2026-10-01T09:00:00Z",
                          price__validUntil="2026-10-01T20:00:00Z", publication__publishedAt="2026-10-01T10:00:00Z")
        reg = registro.montar([lido(velho)], AGORA, arquivo_dias=30)
        self.assertEqual(reg.produtos, {})
        self.assertEqual(reg.arquivados[0]["productId"], "A001")
        self.assertEqual(reg.historico()[0]["versoes"][0]["situacao"], "arquivada")
        reg = registro.montar([lido(velho)], AGORA, arquivo_dias=60)           # parâmetro configurável
        self.assertEqual(len(reg.produtos), 1)
        reg = registro.montar([lido(velho)], AGORA, arquivo_dias=None)         # desativado
        self.assertEqual(len(reg.produtos), 1)

    def test_versao_antiga_arquivada_nao_vira_vigente(self):
        antigo = produto_a(1, "A001", exportedAt="2026-10-01T10:00:00Z", price__verifiedAt="2026-10-01T09:00:00Z",
                           price__validUntil="2026-10-01T20:00:00Z", publication__publishedAt="2026-10-01T10:00:00Z")
        novo = produto_a(2, "A001")
        reg = registro.montar([lido(antigo), lido(novo)], AGORA)
        prod = reg.produtos[("EXEMPLO_A", "A001")]
        self.assertEqual(prod.vigente.export_id, uid(2))
        self.assertEqual({h["situacao"] for h in reg.historico()[0]["versoes"]}, {"vigente", "arquivada"})

    def test_mudanca_de_preco_e_registrada_na_avaliacao(self):
        v1 = produto_a(1, "A001", exportedAt="2026-11-17T10:00:00Z")
        v2 = produto_a(2, "A001", exportedAt="2026-11-17T14:00:00Z", price__amountCents=11990)
        _, av = avaliar([v1, v2])
        self.assertEqual(av.mudanca_de_preco, {"de": 12990, "para": 11990, "versaoAnterior": uid(1)})


class ExpiracaoTest(Base):
    """Teste 6: relógio simulado — dentro, no limite e fora; revalidação configurável."""

    def estado(self, agora, cfg=None, **over):
        d = produto_a(**over)
        return avaliar([d], agora=agora, cfg=cfg)[1]

    def test_dentro_no_limite_e_fora_de_valid_until(self):
        valid = t("2026-11-17T19:00:00Z")
        cfg = Configuracao(revalidacao_horas=None)                    # isola a regra de validUntil
        self.assertEqual(self.estado(valid - timedelta(seconds=1), cfg).estado, estados.PENDENTE_REVISAO)
        self.assertEqual(self.estado(valid, cfg).estado, estados.PENDENTE_REVISAO)           # limite inclusivo
        av = self.estado(valid + timedelta(seconds=1), cfg)
        self.assertEqual(av.estado, estados.EXPIRADO)
        self.assertIn("validUntil", av.motivo_automatico)

    def test_revalidacao_de_24h_padrao_no_limite_e_fora(self):
        # validUntil longe, para que só a janela de 24 h decida
        kw = dict(price__validUntil="2026-11-30T00:00:00Z")
        ver = t("2026-11-17T13:00:00Z")
        self.assertEqual(self.estado(ver + timedelta(hours=24), **kw).estado, estados.PENDENTE_REVISAO)
        av = self.estado(ver + timedelta(hours=24, seconds=1), **kw)
        self.assertEqual(av.estado, estados.EXPIRADO)
        self.assertIn("revalidação", av.motivo_automatico)

    def test_revalidacao_e_parametro_configuravel(self):
        kw = dict(price__validUntil="2026-11-30T00:00:00Z")
        ver = t("2026-11-17T13:00:00Z")
        agora = ver + timedelta(hours=30)
        self.assertEqual(self.estado(agora, Configuracao(revalidacao_horas=24), **kw).estado, estados.EXPIRADO)
        self.assertEqual(self.estado(agora, Configuracao(revalidacao_horas=48), **kw).estado, estados.PENDENTE_REVISAO)
        self.assertEqual(self.estado(agora, Configuracao(revalidacao_horas=None), **kw).estado, estados.PENDENTE_REVISAO)
        self.assertEqual(self.estado(ver + timedelta(hours=2), Configuracao(revalidacao_horas=1), **kw).estado, estados.EXPIRADO)

    def test_padrao_de_revalidacao_e_24h(self):
        self.assertEqual(Configuracao().revalidacao_horas, 24.0)

    def test_b_e_sempre_sem_verificacao(self):
        for agora in (AGORA, AGORA + timedelta(days=1)):
            _, av = avaliar([produto_b()], agora=agora)
            self.assertEqual(av.estado, estados.EXPIRADO)
            self.assertIn("fonte B", av.motivo_automatico)
            self.assertTrue(av.pendencias)

    def test_indisponivel_invalida(self):
        _, av = avaliar([produto_a(availability="out_of_stock")])
        self.assertEqual(av.estado, estados.INVALIDADO)

    def test_expirado_vence_a_aprovacao_humana(self):
        d = produto_a()
        escrever(self.tmp, "d.json", {"decisoes": [decisao(uid(1))]})
        ds = decisoes.carregar(self.tmp / "d.json").por_produto[("EXEMPLO_A", "A001")]
        _, av = avaliar([d], ds, agora=t("2026-11-17T20:00:00Z"))
        self.assertEqual(av.estado, estados.EXPIRADO)
        self.assertIsNone(av.decisao_aplicada)
        self.assertEqual(av.decisoes_ignoradas[0]["decisao"], estados.APROVADO_RASCUNHO)


class FotoTest(Base):
    """Teste 7 (parte de foto)."""

    def test_so_confirmada_e_utilizavel(self):
        base = produto_a()["photo"]
        self.assertTrue(fotos.foto_utilizavel(base))
        for perm in ("pendente", "negada"):
            self.assertFalse(fotos.foto_utilizavel({**base, "usePermission": perm}))
        self.assertFalse(fotos.foto_utilizavel({**base, "url": None}))
        self.assertFalse(fotos.foto_utilizavel(None))

    def test_situacao_traz_aviso_de_sem_foto_autorizada(self):
        s = fotos.situacao_foto({"usePermission": "negada", "url": "https://x.lojaficticia.example/a.jpg"})
        self.assertFalse(s["utilizavel"])
        self.assertIn("sem foto autorizada", s["aviso"])
        self.assertIn("NEGADO", s["aviso"])
        self.assertIn("pendente", fotos.situacao_foto(None)["aviso"])
        self.assertIsNone(fotos.situacao_foto(produto_a()["photo"])["aviso"])

    def test_foto_pendente_ou_negada_deixa_a_ficha_incompleta(self):
        for perm in ("pendente", "negada"):
            d = produto_a(photo__usePermission=perm, photo__permissionRef=None, photo__checkedAt=None)
            _, av = avaliar([d])
            self.assertEqual(av.estado, estados.INCOMPLETO, perm)
            self.assertTrue(any("foto" in p for p in av.pendencias))

    def test_padrao_da_permissao_e_pendente(self):
        r = validar_produto(produto_b(), AGORA)
        self.assertEqual(r.dados["photo"]["usePermission"], "pendente")
        r = validar_produto(mod(produto_a(), photo__usePermission="pendente", photo__permissionRef=None,
                                photo__checkedAt=None), AGORA)
        self.assertTrue(r.ok)


class DecisoesTest(Decs):
    """Teste 8: aprovações só por decisão humana registrada."""

    def test_sem_decisao_nenhuma_ficha_e_aprovada(self):
        for d in (produto_a(), produto_b()):
            _, av = avaliar([d])
            self.assertNotIn(av.estado, estados.APROVACOES)
        self.assertEqual(avaliar([produto_a()])[1].estado, estados.PENDENTE_REVISAO)

    def test_decisao_humana_aprova_para_rascunho(self):
        ds = self.decs(decisao(uid(1))).por_produto[("EXEMPLO_A", "A001")]
        _, av = avaliar([produto_a()], ds)
        self.assertEqual(av.estado, estados.APROVADO_RASCUNHO)
        self.assertEqual(av.estado_automatico, estados.PENDENTE_REVISAO)
        self.assertEqual(av.decisao_aplicada.autor, "Revisor Exemplo")
        self.assertEqual(av.eventos[-1]["origem"], "humano")

    def test_aprovacao_para_publicacao_so_registra_autorizacao(self):
        ds = self.decs(decisao(uid(1), tipo=estados.APROVADO_PUBLICACAO)).por_produto[("EXEMPLO_A", "A001")]
        _, av = avaliar([produto_a()], ds)
        self.assertEqual(av.estado, estados.APROVADO_PUBLICACAO)

    def test_rejeicao_humana(self):
        ds = self.decs(decisao(uid(1), tipo=estados.REJEITADO)).por_produto[("EXEMPLO_A", "A001")]
        self.assertEqual(avaliar([produto_a()], ds)[1].estado, estados.REJEITADO)

    def test_b_nunca_e_aprovado(self):
        for tipo in (estados.APROVADO_RASCUNHO, estados.APROVADO_PUBLICACAO):
            ds = self.decs(decisao(uid(4), tipo=tipo, pid="B001", prov="EXEMPLO_B")).por_produto[("EXEMPLO_B", "B001")]
            _, av = avaliar([produto_b()], ds)
            self.assertEqual(av.estado, estados.EXPIRADO)
            self.assertEqual(len(av.decisoes_ignoradas), 1)

    def test_incompleto_e_invalidado_nao_aceitam_aprovacao(self):
        for d in (produto_a(photo__usePermission="pendente", photo__permissionRef=None, photo__checkedAt=None),
                  produto_a(availability="out_of_stock")):
            ds = self.decs(decisao(uid(1))).por_produto[("EXEMPLO_A", "A001")]
            _, av = avaliar([d], ds)
            self.assertNotIn(av.estado, estados.APROVACOES)
            self.assertEqual(len(av.decisoes_ignoradas), 1)

    def test_decisoes_invalidas_sao_ignoradas_e_relatadas(self):
        ruins = [
            decisao(uid(1), quem="Sistema"), decisao(uid(1), quem="bot de aprovação"), decisao(uid(1), quem="Claude"),
            decisao(uid(1), quem="x"), decisao(uid(1), tipo="expirado"), decisao(uid(1), tipo="recebido"),
            decisao("nao-uuid"), decisao(uid(1), data="ontem"), decisao(uid(1), motivo=" "),
            {**decisao(uid(1)), "extra": 1},
        ]
        d = self.decs(*ruins)
        self.assertEqual(d.por_produto, {})
        self.assertEqual(len(d.avisos), len(ruins))
        self.assertEqual(avaliar([produto_a()], [])[1].estado, estados.PENDENTE_REVISAO)

    def test_arquivo_de_decisoes_ausente_ou_corrompido_nao_aprova(self):
        self.assertEqual(decisoes.carregar(None).por_produto, {})
        d = decisoes.carregar(self.tmp / "nao_existe.json")
        self.assertEqual(d.por_produto, {})
        self.assertTrue(d.avisos)
        escrever(self.tmp, "ruim.json", "{ruim")
        self.assertTrue(decisoes.carregar(self.tmp / "ruim.json").avisos)
        escrever(self.tmp, "forma.json", {"outra": []})
        self.assertTrue(decisoes.carregar(self.tmp / "forma.json").avisos)

    def test_decisao_de_data_futura_ou_anterior_a_exportacao_e_ignorada(self):
        for data in ("2026-11-18T10:00:00Z", "2026-11-17T09:00:00Z"):
            ds = self.decs(decisao(uid(1), data=data)).por_produto[("EXEMPLO_A", "A001")]
            _, av = avaliar([produto_a()], ds)
            self.assertEqual(av.estado, estados.PENDENTE_REVISAO, data)
            self.assertEqual(len(av.decisoes_ignoradas), 1)

    def test_decisao_de_outra_versao_desconhecida_e_ignorada(self):
        ds = self.decs(decisao(uid(99))).por_produto[("EXEMPLO_A", "A001")]
        _, av = avaliar([produto_a()], ds)
        self.assertEqual(av.estado, estados.PENDENTE_REVISAO)

    def test_vale_a_decisao_mais_recente(self):
        ds = self.decs(decisao(uid(1), data="2026-11-17T14:00:00Z"),
                       decisao(uid(1), tipo=estados.REJEITADO, data="2026-11-17T14:30:00Z")).por_produto[("EXEMPLO_A", "A001")]
        self.assertEqual(avaliar([produto_a()], ds)[1].estado, estados.REJEITADO)

    def test_mudanca_de_preco_invalida_aprovacao_anterior(self):
        v1 = produto_a(1, "A001", exportedAt="2026-11-17T10:00:00Z", price__verifiedAt="2026-11-17T09:55:00Z")
        v2 = produto_a(2, "A001", exportedAt="2026-11-17T14:00:00Z", price__amountCents=11990)
        ds = self.decs(decisao(uid(1), data="2026-11-17T11:00:00Z")).por_produto[("EXEMPLO_A", "A001")]
        # com só a v1, a aprovação vale
        self.assertEqual(avaliar([v1], ds, agora=t("2026-11-17T12:00:00Z"))[1].estado, estados.APROVADO_RASCUNHO)
        # com a v2 (preço novo), volta para pendente_revisao
        _, av = avaliar([v1, v2], ds)
        self.assertEqual(av.estado, estados.PENDENTE_REVISAO)
        self.assertTrue(av.aprovacao_invalidada_por_preco)
        self.assertIsNone(av.decisao_aplicada)
        self.assertIn("preço mudou", av.decisoes_ignoradas[0]["ignoradaPorque"])

    def test_aprovacao_sobrevive_a_nova_versao_com_mesmo_preco(self):
        v1 = produto_a(1, "A001", exportedAt="2026-11-17T10:00:00Z", price__verifiedAt="2026-11-17T09:55:00Z")
        v2 = produto_a(2, "A001", exportedAt="2026-11-17T14:00:00Z")
        ds = self.decs(decisao(uid(1), data="2026-11-17T11:00:00Z")).por_produto[("EXEMPLO_A", "A001")]
        self.assertEqual(avaliar([v1, v2], ds)[1].estado, estados.APROVADO_RASCUNHO)

    def test_preco_que_volta_ao_valor_aprovado_nao_reativa_aprovacao(self):
        # v1 (12990, aprovada) -> v2 (11990) -> v3 (12990): houve mudança no meio, aprovação segue invalidada
        v1 = produto_a(1, "A001", exportedAt="2026-11-17T09:00:00Z", price__verifiedAt="2026-11-17T08:55:00Z")
        v2 = produto_a(2, "A001", exportedAt="2026-11-17T12:00:00Z", price__amountCents=11990)
        v3 = produto_a(3, "A001", exportedAt="2026-11-17T14:00:00Z")
        ds = self.decs(decisao(uid(1), data="2026-11-17T10:00:00Z")).por_produto[("EXEMPLO_A", "A001")]
        _, av = avaliar([v1, v2, v3], ds)
        self.assertEqual(av.estado, estados.PENDENTE_REVISAO)
        self.assertTrue(av.aprovacao_invalidada_por_preco)

    def test_codigo_nunca_grava_o_arquivo_de_decisoes(self):
        arq = escrever(self.tmp, "decisoes.json", {"decisoes": [decisao(uid(1))]})
        antes = (arq.read_bytes(), arq.stat().st_mtime_ns)
        decisoes.carregar(arq)
        escrever(self.troca, "a.json", produto_a())
        from produtos.pipeline import processar
        processar(self.troca, self.saida, AGORA, decisoes_arquivo=arq)
        self.assertEqual((arq.read_bytes(), arq.stat().st_mtime_ns), antes)
        # e o módulo só abre arquivos para leitura
        import inspect
        fonte = inspect.getsource(decisoes)
        for proibido in ("write_text", "write_bytes", "open(", ".unlink", "os.remove"):
            self.assertNotIn(proibido, fonte)

    def test_nenhuma_transicao_automatica_para_aprovado(self):
        for d in (produto_a(), produto_b(), produto_a(availability="out_of_stock"),
                  produto_a(photo__usePermission="negada", photo__permissionRef=None, photo__checkedAt=None)):
            _, av = avaliar([d])
            self.assertNotIn(av.estado_automatico, estados.APROVACOES)
            self.assertNotIn(av.estado, estados.APROVACOES)
            self.assertTrue(all(e["origem"] == "automatico" for e in av.eventos))


if __name__ == "__main__":
    unittest.main()
