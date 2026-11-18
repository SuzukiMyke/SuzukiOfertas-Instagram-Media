"""B2R, commit 2: quatro layouts novos e ilustrações por categoria (sem rede, em catálogo temporário)."""
import hashlib
import io
import re
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from gerador import fundo_marca as fm
from gerador import identidade as idv
from gerador import layouts as L
from gerador.carrossel import gerar
from gerador.catalogo import Catalogo
from gerador.validacao import DESVIO_MINIMO_FOTO, maior_area_vazia, validar_slide, validar_slide_v2
from orquestrador_b2 import ilustracoes as il
from produtos.tests.base import Base

RAIZ = Path(__file__).resolve().parents[1]
NOVOS = ("ilustracao_capa", "destaque_numerico", "lista_caracteristicas", "cta_seguir")
CATALOGO_REPO = RAIZ / "photos" / "catalogo.json"
CASOS = {
    "ilustracao_capa": [{"titulo": "FONE SEM FIO", "destaque": "FICTÍCIO", "texto": "Loja Fictícia"},
                        {"titulo": "FURADEIRA", "destaque": "FICTÍCIA 20 V", "texto": "Loja Fictícia"}],
    "destaque_numerico": [{"titulo": "CAPACIDADE", "destaque": "5 L", "texto": "Capacidade de 5 litros"},
                          {"titulo": "AUTONOMIA", "destaque": "20 h", "texto": "Autonomia de até 20 horas com o estojo de recarga"},
                          {"titulo": "PESO", "destaque": "1,2 kg", "texto": "Peso de 1,2 kg"},
                          {"titulo": "NA PRÁTICA", "texto": "Corpo em alumínio resistente"}],
    "lista_caracteristicas": [{"titulo": "NA PRÁTICA", "texto": "Capacidade de 5 litros\nCorpo em alumínio"},
                              {"titulo": "NA PRÁTICA", "texto": "Capacidade de 5 litros\nCorpo em alumínio\nTampa com trava de segurança"}],
    "cta_seguir": [{"titulo": "ACHADOS TODO DIA NO SEU CELULAR", "texto": "Siga o Suzuki Ofertas no WhatsApp e no Telegram.\n"
                                                                       "Ative as notificações e compartilhe com quem gosta de ofertas."},
                   {"titulo": "ACHADOS TODO DIA NO SEU CELULAR", "destaque": "wa.me/5511999999999 · t.me/suzukiofertas_ficticio",
                    "texto": "Siga o Suzuki Ofertas no WhatsApp e no Telegram.\nAtive as notificações e compartilhe com quem gosta de ofertas."}],
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Tela(Base):
    def setUp(self):
        super().setUp()
        self.fundo = fm.gerar_fundo(1, marca=False)
        self.ilus = il.desenhar("casa_cozinha")

    def foto(self, nome):
        return self.ilus if nome == "ilustracao_capa" else self.fundo

    def render(self, nome, s, n=2, total=4):
        sl = {"layout": nome, **s}
        img, areas = L.LAYOUTS[nome](self.foto(nome), sl, n, total)
        with L.sem_texto():
            img0, _ = L.LAYOUTS[nome](self.foto(nome), sl, n, total)
        arq = self.tmp / f"{nome}_{abs(hash(str(s))) % 10 ** 6}.jpg"
        img.convert("RGB").save(arq, "JPEG", quality=92)
        return img, areas, arq, img0


class LayoutsNovosTest(Tela):
    def test_registrados_e_os_antigos_continuam(self):
        for nome in ("foto_topo", "foto_cheia", "cartao") + NOVOS:
            self.assertIn(nome, L.LAYOUTS)
        self.assertEqual(set(L.LAYOUTS_B2R), set(NOVOS))

    def test_resolucao_e_assinatura(self):
        for nome in NOVOS:
            for s in CASOS[nome]:
                img, areas, arq, _ = self.render(nome, s)
                self.assertEqual(img.size, (1080, 1350), nome)
                for k in ("foto_livre", "texto", "texto_total", "logo", "v2"):
                    self.assertIn(k, areas)

    def test_validacao_antiga_do_gerador_aprova_os_novos_layouts(self):
        for nome in NOVOS:
            for s in CASOS[nome]:
                _, areas, arq, _ = self.render(nome, s)
                self.assertEqual(validar_slide(arq, areas), [], (nome, s))

    def test_validacao_b2r_aprova_texto_curto_medio_e_longo(self):
        for nome in NOVOS:
            for s in CASOS[nome]:
                _, areas, arq, img0 = self.render(nome, s)
                v = validar_slide_v2(arq, areas, fundo_sem_texto=img0)
                self.assertTrue(v["ok"], (nome, s, v["erros"]))
                m = v["medidas"]
                self.assertGreaterEqual(m["contraste_min"], 4.5, (nome, m["contraste_por_bloco"]))

    def test_tamanhos_minimos_de_fonte(self):
        minimos = {"titulo": 72, "texto": 44, "rotulo": 36, "contador": 36}
        for nome in NOVOS:
            for s in CASOS[nome]:
                _, areas, *_ = self.render(nome, s)
                vistos = {}
                for it in areas["v2"]["itens"]:
                    vistos[it["tipo"]] = min(vistos.get(it["tipo"], 999), it["tamanho"])
                for tipo, minimo in minimos.items():
                    if tipo in vistos:
                        self.assertGreaterEqual(vistos[tipo], minimo, (nome, tipo))
                self.assertIn("rotulo", vistos)
                self.assertGreaterEqual(vistos["contador"], 38)                           # contador do rodapé grande

    def test_nada_fora_da_area_segura_e_logo_inteiro_de_160px(self):
        for nome in NOVOS:
            for s in CASOS[nome]:
                _, areas, *_ = self.render(nome, s)
                v2 = areas["v2"]
                m = v2["margem"]
                for it in v2["itens"]:
                    c = it["caixa"]
                    self.assertTrue(c[0] + 4 >= m and c[1] + 4 >= m and c[2] - 4 <= 1080 - m and c[3] - 4 <= 1350 - m, (nome, it["tipo"], c))
                x0, y0, x1, y1 = v2["logo"]
                self.assertEqual((x1 - x0, y1 - y0), (160, 160))
                self.assertTrue(x0 >= m and y0 >= m and x1 <= 1080 - m and y1 <= 1350 - m)

    def test_logo_inteiro_sem_cortes_nos_pixels(self):
        img, areas, *_ = self.render("destaque_numerico", CASOS["destaque_numerico"][0])
        x0, y0, x1, y1 = areas["v2"]["logo"]
        with L.sem_texto():
            img0, _ = L.LAYOUTS["destaque_numerico"](self.fundo, {"layout": "destaque_numerico", **CASOS["destaque_numerico"][0]}, 2, 4)
        esperado = img0.crop((x0, y0, x1, y1)).copy()
        esperado.alpha_composite(Image.new("RGBA", (1, 1)), (0, 0))
        self.assertEqual(img.crop((x0, y0, x1, y1)).tobytes(), img0.crop((x0, y0, x1, y1)).tobytes())     # o logo é idêntico com e sem texto
        self.assertGreater(ImageStat.Stat(img.crop((x0, y0, x1, y1)).convert("L")).stddev[0], 20)             # e não é um bloco liso

    def test_sem_texto_nao_muda_a_geometria(self):
        for nome in NOVOS:
            img, areas, _, img0 = self.render(nome, CASOS[nome][0])
            self.assertIsNotNone(ImageChops.difference(img.convert("RGB"), img0.convert("RGB")).getbbox())
            _, areas0 = L.LAYOUTS[nome](self.foto(nome), {"layout": nome, **CASOS[nome][0]}, 2, 4)
            self.assertEqual([i["caixa"] for i in areas["v2"]["itens"]], [i["caixa"] for i in areas0["v2"]["itens"]])

    def test_texto_sem_truncamento_e_sem_reticencias(self):
        for nome in NOVOS:
            for s in CASOS[nome]:
                _, areas, *_ = self.render(nome, s)
                desenhado = " ".join(i["texto"] for i in areas["v2"]["itens"])
                self.assertNotIn("…", desenhado)
                self.assertNotIn("...", desenhado)
                for campo in ("titulo", "destaque", "texto"):
                    for palavra in re.split(r"\s+", (s.get(campo) or "").strip()):
                        if palavra:
                            self.assertIn(palavra, desenhado, (nome, campo, palavra))

    def test_area_decorativa_dentro_do_limite(self):
        for nome in NOVOS:
            for s in CASOS[nome]:
                _, areas, *_ = self.render(nome, s)
                r = maior_area_vazia(areas["v2"]["conteudo"], 1080, 1350, 72)
                self.assertLessEqual(r["fracao"], 0.25, (nome, r))

    def test_conteudo_que_nao_cabe_nao_e_reduzido_nem_truncado(self):
        muito = "ACESSÓRIO ELÉTRICO PORTÁTIL PROFISSIONAL MULTIFUNÇÃO RECARREGÁVEL"
        casos = [("ilustracao_capa", {"titulo": muito, "destaque": "EXTRA GRANDE", "texto": "Loja Fictícia"}),
                 ("destaque_numerico", {"titulo": muito, "destaque": "5 L", "texto": "texto " * 60}),
                 ("lista_caracteristicas", {"titulo": "NA PRÁTICA", "texto": "um item\ndois itens\ntrês itens\nquatro itens"}),
                 ("lista_caracteristicas", {"titulo": "NA PRÁTICA", "texto": "apenas um item"}),
                 ("lista_caracteristicas", {"titulo": "NA PRÁTICA", "texto": ("item muito longo " * 12 + "\n") * 3}),
                 ("cta_seguir", {"titulo": "ACHADOS TODO DIA NO SEU CELULAR " * 3, "texto": "corpo\ncomplemento"}),
                 ("ilustracao_capa", {"titulo": "", "destaque": "", "texto": "Loja"}),
                 ("destaque_numerico", {"titulo": "PALAVRAMUITOMUITOLONGAQUENAOCABENALINHADOTITULOAAAAA", "destaque": "5 L", "texto": "x"}),
                 # cabe em 2 linhas só com fonte < 72 px: não pode ser reduzido abaixo do mínimo
                 ("destaque_numerico", {"titulo": "ACESSÓRIO ELÉTRICO PORTÁTIL RECARREGÁVEL", "destaque": "5 L", "texto": "x"}),
                 ("lista_caracteristicas", {"titulo": "ACESSÓRIO ELÉTRICO PORTÁTIL RECARREGÁVEL", "texto": "um\ndois"}),
                 ("ilustracao_capa", {"titulo": "ACESSÓRIO ELÉTRICO PORTÁTIL", "destaque": "RECARREGÁVEL USB", "texto": "Loja Fictícia"}),
                 ("cta_seguir", {"titulo": "ACESSÓRIO ELÉTRICO PORTÁTIL RECARREGÁVEL", "texto": "corpo\ncomplemento"})]
        for nome, s in casos:
            with self.assertRaises(L.ErroTextoNaoCabe, msg=(nome, s)):
                L.LAYOUTS[nome](self.foto(nome), {"layout": nome, **s}, 1, 4)

    def test_destaque_sem_numero_e_lista_funcionam_com_fonte_grande(self):
        _, areas, arq, img0 = self.render("destaque_numerico", {"titulo": "NA PRÁTICA", "texto": "Corpo em alumínio resistente"})
        self.assertGreaterEqual(min(i["tamanho"] for i in areas["v2"]["itens"] if i["tipo"] == "titulo"), 72)
        self.assertTrue(validar_slide_v2(arq, areas, fundo_sem_texto=img0)["ok"])

    def test_cta_tem_dois_botoes_nomeados_e_nenhum_link_inventado(self):
        _, areas, *_ = self.render("cta_seguir", CASOS["cta_seguir"][0])
        botoes = [i["texto"] for i in areas["v2"]["itens"] if i["tipo"] == "botao"]
        self.assertEqual(botoes, ["WhatsApp", "Telegram"])
        todo = " ".join(i["texto"] for i in areas["v2"]["itens"]).lower()
        self.assertNotIn("http", todo)
        self.assertNotIn("link", todo)
        self.assertNotIn("bio", todo)

    def test_rotulo_arte_ilustrativa_em_todos(self):
        for nome in NOVOS:
            _, areas, *_ = self.render(nome, CASOS[nome][0])
            self.assertTrue(any(i["tipo"] == "rotulo" and i["texto"] == "Arte ilustrativa" for i in areas["v2"]["itens"]), nome)

    def test_numero_e_unidade_grandes_no_destaque(self):
        _, areas, *_ = self.render("destaque_numerico", CASOS["destaque_numerico"][0])
        grandes = [i for i in areas["v2"]["itens"] if i["tipo"] == "destaque"]
        self.assertEqual([i["texto"] for i in grandes], ["5", "L"])
        self.assertGreaterEqual(grandes[0]["tamanho"], 160)

    def test_validador_b2r_reprova_o_que_deve_reprovar(self):
        img, areas, arq, img0 = self.render("lista_caracteristicas", CASOS["lista_caracteristicas"][0])
        ruim = {**areas, "v2": {**areas["v2"], "itens": [{**areas["v2"]["itens"][0], "tamanho": 30}] + areas["v2"]["itens"][1:]}}
        self.assertTrue(any("fonte de 30px" in e for e in validar_slide_v2(arq, ruim, fundo_sem_texto=img0)["erros"]))
        fora = {**areas, "v2": {**areas["v2"], "itens": [{**areas["v2"]["itens"][0], "caixa": (10, 10, 300, 90)}] + areas["v2"]["itens"][1:]}}
        self.assertTrue(any("fora da margem" in e for e in validar_slide_v2(arq, fora, fundo_sem_texto=img0)["erros"]))
        claro = Image.new("RGB", (1080, 1350), (235, 235, 235))                                      # fundo claro sob texto branco
        self.assertTrue(any("contraste" in e for e in validar_slide_v2(arq, areas, fundo_sem_texto=claro)["erros"]))
        vazio = {**areas, "v2": {**areas["v2"], "conteudo": []}}
        self.assertTrue(any("área decorativa" in e for e in validar_slide_v2(arq, vazio, fundo_sem_texto=img0)["erros"]))
        cortado = {**areas, "v2": {**areas["v2"], "logo": (1000, 1250, 1160, 1410)}}
        self.assertTrue(any("logotipo" in e for e in validar_slide_v2(arq, cortado, fundo_sem_texto=img0)["erros"]))


class IlustracoesTest(Base):
    def test_seis_categorias_e_tamanho(self):
        self.assertEqual(il.CATEGORIAS, ("tecnologia", "casa_cozinha", "ferramentas", "moda_beleza", "utilidades", "generica"))
        for c in il.CATEGORIAS:
            im = il.desenhar(c)
            self.assertEqual((im.size, im.mode), ((1080, 776), "RGB"))

    def test_determinismo_das_seis_categorias(self):
        for c in il.CATEGORIAS:
            for v in (0, 3):
                self.assertEqual(il.ilustracao_bytes(c, v), il.ilustracao_bytes(c, v), (c, v))
                self.assertEqual(sha(il.ilustracao_bytes(c, v)), il.sha256_ilustracao(c, v))

    def test_categoria_desconhecida_usa_generica(self):
        for ruim in ("brinquedos", None, "", 5, "TECNOLOGIA"):
            self.assertEqual(il.normalizar_categoria(ruim), "generica")
            self.assertEqual(il.ilustracao_bytes(ruim), il.ilustracao_bytes("generica"))

    def test_categorias_visualmente_distintas(self):
        mini = {c: il.desenhar(c).resize((72, 52)) for c in il.CATEGORIAS}
        for a in il.CATEGORIAS:
            for b in il.CATEGORIAS:
                if a < b:
                    dif = ImageStat.Stat(ImageChops.difference(mini[a], mini[b])).mean
                    self.assertGreater(sum(dif) / 3, 12, (a, b))
                    self.assertNotEqual(il.sha256_ilustracao(a), il.sha256_ilustracao(b))
        self.assertEqual(len({il.sha256_ilustracao("tecnologia", v) for v in range(il.VARIANTES)}), il.VARIANTES)

    def test_cores_da_marca_e_riqueza_visual(self):
        for c in il.CATEGORIAS:
            im = il.desenhar(c)
            dados = im.tobytes()
            amar = sum(1 for i in range(0, len(dados), 3) if abs(dados[i] - 254) < 30 and abs(dados[i + 1] - 198) < 30 and dados[i + 2] < 90)
            self.assertGreater(amar, 3000, c)                                                         # amarelo da marca presente
            self.assertGreater(ImageStat.Stat(im.convert("L")).stddev[0], DESVIO_MINIMO_FOTO + 10, c)  # nada de área lisa

    def test_sem_texto_fotos_ou_marcas(self):
        fonte = (RAIZ / "orquestrador_b2" / "ilustracoes.py").read_text(encoding="utf-8")
        codigo = re.sub(r'^""".*?"""', "", fonte, count=1, flags=re.S)
        for proibido in (".text(", "ImageFont", "idv.fonte(", "Image.open(", "urllib", "socket", "requests", "subprocess"):
            self.assertNotIn(proibido, codigo, proibido)

    def test_categoria_de_ficha(self):
        casos = {("Tecnologia > Fones de Ouvido", None): "tecnologia", ("Casa e Cozinha > Panelas", None): "casa_cozinha",
                 ("Ferramentas > Elétricas", None): "ferramentas", ("Moda e Beleza > Vestuário", None): "moda_beleza",
                 ("Utilidades > Iluminação", None): "utilidades", ("Brinquedos", "Carrinho"): "generica", (None, None): "generica",
                 (None, "Furadeira sem fio fictícia"): "ferramentas"}
        for (cat, tit), esperado in casos.items():
            self.assertEqual(il.categoria_de(cat, tit), esperado, (cat, tit))

    def test_registro_pendente_no_catalogo_temporario(self):
        antes = hashlib.sha256(CATALOGO_REPO.read_bytes()).hexdigest()
        cat = Catalogo(self.tmp / "cat")
        fid, nova = il.registrar_ilustracao(cat, "ferramentas", agora="2026-11-17T15:00:00Z")
        self.assertEqual((fid, nova), ("cg-0001", True))
        m = cat.obter(fid)
        self.assertEqual((m["provedor"], m["origem"], m["aprovacao"]["status"], m["largura"], m["altura"]),
                         ("composicao-grafica", "composicao-grafica", "pendente", 1080, 776))
        self.assertEqual(m["gerador"]["categoria"], "ferramentas")
        self.assertEqual(sha((self.tmp / "cat" / m["caminho_github"]).read_bytes()), m["sha256"])
        self.assertEqual(il.registrar_ilustracao(cat, "ferramentas"), ("cg-0001", False))
        self.assertEqual(il.registrar_ilustracao(cat, "generica")[0], "cg-0002")
        self.assertEqual(hashlib.sha256(CATALOGO_REPO.read_bytes()).hexdigest(), antes)


class IntegracaoComOGeradorTest(Base):
    def test_gerar_renderiza_os_quatro_layouts_novos_e_o_status_e_pronto(self):
        cat = Catalogo(self.tmp / "cat")
        ilus, _ = il.registrar_ilustracao(cat, "tecnologia", agora="2026-11-17T15:00:00Z")
        fundos = [fm.registrar(cat, v, agora="2026-11-17T15:00:00Z", marca=False)[0] for v in (2, 5, 8)]
        for fid in [ilus] + fundos:
            cat.definir_aprovacao(fid, "aprovada", "TESTE", "aprovação de teste")                      # catálogo TEMPORÁRIO
        slides = [{"layout": "ilustracao_capa", "foto": ilus, **CASOS["ilustracao_capa"][0]},
                  {"layout": "destaque_numerico", "foto": fundos[0], **CASOS["destaque_numerico"][0]},
                  {"layout": "lista_caracteristicas", "foto": fundos[1], **CASOS["lista_caracteristicas"][1]},
                  {"layout": "cta_seguir", "foto": fundos[2], **CASOS["cta_seguir"][0]}]
        man = gerar({"id": "teste-b2r", "permitir_fotos_pendentes": False, "slides": slides}, catalogo=cat, saida=self.tmp / "saida")
        self.assertEqual((man["status"], man["problemas"]), ("pronto", []))
        for s in man["slides"]:
            self.assertEqual(s["validacao"], "ok")
            with Image.open(self.tmp / "saida" / s["arquivo"]) as im:
                self.assertEqual((im.size, im.format), ((1080, 1350), "JPEG"))

    def test_imagem_pendente_continua_bloqueada_pelo_gerador(self):
        from gerador.selecao import ErroSelecao
        cat = Catalogo(self.tmp / "cat")
        fid, _ = il.registrar_ilustracao(cat, "generica")
        with self.assertRaises(ErroSelecao):
            gerar({"id": "x", "permitir_fotos_pendentes": False,
                   "slides": [{"layout": "ilustracao_capa", "foto": fid, **CASOS["ilustracao_capa"][0]}]}, catalogo=cat, saida=self.tmp / "s")

    def test_campos_do_slide_aceitos_pelo_carregador(self):
        import json
        from gerador.carrossel import carregar
        arq = self.tmp / "c.json"
        arq.write_text(json.dumps({"id": "c", "permitir_fotos_pendentes": False, "slides": [
            {"layout": n, "foto": "cg-0001", "foco": [0.5, 0.45], "titulo": "X", "destaque": "Y", "texto": "Z", **({"reutilizar": True} if i else {})}
            for i, n in enumerate(NOVOS)]}), encoding="utf-8")
        self.assertEqual(len(carregar(arq)["slides"]), 4)


if __name__ == "__main__":
    unittest.main()
