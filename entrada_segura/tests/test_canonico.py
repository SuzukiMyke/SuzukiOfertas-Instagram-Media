import json
import unittest

from entrada_segura import canonico
from entrada_segura.erros import NaoCanonico


class CanonicoTest(unittest.TestCase):
    def test_ida_e_volta_deterministica(self):
        obj = {"b": [1, 2, {"z": None, "a": True}], "a": "açã", "n": -3}
        b = canonico.serializar(obj)
        self.assertEqual(b, b'{"a":"a\\u00e7\\u00e3","b":[1,2,{"a":true,"z":null}],"n":-3}')
        self.assertEqual(canonico.carregar_canonico(b), obj)
        self.assertEqual(canonico.serializar(canonico.carregar_canonico(b)), b)

    def test_recusas(self):
        casos = {
            "float": b'{"a":1.5}', "float_exp": b'{"a":1e3}', "nan": b'{"a":NaN}', "infinity": b'{"a":Infinity}',
            "chave_duplicada": b'{"a":1,"a":2}', "bom": b'\xef\xbb\xbf{"a":1}', "espaco": b'{"a": 1}', "quebra_final": b'{"a":1}\n',
            "ordem_diferente": b'{"b":1,"a":2}', "nao_ascii": '{"a":"é"}'.encode(), "invalido": b'{"a":', "vazio": b"", "bytes_aleatorios": b"\x00\xff\xfe\x01",
            "raiz_nao_objeto_com_espaco": b"[1, 2]", "escape_desnecessario": b'{"a":"\\u0041"}',
        }
        for nome, dados in casos.items():
            with self.assertRaises(NaoCanonico, msg=nome):
                canonico.carregar_canonico(dados)

    def test_profundidade_e_tamanho(self):
        ok = b"[" * 16 + b"]" * 16
        self.assertEqual(canonico.carregar_canonico(ok), json.loads(ok))
        for dados in (b"[" * 17 + b"]" * 17, b"[" * 100000 + b"]" * 100000):
            with self.assertRaises(NaoCanonico):
                canonico.carregar_canonico(dados)
        with self.assertRaises(NaoCanonico):
            canonico.carregar_canonico(b'{"a":"' + b"x" * 100 + b'"}', max_bytes=50)

    def test_serializar_recusa_tipos(self):
        for obj in ({"a": 1.0}, {"a": float("nan")}, {1: "x"}, {"a": {1, 2}}, {"a": b"x"}, [[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]):
            with self.assertRaises(NaoCanonico):
                canonico.serializar(obj)

    def test_string_com_colchetes_nao_conta_profundidade(self):
        dados = canonico.serializar({"a": "[" * 50})
        self.assertEqual(canonico.carregar_canonico(dados), {"a": "[" * 50})

    def test_entrada_hostil_nao_trava(self):
        for dados in (b"{" * 200000, b'{"a":' * 20000, bytes(range(256)) * 100):
            with self.assertRaises(NaoCanonico):
                canonico.carregar_canonico(dados)
