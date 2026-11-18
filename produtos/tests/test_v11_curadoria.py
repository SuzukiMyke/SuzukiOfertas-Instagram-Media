"""Curadoria manual no contrato 1.1 (GOAL 5.14-B1, commit 1): fonte, preço nulo, URLs, alegações, fichas, P-08 e modo 1.0 intacto."""
import copy
import json
import unittest
from datetime import timedelta

from produtos import curadoria_regras_v11 as cur
from produtos import estados
from produtos import impressao_v11 as imp
from produtos.carrossel_fragmento_v11 import ficha_para_carrossel_v11
from produtos.esquema import (FONTE_CURADORIA, PROVIDER_CURADORIA, SISTEMA_AGENTE, SISTEMA_CURADORIA, validar_produto)
from produtos.leitor import ler_pasta
from produtos.leitor_v11 import ler_lote
from produtos.pipeline import processar
from produtos.registro import Versao
from produtos.tempo import parse_data
from produtos.tests.base import EXEMPLOS
from produtos.tests.base_v11 import AGORA, BaseV11, a_com, gravar_lote, produto_a, produto_b, uid

CHAVE = "CURADORIA__C001"
FATO = {"text": "Capacidade de 5 litros", "sourceRef": "https://fonte.fabricante.example/c001", "verifiedAt": "2026-11-16T12:00:00Z"}
NULO = {"amountCents": None, "currency": "BRL", "originalAmountCents": None, "verifiedAt": None, "validUntil": None,
        "verification": "desconhecida"}


def curadoria(n=11, pid="C001", **over):
    d = {
        "schemaVersion": "1.0.0", "exportId": uid(n), "exportedAt": "2026-11-17T13:05:00Z",
        "source": {"kind": FONTE_CURADORIA, "system": SISTEMA_CURADORIA},
        "product": {"id": pid, "provider": PROVIDER_CURADORIA, "store": "Loja Fictícia", "title": f"Produto Fictício {pid}",
                    "category": "Casa e Cozinha > Utensílios", "categoryOrigin": "fonte",
                    "officialUrl": f"https://www.lojaficticia.example/produto/{pid.lower()}", "affiliateUrl": None},
        "price": dict(NULO), "availability": "unknown", "verifiedFacts": [dict(FATO)],
        "publication": {"state": "nao_publicada", "publishedAt": None, "channel": None},
        "references": [{"label": "Página oficial fictícia", "url": "https://www.lojaficticia.example/produto/c001"}],
        "eligibility": {"agentPublicationEligible": False, "blockReason": "curadoria_manual_sem_verificacao_comercial"},
    }
    return _mod(d, **over)


def _mod(d, **over):
    d = copy.deepcopy(d)
    for caminho, valor in over.items():
        partes = caminho.split("__")
        alvo = d
        for p in partes[:-1]:
            alvo = alvo[int(p)] if isinstance(alvo, list) else alvo[p]
        if valor is _DEL:
            alvo.pop(partes[-1], None)
        else:
            alvo[partes[-1]] = valor
    return d


_DEL = object()


def v11(obj):
    return validar_produto(obj, AGORA, contrato="1.1")


def erros(obj, contrato="1.1"):
    r = validar_produto(obj, AGORA, contrato=contrato)
    assert not r.ok, "esperava rejeição"
    return " | ".join(r.erros)


class FonteTest(BaseV11):
    def test_curadoria_valida_no_contrato_1_1(self):
        r = v11(curadoria())
        self.assertTrue(r.ok, r.erros)
        self.assertEqual((r.dados["source"], r.dados["product"]["provider"], r.dados["price"]["amountCents"]),
                         ({"kind": FONTE_CURADORIA, "system": SISTEMA_CURADORIA}, "CURADORIA", None))

    def test_combinacao_obrigatoria_de_kind_system_provider(self):
        casos = {
            "system do agente": curadoria(source__system=SISTEMA_AGENTE),
            "system inventado": curadoria(source__system="Outro-Sistema"),
            "provider de outra loja": curadoria(product__provider="EXEMPLO_B"),
            "provider em minúsculas": curadoria(product__provider="curadoria"),
        }
        for nome, obj in casos.items():
            self.assertFalse(v11(obj).ok, nome)
        e = erros(curadoria(source__system=SISTEMA_AGENTE))
        self.assertIn("source.system", e)

    def test_tipos_do_agente_exigem_sistema_do_agente_e_nao_usam_o_provider_reservado(self):
        for obj in (produto_b(4, "B001", source__system=SISTEMA_CURADORIA), produto_a(1, "A001", source__system=SISTEMA_CURADORIA)):
            self.assertFalse(v11(obj).ok)
        for obj in (produto_b(4, "B001", product__provider="CURADORIA"), produto_a(1, "A001", product__provider="CURADORIA")):
            for contrato in ("1.0", "1.1"):
                self.assertIn("reservado", erros(obj, contrato))

    def test_curadoria_nunca_entra_em_a(self):
        gravar_lote(self.exp / "A", {"c.json": curadoria(), "a.json": produto_a(1, "A001")})
        l = ler_lote(self.exp / "A", AGORA, "A")
        self.assertEqual(([x.arquivo for x in l.leitura.lidos], [r.arquivo for r in l.leitura.rejeitados]), (["a.json"], ["c.json"]))
        self.assertIn("só entra em B/", l.leitura.rejeitados[0].motivos[0])
        gravar_lote(self.exp / "B", {"c.json": curadoria()})
        lb = ler_lote(self.exp / "B", AGORA, "B")
        self.assertEqual((lb.status, [x.arquivo for x in lb.leitura.lidos]), ("ok", ["c.json"]))

    def test_modo_1_0_rejeita_curadoria_preco_nulo_e_identificadores(self):
        self.assertTrue(v11(curadoria()).ok)
        self.assertFalse(validar_produto(curadoria(), AGORA).ok)                        # padrão = 1.0
        self.assertFalse(validar_produto(curadoria(), AGORA, contrato="1.0").ok)
        e = erros(curadoria(), "1.0")
        self.assertIn("source.kind", e)
        self.assertIn("source.system", e)
        # leitor e pipeline do modo 1.0
        gravar_lote(self.exp / "B", {"c.json": curadoria()})
        lei = ler_pasta(self.exp / "B", AGORA)
        self.assertEqual((lei.lidos, [r.destino for r in lei.rejeitados]), ([], ["rejeitado"]))
        r = processar(self.exp / "B", self.saida, AGORA)
        self.assertEqual((r["fichas"], r["rejeitados"]), (0, 1))

    def test_contrato_desconhecido_e_erro_de_programacao(self):
        with self.assertRaises(ValueError):
            validar_produto(curadoria(), AGORA, contrato="2.0")

    def test_validador_padrao_continua_igual_para_as_fontes_do_agente(self):
        for obj in (produto_a(1, "A001"), produto_b(4, "B001")):
            self.assertEqual(validar_produto(obj, AGORA).dados, validar_produto(obj, AGORA, contrato="1.1").dados)


class PrecoNuloTest(BaseV11):
    def test_preco_nulo_e_exclusivo_da_curadoria(self):
        for obj in (produto_b(4, "B001", price__amountCents=None), produto_a(1, "A001", price__amountCents=None)):
            for contrato in ("1.0", "1.1"):
                self.assertIn("price.amountCents", erros(obj, contrato))
        self.assertTrue(v11(curadoria()).ok)

    def test_tipos_de_preco_invalidos_continuam_invalidos(self):
        for ruim in (0, -1, "10", "", 1.5, 99.99, True, False, [], {}, 10 ** 10):
            self.assertIn("price.amountCents", erros(curadoria(price__amountCents=ruim)), repr(ruim))

    def test_preco_ausente_continua_obrigatorio(self):
        self.assertIn("price.amountCents", erros(curadoria(price__amountCents=_DEL)))

    def test_com_preco_nulo_verificacao_e_validade_devem_ser_nulas(self):
        for campo, valor in (("verifiedAt", "2026-11-17T12:00:00Z"), ("validUntil", "2026-11-17T20:00:00Z"),
                             ("originalAmountCents", 15000)):
            self.assertIn(f"price.{campo}", erros(curadoria(**{f"price__{campo}": valor})), campo)
        for verif in ("catalogo_sem_verificacao", "ao_vivo"):
            self.assertIn("price.verification", erros(curadoria(price__verification=verif)), verif)
        self.assertIn("price.currency", erros(curadoria(price__currency="USD")))

    def test_preco_nao_nulo_em_curadoria_segue_as_regras_de_b(self):
        ok = curadoria(price__amountCents=1990, price__verification="catalogo_sem_verificacao")
        self.assertTrue(v11(ok).ok)
        self.assertIn("price.verification", erros(curadoria(price__amountCents=1990, price__verification="ao_vivo")))

    def test_disponibilidade_obrigatoriamente_desconhecida(self):
        for disp in ("in_stock", "out_of_stock"):
            self.assertIn("availability", erros(curadoria(availability=disp)), disp)
        self.assertIn("availability", erros(curadoria(availability=_DEL)))
        self.assertIn("availability", erros(curadoria(availability="talvez")))
        self.assertTrue(v11(curadoria(availability="unknown")).ok)

    def test_publicacao_e_elegibilidade_de_b_se_aplicam(self):
        self.assertIn("publication.state", erros(curadoria(publication__state="publicada")))
        self.assertIn("agentPublicationEligible", erros(curadoria(eligibility__agentPublicationEligible=True)))
        self.assertIn("affiliateUrl", erros(curadoria(product__affiliateUrl="https://afiliado.lojaficticia.example/ir/1")))


class UrlsEFatosTest(BaseV11):
    def test_officialurl_e_referencias(self):
        ruins = {"http": "http://www.lojaficticia.example/p/1", "credenciais": "https://u:s@www.lojaficticia.example/p",
                 "porta": "https://www.lojaficticia.example:8443/p", "ip": "https://203.0.113.9/p", "localhost": "https://localhost/p",
                 "rastreio": "https://www.lojaficticia.example/p?utm_source=x", "sessao": "https://www.lojaficticia.example/p?sessionid=1",
                 "malformada": "https://", "vazia": "", "encurtador": "https://bit.ly/abc123",
                 "encurtador_sub": "https://www.bit.ly/abc", "punycode": "https://xn--lojaficticia-9db.example/p"}
        for nome, url in ruins.items():
            self.assertFalse(v11(curadoria(product__officialUrl=url)).ok, nome)
            self.assertFalse(v11(curadoria(references__0__url=url)).ok, nome)

    def test_mensagens_nao_vazam_a_url(self):
        e = erros(curadoria(product__officialUrl="https://bit.ly/SEGREDO-NAO-VAZAR"))
        self.assertNotIn("SEGREDO-NAO-VAZAR", e)

    def test_sourceref_https_obrigatorio_e_verificavel_pelo_nome(self):
        for ruim in ("Página do fabricante", "fonte: manual do produto", "http://fonte.example/x", "https://t.co/abc",
                     "https://fonte.example/x?utm_campaign=1", "https://203.0.113.5/x", None):
            self.assertFalse(v11(curadoria(verifiedFacts__0__sourceRef=ruim)).ok, repr(ruim))
        self.assertTrue(v11(curadoria(verifiedFacts__0__sourceRef="https://fonte.fabricante.example/manual#cap2")).ok)

    def test_cada_fato_tem_sourceref_e_data_valida_nao_futura(self):
        for campo in ("sourceRef", "verifiedAt", "text"):
            self.assertFalse(v11(curadoria(**{f"verifiedFacts__0__{campo}": _DEL})).ok, campo)
        for ruim in ("ontem", "2026-11-17", "2026-12-31T00:00:00Z", None):
            self.assertFalse(v11(curadoria(verifiedFacts__0__verifiedAt=ruim)).ok, repr(ruim))

    def test_limite_de_20_fatos(self):
        fatos = [{**FATO, "text": f"Característica {i}"} for i in range(20)]
        self.assertTrue(v11(curadoria(verifiedFacts=fatos)).ok)
        self.assertFalse(v11(curadoria(verifiedFacts=fatos + [dict(FATO)])).ok)

    def test_janela_de_30_dias_existente_continua_valendo(self):
        velho = {**FATO, "text": "Fato verificado há muito tempo", "verifiedAt": "2026-09-01T12:00:00Z"}
        _, fs = self.rodar(b={"c.json": curadoria(verifiedFacts=[FATO, velho])}, humanos=self.humanos())
        f = fs[CHAVE]
        self.assertEqual([x["text"] for x in f["fatosParaUso"]], [FATO["text"]])
        self.assertEqual([x["text"] for x in f["fatosEmRevisao"]], [velho["text"]])

    def test_url_valida_nao_equivale_a_verificacao(self):
        # documentado e testado: o validador aceita QUALQUER https fora das listas; autenticidade segue sendo revisão humana
        r = v11(curadoria(verifiedFacts__0__sourceRef="https://qualquer-site.example/qualquer-coisa"))
        self.assertTrue(r.ok)
        self.assertIn("NÃO prova", cur.__doc__)

    def test_utilitarios_de_host(self):
        self.assertTrue(cur.host_encurtador("bit.ly") and cur.host_encurtador("x.y.tinyurl.com"))
        self.assertFalse(cur.host_encurtador("abit.ly"))
        self.assertIsNone(cur.host_nao_verificavel("www.lojaficticia.example"))
        self.assertIsNotNone(cur.host_nao_verificavel("10.0.0.1"))


class AlegacoesComerciaisTest(BaseV11):
    COMERCIAIS = {
        "preco": ["Panela por apenas 99 reais", "Custa R$ 99", "Preço especial"],
        "desconto_promocao": ["Panela em promoção", "Cupom de desconto", "Oferta da semana", "Liquidação total"],
        "frete_gratis": ["Panela com frete grátis", "Entrega gratuita"],
        "estoque_disponibilidade": ["Panela em estoque", "Últimas unidades", "Produto disponível", "Esgotado"],
        "urgencia": ["Corra e garanta", "Só hoje", "Último dia", "Por tempo limitado"],
        "menor_preco": ["Menor preço do ano", "O mais barato"],
        "percentual_promocional": ["Panela 30% OFF", "20% de desconto"],
    }

    def test_titulos_com_alegacao_comercial_sao_rejeitados(self):
        for cat, titulos in self.COMERCIAIS.items():
            for t in titulos:
                self.assertTrue(cur.alegacoes_comerciais(t), t)
                self.assertFalse(v11(curadoria(product__title=t)).ok, t)

    def test_fatos_com_alegacao_comercial_sao_rejeitados(self):
        for t in ("Frete grátis para todo o Brasil", "Em estoque agora", "Aproveite 30% OFF", "Menor preço garantido",
                  "Disponível para pronta entrega", "Só hoje na loja", "Preço de R$ 10"):
            self.assertFalse(v11(curadoria(verifiedFacts__0__text=t)).ok, t)
        self.assertIn("alegação comercial", erros(curadoria(verifiedFacts__0__text="Frete grátis")))

    def test_titulo_de_risco_alta_e_rejeitado(self):
        for t in ("Fone Original Premium", "Sérum que emagrece", "Produto oficial da marca", "Melhor panela do mercado",
                  "Aparelho com certificação Inmetro", "Kit exclusivo"):
            self.assertFalse(v11(curadoria(product__title=t)).ok, t)
        self.assertIn("ALTA", erros(curadoria(product__title="Fone Original")))

    def test_titulo_de_risco_media_sem_alegacao_comercial_gera_aviso(self):
        r = v11(curadoria(product__title="Power bank 10000 mAh potente"))
        self.assertTrue(r.ok, r.erros)
        self.assertTrue(any("MÉDIA" in a for a in r.avisos), r.avisos)

    def test_fatos_com_risco_alto_nao_comercial_ou_medio_geram_aviso_sem_rejeitar(self):
        r = v11(curadoria(verifiedFacts__0__text="Garantia de 12 meses do fabricante"))
        self.assertTrue(r.ok, r.erros)
        self.assertTrue(any("ALTA" in a for a in r.avisos))
        r2 = v11(curadoria(verifiedFacts__0__text="Bateria de 5000 mAh"))
        self.assertTrue(r2.ok and any("MÉDIA" in a for a in r2.avisos))

    def test_titulos_e_fatos_normais_passam(self):
        for t in ("Panela de Pressão 5L", "Caneta esferográfica azul", "Chaleira elétrica inox"):
            self.assertEqual(cur.alegacoes_comerciais(t), [], t)
            self.assertTrue(v11(curadoria(product__title=t)).ok, t)

    def test_mensagens_nao_ecoam_o_texto_rejeitado(self):
        e = erros(curadoria(product__title="Frete grátis SEGREDO-NAO-VAZAR"))
        self.assertNotIn("SEGREDO-NAO-VAZAR", e)

    def test_limitacoes_estao_documentadas(self):
        for termo in ("falso positivo", "falso negativo"):
            self.assertIn(termo, cur.__doc__)


class FichaEPipelineTest(BaseV11):
    def ficha(self, produto=None, decisoes=None):
        h = self.humanos(decisoes=decisoes)
        r, fs = self.rodar(b={"c.json": produto or curadoria()}, humanos=h)
        return fs[CHAVE], r

    def dec(self, n, tipo="aprovado_para_rascunho", data="2026-11-17T14:30:00Z"):
        return {"provider": "CURADORIA", "productId": "C001", "exportId": uid(n), "decisao": tipo, "autor": "Maria Revisora",
                "data": data, "motivo": "teste"}

    def test_ficha_sem_preco_e_candidato_nao_verificado_e_renderiza_com_seguranca(self):
        f, r = self.ficha()
        self.assertEqual((f["estado"], f["origem"], f["fonte"]), (estados.CANDIDATO_NAO_VERIFICADO, "B", FONTE_CURADORIA))
        self.assertEqual((f["preco"]["amountCents"], f["preco"]["exibicao"], f["alegacaoComercialPermitida"]), (None, None, False))
        self.assertTrue(any("sem preço verificado" in a for a in f["avisos"]))
        md = (self.saida / "fichas" / f"{CHAVE}.md").read_text()
        self.assertIn("sem preço verificado", md)
        self.assertNotIn("None", md)
        self.assertEqual(r["fichasPorEstado"], {"candidato_nao_verificado": 1})

    def test_aprovacao_editorial_vale_e_publicacao_nunca(self):
        f, _ = self.ficha(decisoes=[self.dec(11)])
        self.assertEqual(f["estado"], estados.APROVADO_RASCUNHO)
        self.setUp()
        f, _ = self.ficha(decisoes=[self.dec(11, "aprovado_para_publicacao")])
        self.assertEqual((f["estado"], f["decisoesInaplicaveis"][0]["codigo"]), (estados.CANDIDATO_NAO_VERIFICADO, "fonte_b_sem_publicacao"))

    def test_curadoria_em_lote_b_com_manifesto_integro_e_lote_adulterado_em_quarentena(self):
        gravar_lote(self.exp / "B", {"c.json": curadoria()})
        self.assertEqual(ler_lote(self.exp / "B", AGORA, "B").status, "ok")
        with open(self.exp / "B" / "c.json", "a") as fh:
            fh.write(" ")
        l = ler_lote(self.exp / "B", AGORA, "B")
        self.assertEqual((l.status, l.leitura.lidos), ("quarentena_de_lote", []))

    def test_historico_e_resumo_com_preco_nulo(self):
        f, r = self.ficha()
        h = json.loads((self.saida / "historico.json").read_text())
        self.assertIsNone(h[0]["versoes"][0]["amountCents"])
        self.assertEqual(h[0]["versoes"][0]["fonte"], FONTE_CURADORIA)

    def test_mudanca_de_nulo_para_valor_nao_quebra_a_ficha(self):
        v1 = curadoria(11)
        v2 = curadoria(12, exportedAt="2026-11-17T14:00:00Z", price__amountCents=1990, price__verification="catalogo_sem_verificacao")
        _, fs = self.rodar(b={"a.json": v1, "b.json": v2}, humanos=self.humanos())
        f = fs[CHAVE]
        self.assertTrue(any("sem preço verificado" in a and "R$ 19,90" in a for a in f["avisos"]), f["avisos"])

    def test_carrossel_editorial_da_curadoria_nao_tem_nenhuma_informacao_comercial(self):
        f, _ = self.ficha()
        r = ficha_para_carrossel_v11(f, t_publicacao=AGORA, foto_catalogo_id="cg-0001", recurso_visual="composicao_grafica",
                                     catalogo={"cg-0001": {"provedor": "composicao-grafica", "origem": "composicao-grafica",
                                                           "aprovacao": {"status": "aprovada"}}})
        self.assertEqual((r["status"], r["origem"]), ("rascunho", "B"))
        txt = json.dumps(r["carrossel"], ensure_ascii=False)
        for proibido in ("R$", "%", "estoque", "OFF", "frete"):
            self.assertNotIn(proibido, txt)

    def test_processamento_a_b_existente_nao_muda_com_curadoria_ao_lado(self):
        a, b = {"a.json": a_com(1)}, {"b.json": produto_b(4, "B001")}
        d = [{"provider": "EXEMPLO_A", "productId": "A001", "exportId": uid(1), "decisao": "aprovado_para_rascunho",
              "autor": "Maria Revisora", "data": "2026-11-17T14:30:00Z", "motivo": "t"}]
        _, sem = self.rodar(a=a, b=b, humanos=self.humanos(decisoes=d))
        sem_a, sem_b = copy.deepcopy(sem["EXEMPLO_A__A001"]), copy.deepcopy(sem["EXEMPLO_B__B001"])
        self.setUp()
        _, com = self.rodar(a=a, b={**b, "c.json": curadoria()}, humanos=self.humanos(decisoes=d))
        self.assertEqual((com["EXEMPLO_A__A001"], com["EXEMPLO_B__B001"]), (sem_a, sem_b))
        self.assertEqual(com[CHAVE]["estado"], estados.CANDIDATO_NAO_VERIFICADO)

    def test_exemplos_ficticios_do_1_1_continuam_iguais(self):
        from produtos.pipeline_v11 import processar_v11
        ex = EXEMPLOS.parent / "exemplos_ficticios_v1_1"
        r = processar_v11(ex / "exportacoes", self.saida, AGORA, decisoes_arquivo=ex / "decisoes" / "decisoes.json",
                          permissoes_arquivo=ex / "decisoes" / "permissoes_fotos.json",
                          termos_arquivo=ex / "decisoes" / "termos_programas.json", fotos_dir=ex / "fotos")
        self.assertEqual(r["fichasPorEstado"], {"aprovado_para_rascunho": 2, "incompleto": 1})


class P08Test(BaseV11):
    def dec(self, n=11):
        return {"provider": "CURADORIA", "productId": "C001", "exportId": uid(n), "decisao": "aprovado_para_rascunho",
                "autor": "Maria Revisora", "data": "2026-11-17T14:30:00Z", "motivo": "teste"}

    def ficha(self, produtos):
        _, fs = self.rodar(b={f"c{i}.json": p for i, p in enumerate(produtos, 1)}, humanos=self.humanos(decisoes=[self.dec()]))
        return fs[CHAVE]

    def reexport(self, **over):
        return curadoria(12, exportedAt="2026-11-17T14:50:00Z", **over)

    def test_reexportacao_sem_mudanca_material_mantem_a_aprovacao(self):
        novo = self.reexport(verifiedFacts__0__verifiedAt="2026-11-17T09:00:00Z")
        f = self.ficha([curadoria(11), novo])
        self.assertEqual((f["estado"], f["decisoesInaplicaveis"]), (estados.APROVADO_RASCUNHO, []))
        self.assertEqual(f["impressaoMaterialDecisao"]["impressaoRevisada"], f["impressaoMaterialDecisao"]["impressaoAtual"])

    def test_mudancas_materiais_invalidam_com_o_codigo_certo(self):
        casos = {"identidade_mudou": dict(product__title="Outro Título Fictício"),
                 "fatos_mudaram": dict(verifiedFacts__0__text="Capacidade de 6 litros"),
                 "fonte_comprovacao_mudou": dict(verifiedFacts__0__sourceRef="https://outra.fonte.example/c001")}
        for codigo, mud in casos.items():
            self.setUp()
            f = self.ficha([curadoria(11), self.reexport(**mud)])
            self.assertEqual(f["decisoesInaplicaveis"][0]["codigo"], codigo, codigo)
            self.assertNotEqual(f["estado"], estados.APROVADO_RASCUNHO, codigo)

    def test_impressao_com_preco_nulo_e_deterministica(self):
        v = lambda o, n=1: Versao(f"v{n}.json", "0" * 64, validar_produto(o, AGORA, contrato="1.1").dados, parse_data(o["exportedAt"]))
        a, b = v(curadoria(11)), v(self.reexport(), 2)
        for tipo in ("aprovado_para_rascunho", "aprovado_para_publicacao"):
            self.assertEqual(imp.impressao(a, tipo), imp.impressao(b, tipo))
        self.assertEqual(imp.diferencas(a, b, "aprovado_para_publicacao"), [])


if __name__ == "__main__":
    unittest.main()
