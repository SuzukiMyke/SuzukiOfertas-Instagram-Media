"""Teste 10: ficha aprovada -> fragmento validado contra o formato REAL do gerador de Reels (sem executá-lo)."""
import copy
import unittest

from produtos import reel_fragmento as rf
from produtos.pipeline import processar
from produtos.tests.base import AGORA, Base, escrever, produto_a, produto_b, uid
import json

FOTO = "reels/assets/synthetic/s1_tecnologia.jpg"       # arquivo existente, apenas como caminho local de teste


class FragmentoTest(Base):
    def ficha(self, produto, aprovar=None, nome="a"):
        escrever(self.troca, nome + ".json", produto)
        dec = None
        if aprovar:
            dec = self.tmp / "decisoes.json"
            escrever(self.tmp, "decisoes.json", {"decisoes": [{
                "provider": produto["product"]["provider"], "productId": produto["product"]["id"],
                "exportId": produto["exportId"], "decisao": aprovar, "autor": "Revisor Exemplo",
                "data": "2026-11-17T14:00:00Z", "motivo": "conferido (fictício)"}]})
        processar(self.troca, self.saida, AGORA, decisoes_arquivo=dec)
        base = f"{produto['product']['provider']}__{produto['product']['id']}"
        return json.loads((self.saida / "fichas" / f"{base}.json").read_text(encoding="utf-8"))

    def test_fragmento_valido_contra_o_formato_real(self):
        f = self.ficha(produto_a(), aprovar="aprovado_para_rascunho")
        r = rf.ficha_para_fragmento(f, FOTO)
        erros, avisos = rf.validar_fragmento(r["fragmento"])
        self.assertEqual(erros, [], erros)
        cena = r["fragmento"]["scenes"][0]
        self.assertEqual(cena["source"]["kind"], "real_photo")
        self.assertEqual(cena["source"]["path"], FOTO)
        self.assertEqual(cena["source"]["catalog_id"], "produto:EXEMPLO_A:A001")
        self.assertIn("termo-ficticio-001", cena["source"]["license"])
        self.assertEqual(cena["title"], "Produto Fictício A001")

    def test_preco_fica_fora_do_video(self):
        f = self.ficha(produto_a(), aprovar="aprovado_para_rascunho")
        cena = rf.ficha_para_fragmento(f, FOTO)["fragmento"]["scenes"][0]
        for campo in ("price", "discount", "stock", "rating", "verified_at", "source_url"):
            self.assertNotIn(campo, cena)
        texto = json.dumps(cena, ensure_ascii=False)
        self.assertNotIn("129", texto)
        self.assertNotIn("R$", texto)
        self.assertIn("Preço fora do vídeo", rf.ficha_para_fragmento(f, FOTO)["legenda_aviso"])

    def test_aprovado_para_publicacao_tambem_gera_rascunho(self):
        f = self.ficha(produto_a(), aprovar="aprovado_para_publicacao")
        self.assertIn("scenes", rf.ficha_para_fragmento(f, FOTO)["fragmento"])

    def test_recusa_estados_sem_aprovacao_humana(self):
        casos = {
            "pendente_revisao": self.ficha(produto_a()),
            "expirado (B)": self.ficha(produto_b(), nome="b"),
        }
        for nome, f in casos.items():
            with self.assertRaises(rf.FragmentoRecusado, msg=nome):
                rf.ficha_para_fragmento(f, FOTO)

    def test_recusa_sem_foto_autorizada_nem_com_ia(self):
        f = self.ficha(produto_a(), aprovar="aprovado_para_rascunho")
        f = copy.deepcopy(f)
        f["foto"]["utilizavel"] = False
        with self.assertRaisesRegex(rf.FragmentoRecusado, "sem foto autorizada"):
            rf.ficha_para_fragmento(f, FOTO)

    def test_recusa_foto_local_ausente_ou_insegura(self):
        f = self.ficha(produto_a(), aprovar="aprovado_para_rascunho")
        for caminho in (None, "", "/etc/passwd", "../fora.jpg", "photos/nao_existe.jpg", "reels/../reels/x.jpg"):
            with self.assertRaises(rf.FragmentoRecusado, msg=str(caminho)):
                rf.ficha_para_fragmento(f, caminho)

    def test_avisos_de_titulo_longo_e_categoria_ausente(self):
        d = produto_a(product__title="Produto fictício com um nome muito longo que passa de sessenta caracteres",
                      product__category=None, product__categoryOrigin=None)
        f = self.ficha(d, aprovar="aprovado_para_rascunho")
        r = rf.ficha_para_fragmento(f, FOTO)
        self.assertEqual(len(r["avisos"]), 2)
        self.assertEqual(r["fragmento"]["scenes"][0]["category"], rf.CATEGORIA_NEUTRA)
        self.assertEqual(rf.validar_fragmento(r["fragmento"])[0], [])

    def test_politica_de_conteudo_do_gerador_e_aplicada(self):
        d = produto_a(product__title="Oferta imperdível de produto fictício")
        f = self.ficha(d, aprovar="aprovado_para_rascunho")
        erros, _ = rf.validar_fragmento(rf.ficha_para_fragmento(f, FOTO)["fragmento"])
        self.assertTrue(any("termo proibido" in e for e in erros), erros)

    def test_validador_real_rejeita_fragmento_fora_do_formato(self):
        f = self.ficha(produto_a(), aprovar="aprovado_para_rascunho")
        frag = copy.deepcopy(rf.ficha_para_fragmento(f, FOTO)["fragmento"])
        frag["scenes"][0]["campo_inventado"] = 1
        erros, _ = rf.validar_fragmento(frag)
        self.assertTrue(any("chave desconhecida" in e for e in erros), erros)

    def test_nao_altera_a_config_base_nem_o_gerador(self):
        import hashlib
        from pathlib import Path
        arquivos = [rf.RAIZ_REPO / "reels" / "configs" / "pilot_demo_01.json",
                    rf.RAIZ_REPO / "reels" / "reel_gen" / "config.py", rf.RAIZ_REPO / "reels" / "reel_gen" / "pipeline.py"]
        antes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in arquivos]
        f = self.ficha(produto_a(), aprovar="aprovado_para_rascunho")
        rf.validar_fragmento(rf.ficha_para_fragmento(f, FOTO)["fragmento"])
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest() for p in arquivos], antes)


if __name__ == "__main__":
    unittest.main()
