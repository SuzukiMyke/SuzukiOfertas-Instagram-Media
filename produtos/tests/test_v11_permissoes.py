"""Modo 1.1: permissões de foto só por registro humano com hash; evidência por programa; nada é gravado (§8, §10)."""
import hashlib
import unittest

from produtos import permissoes as pm
from produtos.tests.base_v11 import (EVIDENCIA_SHA, FOTO_BYTES, FOTO_SHA, BaseV11, instantaneo, permissao, termo)


class PermissoesTest(BaseV11):
    def avaliar(self, termos=None, permissoes=None, fotos_dir="padrao", url=None, pid="A001"):
        h = self.humanos(termos=termos, permissoes=permissoes)
        reg = pm.carregar(h["termos_arquivo"], h["permissoes_arquivo"])
        return pm.avaliar_foto("EXEMPLO_A", pid, reg, self.fotos if fotos_dir == "padrao" else fotos_dir, url), reg

    def test_caminho_feliz(self):
        r, _ = self.avaliar()
        self.assertTrue(r["utilizavel"], r)
        self.assertEqual((r["fotoSha256"], r["termoId"]), (FOTO_SHA, "T1"))

    def test_sem_registro_ou_sem_repositorio_de_fotos(self):
        self.assertFalse(self.avaliar(permissoes=[])[0]["utilizavel"])
        r, _ = self.avaliar(fotos_dir=None)
        self.assertFalse(r["utilizavel"])
        self.assertIn("não informado", r["motivo"])

    def test_negada_posterior_revoga_confirmada(self):
        perms = [permissao(data="2026-11-17T14:00:00Z"), permissao(status="negada", data="2026-11-17T16:00:00Z")]
        r, _ = self.avaliar(permissoes=perms)
        self.assertFalse(r["utilizavel"])
        self.assertIn("NEGADA", r["motivo"])

    def test_termo_inexistente_e_escopo_errado(self):
        self.assertIn("inexistente", self.avaliar(termos=[])[0]["motivo"])
        self.assertIn("escopo", self.avaliar(termos=[termo(escopo="provider:OUTRO")])[0]["motivo"])

    def test_evidencia_nao_pode_ser_a_url_da_foto_do_agente(self):
        url = "https://programa.ficticio.example/termos"
        r, _ = self.avaliar(url=url)
        self.assertFalse(r["utilizavel"])
        self.assertIn("URL da foto exportada", r["motivo"])

    def test_hash_divergente_ou_arquivo_renomeado(self):
        # conteúdo alterado sob o mesmo nome
        (self.fotos / "fotos" / f"{FOTO_SHA}.jpg").write_bytes(FOTO_BYTES + b"x")
        r, _ = self.avaliar()
        self.assertFalse(r["utilizavel"])
        self.assertIn("diverge", r["motivo"])
        # registro aponta para um hash cujo arquivo não existe (renomear não vale)
        r2, _ = self.avaliar(permissoes=[permissao(fotoSha256="a" * 64)])
        self.assertIn("ausente", r2["motivo"])

    def test_arquivo_grande_ou_tipo_invalido(self):
        grande = b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024)
        sha = hashlib.sha256(grande).hexdigest()
        (self.fotos / "fotos" / f"{sha}.jpg").write_bytes(grande)
        self.assertIn("2 MB", self.avaliar(permissoes=[permissao(fotoSha256=sha)])[0]["motivo"])
        exe = b"MZ" + b"1" * 50
        sha2 = hashlib.sha256(exe).hexdigest()
        (self.fotos / "fotos" / f"{sha2}.jpg").write_bytes(exe)
        self.assertIn("tipo inválido", self.avaliar(permissoes=[permissao(fotoSha256=sha2)])[0]["motivo"])

    def test_evidencia_ausente_ou_adulterada_ou_com_caminho_perigoso(self):
        (self.fotos / "evidencias" / "termo.txt").write_bytes(b"adulterado")
        self.assertIn("evidenciaSha256", self.avaliar()[0]["motivo"])
        (self.fotos / "evidencias" / "termo.txt").unlink()
        self.assertIn("ausente", self.avaliar()[0]["motivo"])
        self.assertIn("inválido", self.avaliar(termos=[termo(arquivoEvidencia="../fotos/x.jpg")])[0]["motivo"])

    def test_foto_simbolica_e_recusada(self):
        p = self.fotos / "fotos" / f"{FOTO_SHA}.jpg"
        p.unlink()
        alvo = self.tmp / "fora.jpg"
        alvo.write_bytes(FOTO_BYTES)
        p.symlink_to(alvo)
        self.assertFalse(self.avaliar()[0]["utilizavel"])

    def test_autor_de_automacao_e_registro_invalido_sao_ignorados(self):
        r, reg = self.avaliar(permissoes=[permissao(autor="Claude"), permissao(autor="bot de testes"),
                                          permissao(extra="x"), permissao(fotoSha256="curto"), permissao(status="talvez")])
        self.assertFalse(r["utilizavel"])
        self.assertEqual(len(reg.avisos), 5)
        _, reg2 = self.avaliar(termos=[termo(autor="sistema"), termo(tipoEvidencia="inventado")])
        self.assertEqual(reg2.termos, {})

    def test_schema_version_errado_ou_json_invalido_nao_concede_nada(self):
        self.humanos()
        (self.hum / "permissoes_fotos.json").write_text('{"schemaVersion": "2.0", "permissoes": []}')
        (self.hum / "termos_programas.json").write_text("{quebrado")
        reg = pm.carregar(self.hum / "termos_programas.json", self.hum / "permissoes_fotos.json")
        self.assertEqual((reg.termos, reg.permissoes, len(reg.avisos)), ({}, {}, 2))

    def test_arquivo_humano_ausente_nao_concede_nada(self):
        reg = pm.carregar(self.tmp / "nao_existe.json", self.tmp / "nem_este.json")
        self.assertEqual((reg.permissoes, len(reg.avisos)), ({}, 2))

    def test_leitura_nunca_grava(self):
        self.humanos()
        antes = instantaneo(self.tmp)
        reg = pm.carregar(self.hum / "termos_programas.json", self.hum / "permissoes_fotos.json")
        pm.avaliar_foto("EXEMPLO_A", "A001", reg, self.fotos)
        self.assertEqual(instantaneo(self.tmp), antes)

    def test_politica_de_arquivo_de_foto(self):
        self.assertIsNone(pm.validar_arquivo_foto(FOTO_BYTES))
        self.assertIsNone(pm.validar_arquivo_foto(b"\x89PNG\r\n\x1a\n" + b"0"))
        self.assertIsNone(pm.validar_arquivo_foto(b"RIFF\0\0\0\0WEBPxx"))
        self.assertIn("2 MB", pm.validar_arquivo_foto(b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024)))
        self.assertIn("tipo", pm.validar_arquivo_foto(b"GIF89a"))
        self.assertEqual(pm.sha256_bytes(b""), hashlib.sha256(b"").hexdigest())
        self.assertEqual(EVIDENCIA_SHA, hashlib.sha256("termo fictício de teste\n".encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
