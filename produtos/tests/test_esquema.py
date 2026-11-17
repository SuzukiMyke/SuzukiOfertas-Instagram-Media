"""Testes 1–3: validação, separação A × B e campos proibidos/desconhecidos."""
import unittest

from produtos import esquema
from produtos.tests.base import AGORA, DEL, Base, mod, produto_a, produto_b


def validar(d):
    return esquema.validar_produto(d, AGORA)


class ValidosTest(Base):
    def test_a_e_b_validos(self):
        for d in (produto_a(), produto_b()):
            r = validar(d)
            self.assertTrue(r.ok, r.erros)
            self.assertEqual(r.erros, [])

    def test_b_api_candidato_e_foto_opcional(self):
        self.assertTrue(validar(produto_b(source__kind="api_candidato")).ok)

    def test_dados_normalizados_so_tem_campos_permitidos(self):
        r = validar(produto_b())
        self.assertEqual(set(r.dados), set(esquema.TOPO))
        self.assertEqual(set(r.dados["product"]), set(esquema.CAMPOS["product"]))
        self.assertEqual(r.dados["photo"]["usePermission"], "pendente")   # padrão quando ausente

    def test_aviso_categoria_ausente(self):
        r = validar(produto_b(product__category=None, product__categoryOrigin=None))
        self.assertTrue(r.ok)
        self.assertTrue(any("categoria ausente" in a for a in r.avisos))


class InvalidosTest(Base):
    CASOS = {
        "obrigatorio_ausente": (produto_a(product__title=DEL), "product.title: campo obrigatório ausente"),
        "obrigatorio_ausente_preco": (produto_a(price__amountCents=DEL), "price.amountCents"),
        "tipo_errado_titulo": (produto_a(product__title=123), "product.title: esperado texto"),
        "titulo_vazio": (produto_a(product__title="   "), "product.title"),
        "titulo_longo": (produto_a(product__title="x " * 130), "product.title: excede 240"),
        "preco_decimal": (produto_a(price__amountCents=129.9), "price.amountCents"),
        "preco_texto": (produto_a(price__amountCents="12990"), "price.amountCents"),
        "preco_bool": (produto_a(price__amountCents=True), "price.amountCents"),
        "preco_zero": (produto_a(price__amountCents=0), "maior que zero"),
        "preco_negativo": (produto_a(price__amountCents=-5), "maior que zero"),
        "moeda": (produto_a(price__currency="USD"), "moeda deve ser BRL"),
        "url_http": (produto_a(product__officialUrl="http://www.lojaficticia.example/p"), "https://"),
        "url_credenciais": (produto_a(product__officialUrl="https://u:p@www.lojaficticia.example/p"), "credenciais"),
        "url_porta": (produto_a(product__officialUrl="https://www.lojaficticia.example:8443/p"), "porta"),
        "url_token": (produto_a(product__officialUrl="https://www.lojaficticia.example/p?access_token=ABC"), "token"),
        "url_sessao": (produto_a(product__officialUrl="https://www.lojaficticia.example/p?JSESSIONID=1"), "sessão"),
        "url_rastreio_oficial": (produto_a(product__officialUrl="https://www.lojaficticia.example/p?utm_source=x"), "rastreio"),
        "url_ip": (produto_a(product__officialUrl="https://203.0.113.9/p"), "host"),
        "url_localhost": (produto_a(product__officialUrl="https://localhost/p"), "host"),
        "url_espaco": (produto_a(product__officialUrl="https://www.lojaficticia.example/a b"), "URL"),
        "afiliado_com_token": (produto_a(product__affiliateUrl="https://a.lojaficticia.example/x?token=1"), "token"),
        "foto_url_http": (produto_a(photo__url="http://cdn.lojaficticia.example/a.jpg"), "photo.url"),
        "referencia_url_http": (produto_a(references__0__url="http://x.lojaficticia.example/"), "references[0].url"),
        "data_invalida": (produto_a(exportedAt="2026-13-45T10:00:00Z"), "exportedAt: data inválida"),
        "data_texto": (produto_a(exportedAt="ontem"), "exportedAt"),
        "data_sem_zona": (produto_a(exportedAt="2026-11-17T10:00:00"), "exportedAt"),
        "data_futura": (produto_a(exportedAt="2026-11-18T10:00:00Z"), "data no futuro"),
        "verificado_futuro": (produto_a(price__verifiedAt="2026-11-17T16:00:00Z"), "price.verifiedAt: data no futuro"),
        "valido_antes_de_verificado": (produto_a(price__validUntil="2026-11-17T12:00:00Z"), "posterior"),
        "export_id": (produto_a(exportId="nao-e-uuid"), "exportId"),
        "semver_malformado": (produto_a(schemaVersion="1"), "semver"),
        "sistema_desconhecido": (produto_a(source__system="OutroSistema"), "sistema de origem"),
        "kind_desconhecido": (produto_a(source__kind="manual"), "source.kind"),
        "disponibilidade": (produto_a(availability="talvez"), "availability"),
        "id_com_barra": (produto_a(product__id="../x"), "product.id"),
        "provider_minusculo": (produto_a(product__provider="awin"), "product.provider"),
        "canal_id_privado": (produto_a(publication__channel="-1001234567890"), "publication.channel"),
        "caractere_controle": (produto_a(product__title="Produto\x07 teste"), "controle"),
        "bidi": (produto_a(product__title="Produto‮ teste"), "controle"),
        "raiz_nao_objeto": ([1, 2], "objeto"),
        "foto_confirmada_sem_ref": (produto_a(photo__permissionRef=None), "permissionRef"),
        "foto_confirmada_sem_url": (produto_a(photo__url=None), "photo.url"),
        "foto_confirmada_sem_data": (produto_a(photo__checkedAt=None), "checkedAt"),
        "fatos_demais": (produto_a(verifiedFacts=[{"text": "a", "sourceRef": "doc", "verifiedAt": "2026-11-17T10:00:00Z"}] * 21), "verifiedFacts"),
    }

    def test_cada_caso_invalido_e_rejeitado_com_motivo_claro(self):
        for nome, (d, trecho) in self.CASOS.items():
            with self.subTest(nome):
                r = validar(d)
                self.assertEqual(r.destino, "rejeitado", r.erros)
                self.assertTrue(any(trecho in e for e in r.erros), (trecho, r.erros))
                self.assertIsNone(r.dados)

    def test_major_desconhecida_vai_para_quarentena(self):
        for v in ("2.0.0", "0.9.0", "10.1.1"):
            r = validar(produto_a(schemaVersion=v))
            self.assertEqual(r.destino, "quarentena", v)
        self.assertTrue(validar(produto_a(schemaVersion="1.3.7")).ok)     # mesma major, minor/patch novos

    def test_sem_schemaversion_ou_exportid_e_ignorado(self):
        for ch in ("schemaVersion", "exportId"):
            r = validar(produto_a(**{ch: DEL}))
            self.assertEqual(r.destino, "ignorado")

    def test_dados_insuficientes_lista_campos_faltantes(self):
        r = validar(produto_a(product__title=DEL, price__currency=DEL))
        self.assertEqual(r.destino, "rejeitado")
        self.assertTrue(r.dados_insuficientes)
        self.assertEqual(sorted(r.faltantes), ["price.currency", "product.title"])
        r2 = validar(produto_a(product__title=DEL, price__currency="USD"))
        self.assertFalse(r2.dados_insuficientes)


class FontesATest(Base):
    """Teste 2: separação A × B."""

    def test_a_exige_verificacao_publicacao_e_afiliado(self):
        casos = [
            (produto_a(price__verifiedAt=None), "price.verifiedAt"),
            (produto_a(price__validUntil=None), "price.validUntil"),
            (produto_a(price__verification="catalogo_sem_verificacao"), "verificação ao vivo"),
            (produto_a(publication__state="nao_publicada"), "state='publicada'"),
            (produto_a(publication__publishedAt=None), "publication.publishedAt"),
            (produto_a(product__affiliateUrl=None), "product.affiliateUrl"),
            (produto_a(photo=DEL), "photo.usePermission"),
            (produto_a(photo__usePermission=DEL), "photo.usePermission"),
        ]
        for d, trecho in casos:
            r = validar(d)
            self.assertEqual(r.destino, "rejeitado", trecho)
            self.assertTrue(any(trecho in e for e in r.erros), (trecho, r.erros))

    def test_b_nao_pode_ser_publicada_nem_elegivel(self):
        casos = [
            (produto_b(publication__state="publicada"), "nao_publicada"),
            (produto_b(publication__publishedAt="2026-11-17T10:00:00Z"), "data de publicação"),
            (produto_b(eligibility__agentPublicationEligible=True), "nunca pode ser elegível"),
            (produto_b(product__affiliateUrl="https://a.lojaficticia.example/x"), "link de afiliado"),
            (produto_b(price__verification="ao_vivo"), "não pode declarar verificação ao vivo"),
        ]
        for d, trecho in casos:
            r = validar(d)
            self.assertEqual(r.destino, "rejeitado", trecho)
            self.assertTrue(any(trecho in e for e in r.erros), (trecho, r.erros))

    def test_b_nao_exige_afiliado_nem_verificacao_nem_foto(self):
        d = produto_b()
        self.assertIsNone(d["product"]["affiliateUrl"])
        self.assertTrue(validar(d).ok)

    def test_source_kind_inconsistente_com_campos(self):
        # A com campos de B e B com campos de A são rejeitados
        self.assertFalse(validar(produto_a(source__kind="catalogo_candidato")).ok)
        self.assertFalse(validar(produto_b(source__kind="agente_publicada")).ok)


class ProibidosTest(Base):
    """Teste 3: lista de permissão de campos."""

    def test_campos_proibidos_rejeitam_o_arquivo(self):
        casos = {
            "telegramUpdateId": produto_a(telegramUpdateId=1),
            "token": produto_a(token="x"),
            "apiKey": produto_a(apiKey="x"),
            "operatorId": produto_a(operatorId=1),
            "chat_id": produto_a(chat_id=1),
            "product.password": produto_a(product__password="x"),
            "photo.sessionId": produto_a(photo__sessionId="x"),
            "source.cofre": produto_a(source__cofre="x"),
        }
        for nome, d in casos.items():
            with self.subTest(nome):
                r = validar(d)
                self.assertEqual(r.destino, "rejeitado")
                self.assertTrue(any("campo proibido" in e for e in r.erros), r.erros)

    def test_campos_desconhecidos_e_comentarios_rejeitam(self):
        for d in (produto_a(foo=1), produto_a(_comment="x"), produto_a(product__extra="x"),
                  produto_a(verifiedFacts=[{"text": "a", "sourceRef": "d", "verifiedAt": "2026-11-17T10:00:00Z", "x": 1}])):
            r = validar(d)
            self.assertEqual(r.destino, "rejeitado")
            self.assertTrue(any("campo desconhecido" in e for e in r.erros), r.erros)

    def test_mensagens_nao_ecoam_valores_suspeitos(self):
        segredo = "VALOR-SECRETO-NAO-ECOAR"
        casos = [
            produto_a(token=segredo),
            produto_a(product__officialUrl=f"https://www.lojaficticia.example/p?token={segredo}"),
            produto_a(product__title="123456789:" + "A" * 35),            # parece token de bot
            produto_a(product__title="chave " + "Ab1" * 20),               # sequência opaca longa
            produto_a(product__title="Bearer " + "x" * 30),
            produto_a(product__title="-----BEGIN PRIVATE KEY-----"),
            produto_a(photo__permissionRef="ghp_" + "a" * 30),
        ]
        for d in casos:
            r = validar(d)
            self.assertEqual(r.destino, "rejeitado")
            texto = " ".join(r.erros)
            self.assertNotIn(segredo, texto)
            self.assertNotIn("A" * 20, texto)
            self.assertNotIn("x" * 20, texto)
            self.assertNotIn("ghp_", texto)

    def test_chave_com_valor_estranho_e_sanitizada_na_mensagem(self):
        d = produto_a()
        d["campo\nmalicioso‮"] = 1
        r = validar(d)
        self.assertTrue(all(c not in " ".join(r.erros) for c in ("\n", "‮")))


if __name__ == "__main__":
    unittest.main()
