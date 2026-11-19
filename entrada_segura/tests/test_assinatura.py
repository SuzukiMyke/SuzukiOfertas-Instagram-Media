import base64
import unittest
from unittest import mock

from entrada_segura import assinatura, canonico
from entrada_segura.assinatura import PREFIXO_ATESTADO, PREFIXO_REVOGACOES, verificar
from entrada_segura.erros import ErroAssinatura
from entrada_segura.tests.suporte_sintetico import ANCORA1, ANCORA2, ANCORAS_SINTETICAS, INTRUSO

DOC = canonico.serializar({"tipo": "teste", "valor": 1})

# RFC 8032 §7.1 (vetores oficiais; nunca ajustados)
V1 = ("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
      "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b", b"")
V2 = ("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
      "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00", bytes([0x72]))


def sig_json(chave_hex: str, assin_hex: str, **troca) -> bytes:
    d = {"algoritmo": "ed25519", "assinatura": base64.b64encode(bytes.fromhex(assin_hex)).decode(),
         "chavePublica": base64.b64encode(bytes.fromhex(chave_hex)).decode(), "schemaVersion": "1"}
    d.update(troca)
    return canonico.serializar(d)


class VetoresRFC8032(unittest.TestCase):
    """Os vetores oficiais exercitam a primitiva (prefixo vazio, mensagem do vetor) e provam que a biblioteca verifica Ed25519 de verdade."""

    def test_vetores_validos(self):
        for nome, (chave, assin, msg) in (("v1", V1), ("v2", V2)):
            fp = assinatura.fingerprint(bytes.fromhex(chave))
            r = verificar(b"", msg, sig_json(chave, assin), frozenset({fp}))
            self.assertEqual(r.fingerprint, fp, nome)

    def test_negativos_dos_vetores(self):
        chave, assin, msg = V1
        fp = frozenset({assinatura.fingerprint(bytes.fromhex(chave))})
        casos = {"mensagem_trocada": (b"x", chave, assin)}
        raw = bytearray(bytes.fromhex(assin)); raw[10] ^= 1
        casos["bit_na_assinatura"] = (msg, chave, bytes(raw).hex())
        for nome, (m, c, a) in casos.items():
            with self.assertRaises(ErroAssinatura, msg=nome) as cm:
                verificar(b"", m, sig_json(c, a), fp)
            self.assertEqual(cm.exception.codigo, "assinatura_invalida", nome)
        kb = bytearray(bytes.fromhex(chave)); kb[3] ^= 1
        with self.assertRaises(ErroAssinatura):
            verificar(b"", msg, sig_json(bytes(kb).hex(), assin), fp)


class Verificacao(unittest.TestCase):
    def ok(self, chave=ANCORA1, prefixo=PREFIXO_ATESTADO, doc=DOC):
        return chave.arquivo_assinatura(prefixo, doc)

    def test_valida_com_ancora(self):
        self.assertEqual(verificar(PREFIXO_ATESTADO, DOC, self.ok(), ANCORAS_SINTETICAS).fingerprint, ANCORA1.fingerprint)

    def erro(self, prefixo, doc, sig, ancoras=ANCORAS_SINTETICAS):
        with self.assertRaises(ErroAssinatura) as cm:
            verificar(prefixo, doc, sig, ancoras)
        return cm.exception.codigo

    def test_negativos(self):
        sig = self.ok()
        self.assertEqual(self.erro(PREFIXO_ATESTADO, DOC + b" ", sig), "assinatura_invalida")
        flip = bytearray(DOC); flip[2] ^= 1
        self.assertEqual(self.erro(PREFIXO_ATESTADO, bytes(flip), sig), "assinatura_invalida")
        self.assertEqual(self.erro(PREFIXO_ATESTADO, DOC, self.ok(INTRUSO)), "ancora_desconhecida")
        self.assertEqual(self.erro(PREFIXO_ATESTADO, DOC, sig, frozenset()), "ancora_desconhecida")        # âncora de produção vazia
        self.assertEqual(self.erro(PREFIXO_ATESTADO, DOC, self.ok(ANCORA2), frozenset({ANCORA1.fingerprint})), "ancora_desconhecida")

    def test_separacao_de_dominio(self):
        self.assertEqual(self.erro(PREFIXO_REVOGACOES, DOC, self.ok(prefixo=PREFIXO_ATESTADO)), "assinatura_invalida")
        self.assertEqual(self.erro(PREFIXO_ATESTADO, DOC, self.ok(prefixo=PREFIXO_REVOGACOES)), "assinatura_invalida")
        self.assertEqual(self.erro(b"SuzukiOfertas-Instagram/outro/v1\n", DOC, self.ok()), "assinatura_invalida")

    def test_arquivo_de_assinatura_malformado(self):
        base = ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC)
        b64 = lambda n: base64.b64encode(bytes(n)).decode()
        casos = {
            "assinatura_truncada": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, assinatura=b64(63)),
            "assinatura_estendida": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, assinatura=b64(65)),
            "chave_curta": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, chavePublica=b64(31)),
            "chave_longa": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, chavePublica=b64(33)),
            "algoritmo": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, algoritmo="rsa"),
            "versao": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, schemaVersion="2"),
            "campo_extra": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, extra="x"),
            "base64_com_espaco": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, assinatura=" " + b64(64)),
            "base64_invalido": ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, DOC, assinatura="***"),
            "nao_canonico": base.replace(b'{"', b'{ "', 1), "vazio": b"", "lixo": b"\x00\x01",
        }
        for nome, sig in casos.items():
            with self.assertRaises(ErroAssinatura, msg=nome):
                verificar(PREFIXO_ATESTADO, DOC, sig, ANCORAS_SINTETICAS)
        falta = canonico.serializar({k: v for k, v in canonico.carregar_canonico(base).items() if k != "assinatura"})
        with self.assertRaises(ErroAssinatura):
            verificar(PREFIXO_ATESTADO, DOC, falta, ANCORAS_SINTETICAS)

    def test_dependencia_ausente_simulada_e_recusa(self):
        with mock.patch.object(assinatura, "_importar_cripto", side_effect=ImportError("simulado")):
            self.assertEqual(self.erro(PREFIXO_ATESTADO, DOC, self.ok()), "dependencia_ausente")

    def test_chave_invalida_para_a_biblioteca(self):
        with mock.patch.object(assinatura, "_importar_cripto") as m:
            cls = mock.Mock(); cls.from_public_bytes.side_effect = ValueError("x")
            m.return_value = (cls, type("InvalidSignatureFalsa", (Exception,), {}))
            self.assertEqual(self.erro(PREFIXO_ATESTADO, DOC, self.ok()), "chave_invalida")


class Dependencia(unittest.TestCase):
    def test_dependencia_declarada_e_disponivel(self):
        """Nunca ignorado: se ``cryptography`` faltar, este teste FALHA (e os de assinatura também)."""
        import re
        from pathlib import Path
        import cryptography
        req = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(req), 1)
        m = re.fullmatch(r"cryptography>=(\d+(?:\.\d+)*)", req[0])
        self.assertIsNotNone(m, req)
        minimo = tuple(int(x) for x in m.group(1).split("."))
        atual = tuple(int(x) for x in re.match(r"\d+(?:\.\d+)*", cryptography.__version__).group(0).split("."))
        self.assertGreaterEqual(atual, minimo)
        Ed25519PublicKey, InvalidSignature = assinatura._importar_cripto()
        self.assertTrue(callable(Ed25519PublicKey.from_public_bytes))
        self.assertTrue(issubclass(InvalidSignature, Exception))
