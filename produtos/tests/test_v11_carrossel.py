"""Ponte ficha v1.1 -> carrossel: regras comerciais, títulos, imagens, CTA, determinismo e compatibilidade REAL com o gerador híbrido."""
import copy
import hashlib
import json
import re
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from PIL import Image

from produtos import carrossel_fragmento_v11 as cf
from produtos.carrossel_fragmento_v11 import CarrosselRecusado, ficha_para_carrossel_v11
from produtos.tests.base_v11 import (AGORA, FOTO_SHA, BaseV11, a_com, a_expirada, b_de, permissao, produto_a, produto_b, uid)

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = Path(__file__).resolve().parents[1]
CHAVE_A, CHAVE_B = "EXEMPLO_A__A001", "EXEMPLO_B__B001"
LINKS = {"whatsapp": "https://wa.me/5511999999999", "telegram": "https://t.me/suzukiofertas_ficticio"}
PRECO = {"id": "p", "tipo": "preco", "funcao": "essencial"}
OFERTA = {"id": "o", "tipo": "oferta", "funcao": "acessoria", "texto": "Confira a seleção da loja"}
FATO = {"text": "Capacidade de 5 litros", "sourceRef": "Página fictícia", "verifiedAt": "2026-11-16T12:00:00Z"}
CAT = {
    "real-0001": {"provedor": "foto-real", "origem": "fotografia-real", "sha256_original": FOTO_SHA, "sha256": "f" * 64,
                  "aprovacao": {"status": "aprovada"}},
    "nb-0001": {"provedor": "nano-banana", "origem": "ia", "sha256_original": "e" * 64, "sha256": "d" * 64,
                "aprovacao": {"status": "aprovada"}},
    "nb-0002": {"provedor": "nano-banana", "origem": "ia", "sha256_original": "c" * 64, "sha256": "b" * 64,
                "aprovacao": {"status": "pendente"}},
}
PROIBIDOS_B = re.compile(r"R\$|%|estoque|urgen|últim|ultim|menor preço|desconto|\boferta\b|\boff\b", re.I)


class CarrosselBase(BaseV11):
    def ficha_a(self, produto=None, tipo="aprovado_para_rascunho", permissoes=None, **kw):
        d = [{"provider": "EXEMPLO_A", "productId": "A001", "exportId": uid(1), "decisao": tipo, "autor": "Maria Revisora",
              "data": "2026-11-17T14:30:00Z", "motivo": "teste"}] if tipo else []
        _, f = self.rodar(a={"a.json": produto or a_com(1)}, humanos=self.humanos(decisoes=d, permissoes=permissoes), **kw)
        return f[CHAVE_A]

    def ficha_b(self, produto=None, **kw):
        _, f = self.rodar(b={"b.json": produto or produto_b(4, "B001")}, humanos=self.humanos(), **kw)
        return f[CHAVE_B]

    def gerar(self, ficha, **kw):
        base = dict(t_publicacao=AGORA, foto_catalogo_id="nb-0001", recurso_visual="composicao_grafica", catalogo=CAT)
        base.update(kw)
        return ficha_para_carrossel_v11(ficha, **base)

    def textos(self, r):
        return " | ".join(f"{s.get('titulo','')} {s.get('destaque','')} {s.get('texto','')}" for s in r["carrossel"]["slides"])


class FonteBTest(CarrosselBase):
    def test_b_candidato_gera_so_rascunho_editorial_sem_nenhuma_informacao_comercial(self):
        r = self.gerar(self.ficha_b(), links_oficiais=LINKS)
        self.assertEqual((r["status"], r["origem"], r["estado_ficha"]), ("rascunho", "B", "candidato_nao_verificado"))
        self.assertIsNone(PROIBIDOS_B.search(self.textos(r)), self.textos(r))
        self.assertEqual((r["alegacoes_comerciais_permitidas"], r["aprovado_para_publicacao_definido"]), ([], False))
        self.assertTrue(any("fonte B" in a for a in r["avisos"]))

    def test_b_com_alegacao_essencial_bloqueia_e_acessoria_e_omitida(self):
        r = self.gerar(self.ficha_b(), alegacoes=[PRECO])
        self.assertEqual((r["status"], r["carrossel"]), ("bloqueado", None))
        r2 = self.gerar(self.ficha_b(), alegacoes=[OFERTA])
        self.assertEqual((r2["status"], [o["id"] for o in r2["alegacoes_omitidas"]]), ("rascunho", ["o"]))
        self.assertIsNone(PROIBIDOS_B.search(self.textos(r2)))

    def test_b_aprovada_para_rascunho_tambem_e_elegivel(self):
        d = [{"provider": "EXEMPLO_B", "productId": "B001", "exportId": uid(4), "decisao": "aprovado_para_rascunho",
              "autor": "Maria Revisora", "data": "2026-11-17T14:30:00Z", "motivo": "t"}]
        _, f = self.rodar(b={"b.json": produto_b(4, "B001")}, humanos=self.humanos(decisoes=d))
        self.assertEqual(self.gerar(f[CHAVE_B])["status"], "rascunho")

    def test_ficha_em_fallback_por_a_expirada_nunca_tem_preco(self):
        _, f = self.rodar(a={"a.json": a_expirada(1)}, b={"b.json": b_de(4)}, humanos=self.humanos())
        ficha = f[CHAVE_A]
        self.assertEqual((ficha["origem"], ficha["estado"]), ("B", "candidato_nao_verificado"))
        r = self.gerar(ficha, alegacoes=[OFERTA])
        self.assertIsNone(PROIBIDOS_B.search(self.textos(r)))


class FonteATest(CarrosselBase):
    def test_janela_valida_permite_preco(self):
        r = self.gerar(self.ficha_a(), alegacoes=[PRECO], preco_aprovado_centavos=12990, links_oficiais=LINKS)
        self.assertEqual((r["status"], r["alegacoes_comerciais_permitidas"], r["portao"]["acao"]), ("rascunho", ["p"], "liberar"))
        sl = r["carrossel"]["slides"][1]
        self.assertEqual((sl["layout"], sl["destaque"]), ("cartao", "R$ 129,90"))
        self.assertIn("Preços e condições podem mudar", sl["texto"])
        self.assertIn("Preços e condições podem mudar", r["legenda_sugerida"])

    def test_janela_expirada_bloqueia_essencial_e_omite_acessoria_registrando(self):
        f = self.ficha_a()
        fora = AGORA + timedelta(hours=8)                                    # depois de validUntil (19:00)
        r = self.gerar(f, alegacoes=[PRECO], preco_aprovado_centavos=12990, t_publicacao=fora)
        self.assertEqual((r["status"], r["carrossel"], r["bloqueios"][0]["codigo"]), ("bloqueado", None, "alegacao_essencial_invalida"))
        r2 = self.gerar(f, alegacoes=[OFERTA], preco_aprovado_centavos=12990, t_publicacao=fora)
        self.assertEqual(r2["status"], "rascunho")
        self.assertEqual([(o["id"], o["tipo"]) for o in r2["alegacoes_omitidas"]], [("o", "oferta")])
        self.assertIsNone(re.search(r"R\$|oferta|confira a sele", self.textos(r2), re.I))

    def test_margem_e_limite_inclusivo_do_horario_efetivo(self):
        f = self.ficha_a()
        limite = AGORA + timedelta(hours=4) - timedelta(minutes=30)          # 18:30
        ok = self.gerar(f, alegacoes=[PRECO], preco_aprovado_centavos=12990, t_publicacao=limite)
        no = self.gerar(f, alegacoes=[PRECO], preco_aprovado_centavos=12990, t_publicacao=limite + timedelta(seconds=1))
        self.assertEqual((ok["status"], no["status"]), ("rascunho", "bloqueado"))

    def test_sem_preco_aprovado_ou_com_preco_diferente_bloqueia(self):
        f = self.ficha_a()
        for aprovado in (None, 1):
            self.assertEqual(self.gerar(f, alegacoes=[PRECO], preco_aprovado_centavos=aprovado)["status"], "bloqueado")

    def test_desconto_disponibilidade_e_oferta_com_texto_do_chamador(self):
        f = self.ficha_a(a_com(1, price__originalAmountCents=15000))
        alegs = [{"id": "d", "tipo": "desconto", "funcao": "acessoria"}, {"id": "e", "tipo": "disponibilidade", "funcao": "acessoria"},
                 OFERTA]
        r = self.gerar(f, alegacoes=alegs, preco_aprovado_centavos=12990)
        sl = {s["titulo"]: s for s in r["carrossel"]["slides"]}
        self.assertEqual(sl["DESCONTO"]["destaque"], "13% OFF")
        self.assertIn("De R$ 150,00 por R$ 129,90", sl["DESCONTO"]["texto"])
        self.assertEqual(sl["DISPONIBILIDADE"]["destaque"], "EM ESTOQUE")
        self.assertEqual(r["alegacoes_comerciais_permitidas"], ["d", "e", "o"])

    def test_desconto_sem_preco_original_e_omitido(self):
        r = self.gerar(self.ficha_a(), alegacoes=[{"id": "d", "tipo": "desconto", "funcao": "acessoria"}], preco_aprovado_centavos=12990)
        self.assertEqual([o["id"] for o in r["alegacoes_omitidas"]], ["d"])

    def test_menor_preco_exige_prova(self):
        mp = {"id": "m", "tipo": "menor_preco", "funcao": "acessoria", "texto": "Menor preço do mês"}
        r = self.gerar(self.ficha_a(), alegacoes=[mp], preco_aprovado_centavos=12990)
        self.assertEqual(r["alegacoes_comerciais_permitidas"], [])
        r2 = self.gerar(self.ficha_a(), alegacoes=[mp], preco_aprovado_centavos=12990, prova_menor_preco=True)
        self.assertEqual(r2["alegacoes_comerciais_permitidas"], ["m"])

    def test_aprovado_para_publicacao_nunca_e_definido_pela_funcao(self):
        f = self.ficha_a(tipo="aprovado_para_publicacao")
        antes = copy.deepcopy(f)
        r = self.gerar(f)
        self.assertEqual(f, antes)                                            # a ficha não é alterada
        self.assertEqual((r["status"], r["aprovado_para_publicacao_definido"], r["revisao_humana_obrigatoria"]), ("rascunho", False, True))
        self.assertNotIn("aprovado_para_publicacao", json.dumps(r["carrossel"]))

    def test_aprovacao_editorial_nao_e_validade_comercial(self):
        f = self.ficha_a(tipo="aprovado_para_rascunho")
        r = self.gerar(f, alegacoes=[PRECO], preco_aprovado_centavos=12990, t_publicacao=AGORA + timedelta(hours=9))
        self.assertEqual(r["status"], "bloqueado")


class EstadosInelegiveisTest(CarrosselBase):
    def test_estados_inelegiveis_voltam_como_bloqueio_explicito_sem_conteudo(self):
        # revisão 5.14-A: estado inelegível é situação NORMAL de um lote -> relatório de bloqueio, não exceção
        base = self.ficha_a()
        casos = [(base, est) for est in ("pendente_revisao", "incompleto", "expirado", "invalidado", "rejeitado", "recebido",
                                         "candidato_nao_verificado")]
        b = self.ficha_b()
        casos += [(b, est) for est in ("pendente_revisao", "expirado", "aprovado_para_publicacao", "rejeitado", "incompleto")]
        for ficha, est in casos:
            r = self.gerar({**ficha, "estado": est})
            self.assertEqual((r["status"], r["carrossel"], r["portao"]), ("bloqueado", None, None), est)
            bl = r["bloqueios"][0]
            self.assertEqual((bl["codigo"], bl["estado"]), ("estado_inelegivel", est))
            self.assertTrue(bl["estados_elegiveis"])
            self.assertEqual((r["alegacoes_comerciais_permitidas"], r["aprovado_para_publicacao_definido"]), ([], False))

    def test_chamadas_invalidas(self):
        f = self.ficha_a()
        for kw in (dict(t_publicacao=AGORA.replace(tzinfo=None)), dict(recurso_visual="foto_qualquer")):
            with self.assertRaises(CarrosselRecusado):
                self.gerar(f, **kw)
        with self.assertRaises(CarrosselRecusado):
            self.gerar({**f, "contrato": "1.0"})
        with self.assertRaises(CarrosselRecusado):
            self.gerar(f, alegacoes=[{"id": "x", "tipo": "preco", "funcao": "talvez"}])


class TitulosTest(CarrosselBase):
    def test_risco_alta_bloqueia(self):
        f = self.ficha_a(a_com(1, product__title="Fone Original Premium Garantia"))
        r = self.gerar(f)
        self.assertEqual((r["status"], r["carrossel"], r["bloqueios"][0]["codigo"]), ("bloqueado", None, "titulo_risco_alta"))

    def test_risco_media_exige_revisao_e_registra_aviso(self):
        r = self.gerar(self.ficha_a(a_com(1, product__title="Power bank 10000 mAh")))
        self.assertEqual((r["status"], r["revisao_humana_obrigatoria"]), ("rascunho", True))
        self.assertTrue(any("MÉDIA" in a for a in r["avisos"]))

    def test_titulo_longo_e_abreviado_com_aviso(self):
        r = self.gerar(self.ficha_a(a_com(1, product__title="Panela de Pressão Elétrica Inox 5 Litros Digital Preta")))
        cap = r["carrossel"]["slides"][0]
        self.assertTrue(cap["destaque"].endswith("…"))
        self.assertTrue(any("abreviado" in a for a in r["avisos"]))


class ImagensTest(CarrosselBase):
    def test_foto_real_autorizada_com_hash_correto(self):
        r = self.gerar(self.ficha_a(), recurso_visual="foto_real_autorizada", foto_catalogo_id="real-0001")
        self.assertEqual(r["status"], "rascunho")
        sl = r["carrossel"]["slides"]
        self.assertTrue(all(s["foto"] == "real-0001" for s in sl))
        self.assertNotIn("reutilizar", sl[0])
        self.assertTrue(all(s["reutilizar"] for s in sl[1:]))                 # o gerador só repete foto com reutilizar
        self.assertNotIn("Imagem ilustrativa", sl[0]["texto"])

    def test_foto_real_sem_permissao_humana_ou_negada(self):
        # fichas A elegíveis sempre têm foto autorizada (sem ela ficam 'incompleto'); fonte B não exige foto: é o caso de teste
        neg = [permissao(provider="EXEMPLO_B", pid="B001", status="negada")]
        neg[0]["productId"] = "B001"
        for perms in ([], neg):
            self.setUp()
            _, fs = self.rodar(b={"b.json": produto_b(4, "B001")}, humanos=self.humanos(permissoes=perms))
            r = self.gerar(fs[CHAVE_B], recurso_visual="foto_real_autorizada", foto_catalogo_id="real-0001")
            self.assertEqual([b["codigo"] for b in r["bloqueios"]], ["foto_sem_permissao_humana"])
            self.assertIsNone(r["carrossel"])

    def test_permissao_exportada_pelo_agente_nao_basta(self):
        f = copy.deepcopy(self.ficha_a())
        f["foto"].update(utilizavel=False, motivo="sem registro humano de permissão de foto")      # só o agente "confirmou"
        self.assertEqual(f["foto"]["usePermission"], "confirmada")
        r = self.gerar(f, recurso_visual="foto_real_autorizada", foto_catalogo_id="real-0001")
        self.assertEqual((r["status"], r["bloqueios"][0]["codigo"]), ("bloqueado", "foto_sem_permissao_humana"))

    def test_a_sem_foto_humana_nem_e_elegivel(self):
        f = self.ficha_a(permissoes=[])
        self.assertEqual(f["estado"], "incompleto")
        r = self.gerar(f)
        self.assertEqual((r["status"], r["bloqueios"][0]["codigo"]), ("bloqueado", "estado_inelegivel"))

    def test_hash_do_catalogo_divergente(self):
        cat = copy.deepcopy(CAT)
        cat["real-0001"]["sha256_original"], cat["real-0001"]["sha256"] = "9" * 64, "8" * 64
        r = self.gerar(self.ficha_a(), recurso_visual="foto_real_autorizada", foto_catalogo_id="real-0001", catalogo=cat)
        self.assertEqual([b["codigo"] for b in r["bloqueios"]], ["foto_hash_divergente"])

    def test_foto_real_exige_catalogo_provedor_real_e_aprovacao(self):
        f = self.ficha_a()
        r = self.gerar(f, recurso_visual="foto_real_autorizada", foto_catalogo_id="real-0001", catalogo=None)
        self.assertEqual(r["bloqueios"][0]["codigo"], "foto_fora_do_catalogo")
        cat = copy.deepcopy(CAT)
        cat["real-0001"]["provedor"] = "nano-banana"
        self.assertIn("foto_nao_e_real", [b["codigo"] for b in self.gerar(f, recurso_visual="foto_real_autorizada",
                                                                         foto_catalogo_id="real-0001", catalogo=cat)["bloqueios"]])
        cat = copy.deepcopy(CAT)
        cat["real-0001"]["aprovacao"] = {"status": "pendente"}
        self.assertIn("foto_nao_aprovada_no_catalogo", [b["codigo"] for b in self.gerar(
            f, recurso_visual="foto_real_autorizada", foto_catalogo_id="real-0001", catalogo=cat)["bloqueios"]])

    def test_foto_id_obrigatoria(self):
        self.assertEqual(self.gerar(self.ficha_a(), foto_catalogo_id=None)["bloqueios"][0]["codigo"], "foto_catalogo_ausente")

    def test_ilustrativa_e_rotulada_nunca_como_fiel(self):
        for classe, rotulo in (("ambientacao_ilustrativa", "Imagem ilustrativa"), ("composicao_grafica", "Arte ilustrativa")):
            r = self.gerar(self.ficha_a(), recurso_visual=classe)
            self.assertIn(rotulo, r["carrossel"]["slides"][0]["texto"])
            self.assertIn(rotulo, r["legenda_sugerida"])
            self.assertTrue(any(rotulo in a for a in r["avisos"]))

    def test_foto_real_nao_passa_por_ilustracao_e_pendente_e_bloqueada(self):
        f = self.ficha_a()
        r = self.gerar(f, recurso_visual="ambientacao_ilustrativa", foto_catalogo_id="real-0001")
        self.assertEqual(r["bloqueios"][0]["codigo"], "foto_real_como_ilustracao")
        r2 = self.gerar(f, recurso_visual="ambientacao_ilustrativa", foto_catalogo_id="nb-0002")
        self.assertEqual(r2["bloqueios"][0]["codigo"], "foto_nao_aprovada_no_catalogo")

    def test_sem_catalogo_a_ilustrativa_so_avisa(self):
        r = self.gerar(self.ficha_a(), catalogo=None)
        self.assertEqual(r["status"], "rascunho")
        self.assertTrue(any("não verificada" in a for a in r["avisos"]))

    def test_nunca_permite_fotos_pendentes_no_gerador(self):
        self.assertIs(self.gerar(self.ficha_a())["carrossel"]["permitir_fotos_pendentes"], False)


class FatosTest(CarrosselBase):
    def test_so_fatos_frescos_nao_truncados_e_sem_termo_comercial(self):
        velho = {**FATO, "text": "Fato antigo demais", "verifiedAt": "2026-10-01T12:00:00Z"}
        longo = {**FATO, "text": ("característica longa " * 5).strip()}
        comercial = {**FATO, "text": "Com desconto exclusivo hoje"}
        f = self.ficha_a(a_com(1, verifiedFacts=[FATO, velho, longo, comercial]))
        r = self.gerar(f)
        txt = self.textos(r)
        self.assertIn("Capacidade de 5 litros", txt)
        self.assertNotIn("antigo", txt)
        self.assertNotIn("longa característica", txt.lower())
        self.assertNotIn("desconto", txt.lower())
        self.assertTrue(any("mais de 80" in a for a in r["avisos"]))
        self.assertTrue(any(o["tipo"] == "fato" for o in r["alegacoes_omitidas"]))
        self.assertTrue(any("fatos em revisão" in a for a in r["avisos"]))

    def test_limite_de_fatos_por_carrossel(self):
        fatos = [{**FATO, "text": f"Característica {i}"} for i in range(5)]
        r = self.gerar(self.ficha_a(a_com(1, verifiedFacts=fatos)))
        self.assertEqual(sum(1 for s in r["carrossel"]["slides"] if s.get("titulo") == "CARACTERÍSTICA"), cf.MAX_FATOS)


class CtaELinksTest(CarrosselBase):
    def test_ultimo_slide_e_cta_para_whatsapp_e_telegram_com_links_fornecidos(self):
        r = self.gerar(self.ficha_a(), links_oficiais=LINKS)
        ult = r["carrossel"]["slides"][-1]
        self.assertEqual((ult["layout"], ult["titulo"], ult["destaque"]), ("foto_topo", "CHAME NO", "WHATSAPP E TELEGRAM"))
        self.assertIn("wa.me/5511999999999", ult["texto"])
        self.assertIn("t.me/suzukiofertas_ficticio", ult["texto"])
        self.assertIn("https://wa.me/5511999999999", r["legenda_sugerida"])

    def test_sem_links_o_cta_existe_mas_nada_e_inventado(self):
        r = self.gerar(self.ficha_a())
        ult = r["carrossel"]["slides"][-1]
        self.assertEqual(ult["texto"], "Links oficiais na legenda.")
        self.assertNotIn("http", json.dumps(r["carrossel"]) + r["legenda_sugerida"])
        self.assertEqual(sum("link oficial" in a for a in r["avisos"]), 2)

    def test_links_fora_do_padrao_oficial_bloqueiam(self):
        for ruim in ("http://wa.me/1", "https://evil.example/1", "https://user:x@wa.me/1", "https://wa.me/", "https://wa.me/1?x=1",
                     "https://wa.me:8080/1", 5):
            r = self.gerar(self.ficha_a(), links_oficiais={"whatsapp": ruim})
            self.assertEqual((r["status"], r["bloqueios"][0]["codigo"]), ("bloqueado", "link_whatsapp_invalido"), repr(ruim))
        r = self.gerar(self.ficha_a(), links_oficiais={"telegram": "https://wa.me/1"})
        self.assertEqual(r["bloqueios"][0]["codigo"], "link_telegram_invalido")

    def test_identificacao_de_afiliado_so_quando_aplicavel(self):
        a = self.gerar(self.ficha_a())
        self.assertTrue(a["afiliado"])
        self.assertIn("Publicidade", a["carrossel"]["slides"][0]["texto"])
        self.assertIn("link de afiliado", a["legenda_sugerida"])
        b = self.gerar(self.ficha_b())
        self.assertFalse(b["afiliado"])
        self.assertNotIn("Publicidade", b["carrossel"]["slides"][0]["texto"])


class FormatoEDeterminismoTest(CarrosselBase):
    def completo(self):
        f = self.ficha_a(a_com(1, price__originalAmountCents=15000, verifiedFacts=[FATO]))
        return self.gerar(f, alegacoes=[PRECO, OFERTA], preco_aprovado_centavos=12990, links_oficiais=LINKS)

    def test_formato_do_gerador(self):
        from gerador.carrossel import CAMPOS_SLIDE
        from gerador.layouts import LAYOUTS
        r = self.completo()
        c = r["carrossel"]
        self.assertEqual(set(c), {"id", "permitir_fotos_pendentes", "slides"})
        self.assertRegex(c["id"], r"^[a-z0-9-]{1,60}$")
        self.assertTrue(1 <= len(c["slides"]) <= 10)
        for s in c["slides"]:
            self.assertLessEqual(set(s), CAMPOS_SLIDE)
            self.assertIn(s["layout"], LAYOUTS)
            self.assertIn(s["layout"], cf.LAYOUTS_EMITIDOS)
            self.assertTrue(len(s.get("titulo", "")) <= cf.LIM_TITULO and len(s.get("destaque", "")) <= cf.LIM_DESTAQUE and len(s.get("texto", "")) <= cf.LIM_TEXTO)
            self.assertTrue(isinstance(s["foco"], list) and len(s["foco"]) == 2)
            self.assertTrue(s.get("titulo") or s.get("destaque"))
        self.assertEqual(r["resolucao"], "1080x1350")

    def test_deterministico(self):
        a, b = json.dumps(self.completo(), sort_keys=True), json.dumps(self.completo(), sort_keys=True)
        self.assertEqual(a, b)

    def test_funcao_pura_nao_le_relogio_nem_grava_nem_usa_rede(self):
        fonte = (PACOTE / "carrossel_fragmento_v11.py").read_text(encoding="utf-8")
        for proibido in (".now(", "utcnow", "time.time", "time.sleep", "open(", ".write_", ".mkdir", "unlink", "socket", "subprocess",
                         "os.environ", "getenv", "urlopen", "import requests", "token", "senha", "vault", ".db\""):
            self.assertNotIn(proibido, fonte, proibido)
        for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", fonte, re.M):
            raiz = (m.group(1) or m.group(2)).split(".")[0].strip()
            self.assertTrue(raiz in __import__("sys").stdlib_module_names or raiz == "", raiz)

    def test_slides_demais_bloqueiam(self):
        fatos = [{**FATO, "text": f"Característica {i}"} for i in range(3)]
        f = self.ficha_a(a_com(1, verifiedFacts=fatos))
        alegs = [{"id": f"o{i}", "tipo": "oferta", "funcao": "acessoria", "texto": f"Seleção {i}"} for i in range(8)]
        r = self.gerar(f, alegacoes=alegs, preco_aprovado_centavos=12990)
        self.assertEqual(r["bloqueios"][0]["codigo"], "slides_demais")


class CompatibilidadeComGeradorTest(CarrosselBase):
    """Prova real: o JSON é aceito pelo carregador E pelo renderizador do gerador híbrido (1080×1350, validação do gerador)."""

    def setUp(self):
        super().setUp()
        from gerador.catalogo import Catalogo
        self.raiz_gerador = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.raiz_gerador, ignore_errors=True)
        self.catalogo = Catalogo(self.raiz_gerador)
        self.entrada = self.raiz_gerador / "entrada"
        self.entrada.mkdir()

    def foto(self, nome, semente, fmt="JPEG"):
        p = self.entrada / nome
        Image.effect_noise((900, 900), 60 + semente).convert("RGB").save(p, fmt, quality=90)
        return p

    def importar(self, nome, provedor, origem, semente):
        from gerador.importar import importar
        p = self.foto(nome, semente)
        fid, _ = importar(p, provedor=provedor, catalogo=self.catalogo, origem=origem, aprovado_por="Maria Revisora")
        return fid, hashlib.sha256(p.read_bytes()).hexdigest()

    def catalogo_dict(self):
        return self.catalogo.fotos

    def test_carregador_do_gerador_aceita_o_json(self):
        from gerador.carrossel import carregar
        r = self.gerar(self.ficha_a(), links_oficiais=LINKS)
        arq = self.tmp / "carrossel.json"
        arq.write_text(json.dumps(r["carrossel"], ensure_ascii=False), encoding="utf-8")
        dados = carregar(arq)
        self.assertEqual(dados["id"], r["carrossel"]["id"])

    def test_renderizacao_temporaria_1080x1350_com_ilustrativa(self):
        from gerador.carrossel import gerar
        fid, _ = self.importar("ilus.jpg", "nano-banana", "ia", 1)
        f = self.ficha_a(a_com(1, price__originalAmountCents=15000, verifiedFacts=[FATO]))
        r = ficha_para_carrossel_v11(f, t_publicacao=AGORA, foto_catalogo_id=fid, recurso_visual="ambientacao_ilustrativa",
                                     catalogo=self.catalogo_dict(), links_oficiais=LINKS, preco_aprovado_centavos=12990,
                                     alegacoes=[PRECO, {"id": "d", "tipo": "desconto", "funcao": "acessoria"}, OFERTA])
        self.assertEqual(r["status"], "rascunho", r["bloqueios"])
        man = gerar(r["carrossel"], catalogo=self.catalogo, saida=self.raiz_gerador / "saida")
        self.assertEqual((man["status"], man["resolucao"], man["problemas"]), ("pronto", "1080x1350", []))
        self.assertEqual(len(man["slides"]), len(r["carrossel"]["slides"]))
        for s in man["slides"]:
            self.assertEqual(s["validacao"], "ok")
            with Image.open(self.raiz_gerador / "saida" / s["arquivo"]) as im:
                self.assertEqual((im.size, im.format), ((1080, 1350), "JPEG"))

    def test_renderizacao_com_foto_real_autorizada_e_hash_conferido_de_ponta_a_ponta(self):
        from gerador.carrossel import gerar
        fid, sha = self.importar("real.jpg", "foto-real", "fotografia-real", 2)
        # registro humano de permissão com o hash real do arquivo importado
        (self.fotos / "fotos" / f"{sha}.jpg").write_bytes((self.entrada / "real.jpg").read_bytes())
        h = self.humanos(permissoes=[permissao(fotoSha256=sha)],
                         decisoes=[{"provider": "EXEMPLO_A", "productId": "A001", "exportId": uid(1), "decisao": "aprovado_para_rascunho",
                                    "autor": "Maria Revisora", "data": "2026-11-17T14:30:00Z", "motivo": "t"}])
        _, fs = self.rodar(a={"a.json": a_com(1)}, humanos=h)
        ficha = fs[CHAVE_A]
        self.assertTrue(ficha["foto"]["utilizavel"])
        r = ficha_para_carrossel_v11(ficha, t_publicacao=AGORA, foto_catalogo_id=fid, recurso_visual="foto_real_autorizada",
                                     catalogo=self.catalogo_dict(), links_oficiais=LINKS)
        self.assertEqual(r["status"], "rascunho", r["bloqueios"])
        man = gerar(r["carrossel"], catalogo=self.catalogo, saida=self.raiz_gerador / "saida_real")
        self.assertEqual((man["status"], man["problemas"]), ("pronto", []))
        self.assertTrue(all(s["foto"] == fid and s["status_foto"] == "aprovada" for s in man["slides"]))
        # foto trocada por outra com hash diferente => bloqueada ANTES do gerador
        fid2, _ = self.importar("outra.jpg", "foto-real", "fotografia-real", 3)
        r2 = ficha_para_carrossel_v11(ficha, t_publicacao=AGORA, foto_catalogo_id=fid2, recurso_visual="foto_real_autorizada",
                                      catalogo=self.catalogo_dict())
        self.assertEqual(r2["bloqueios"][0]["codigo"], "foto_hash_divergente")

    def test_pior_caso_de_texto_nos_layouts_emitidos_cabe_no_gerador(self):
        from gerador.carrossel import gerar
        fid, _ = self.importar("ilus.jpg", "nano-banana", "ia", 4)
        largo = lambda n: " ".join(("MW" * 6)[:min(8, n - i)] for i in range(0, n, 9))[:n]
        slides = []
        for i, layout in enumerate(cf.LAYOUTS_EMITIDOS):
            s = {"layout": layout, "foto": fid, "foco": [0.5, 0.45], "titulo": largo(cf.LIM_TITULO), "destaque": largo(cf.LIM_DESTAQUE),
                 "texto": ("palavramuitolonga " * 6)[:cf.LIM_TEXTO].strip()}
            if i:
                s["reutilizar"] = True
            slides.append(s)
        man = gerar({"id": "pior-caso", "permitir_fotos_pendentes": False, "slides": slides}, catalogo=self.catalogo,
                    saida=self.raiz_gerador / "saida_pior")
        self.assertEqual((man["status"], man["problemas"]), ("pronto", []))

    def test_foto_cheia_e_aceita_pelo_gerador_mas_nao_e_emitida_aqui(self):
        # o validador do gerador reprova combinações de texto em foto_cheia (exige >= 300 px de foto visível): por isso a ponte não a emite
        from gerador.layouts import LAYOUTS
        self.assertIn("foto_cheia", LAYOUTS)
        self.assertNotIn("foto_cheia", cf.LAYOUTS_EMITIDOS)

    def test_json_nao_altera_o_contrato_do_gerador(self):
        # o módulo do gerador não é importado por produtos/ em tempo de importação e não foi modificado por esta etapa
        for m in ("carrossel_fragmento_v11",):
            fonte = (PACOTE / f"{m}.py").read_text(encoding="utf-8")
            self.assertNotRegex(fonte, r"^(from|import)\s+gerador", "gerador não deve ser importado")


if __name__ == "__main__":
    unittest.main()
