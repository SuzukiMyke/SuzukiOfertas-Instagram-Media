import unittest

from entrada_segura import hosts as hs


class HostsTest(unittest.TestCase):
    def a(self, u):
        return hs.analisar_url(u)

    def test_reservados_por_rotulos(self):
        for u in ("https://www.lojaficticia.example/p", "https://loja.example.com", "https://a.b.example.net/x", "https://example.org", "https://x.invalid",
                  "https://meu.test/", "HTTPS://LOJA.EXAMPLE.COM./Caminho", "https://Loja.Example.Com"):
            r = self.a(u)
            self.assertTrue(r.valido and r.reservado, u)
        self.assertEqual(self.a("HTTPS://LOJA.EXAMPLE.COM./x").host, "loja.example.com")

    def test_imitacoes_nao_sao_reservadas(self):
        for u in ("https://example.com.evil.com", "https://evilexample.com", "https://example.com.br", "https://exampleXcom.net", "https://example.co",
                  "https://notexample.com", "https://example.com.example.evil.io", "https://loja.com"):
            r = self.a(u)
            self.assertTrue(r.valido, u)
            self.assertFalse(r.reservado, u)

    def test_rotulo_unico_parecido_nao_e_reservado_nem_valido(self):
        r = self.a("https://exampleXcom")
        self.assertFalse(r.reservado)
        self.assertFalse(r.valido)

    def test_hosts_invalidos(self):
        casos = {"https://user@example.com": "userinfo", "https://user:senha@host.example": "userinfo", "https://127.0.0.1/": "ip_literal",
                 "https://10.0.0.1:443": "ip_literal", "https://[::1]/": "ip_literal", "https://[2001:db8::1]:443/": "ip_literal",
                 "https://localhost": "host_nao_reconhecivel", "https://example.com:8080": "porta", "https://example.com:0": "porta",
                 "https://xn--e1afmkfd.example": "punycode", "https://é.example": "nao_ascii", "https://":
                 "host_ausente", "https://a..example": "host_nao_reconhecivel", "https://intranet": "host_nao_reconhecivel", "https://-a.example": "rotulo_invalido",
                 "https://a b.example": "vazio_ou_controle", "https://a\x00.example": "vazio_ou_controle", "": "vazio_ou_controle", " https://a.example": "vazio_ou_controle"}
        for u, motivo in casos.items():
            r = self.a(u)
            self.assertFalse(r.valido, u)
            self.assertEqual(r.motivo_invalido, motivo, u)
            self.assertIsNone(r.host)

    def test_portas_80_e_443_ok(self):
        self.assertTrue(self.a("https://a.example:443/x").valido)
        self.assertTrue(self.a("http://a.example:80/x").valido)

    def test_esquemas_perigosos_e_nao_permitidos(self):
        for u in ("file:///etc/passwd", "data:text/html;base64,AAAA", "javascript:alert(1)", "mailto:a@b.example", "ftp://x.example/a", "FILE:///x"):
            self.assertEqual(self.a(u).motivo_invalido, "esquema_perigoso", u)
        for u in ("ws://a.example", "gopher://a.example"):
            self.assertEqual(self.a(u).motivo_invalido, "esquema_nao_permitido", u)

    def test_http_extrai_o_host_e_marca(self):
        r = self.a("http://cdn.loja.com/a.jpg")
        self.assertTrue(r.valido and r.http and not r.reservado)
        self.assertEqual(r.host, "cdn.loja.com")
        r = self.a("http://a.example/x")
        self.assertTrue(r.valido and r.http and r.reservado)
        self.assertFalse(self.a("https://a.example").http)
        self.assertTrue(self.a("http://user@a.example").http)             # inválido, mas o esquema http continua sinalizado

    def test_candidatos(self):
        sim = [("https://a.example", None), ("www.loja.com", None), ("loja.com.br/p", None), ("loja.com", "x"), ("qualquer coisa", "officialUrl"),
               ("x", "sourceRef"), ("x", "referencia"), ("x", "link"), ("x", "href"), ("x", "photoUrl"), ("javascript:alert(1)", None)]
        nao = [("manifest.json", None), ("termo.txt", None), ("1.0.0", None), ("Produto Fictício", None), ("", None), ("a_b.json", None), ("foto.JPG", None),
               ("v1.2", None), ("EXEMPLO_A", None)]
        for v, c in sim:
            self.assertTrue(hs.e_candidato_textual(v, c), (v, c))
        for v, c in nao:
            self.assertFalse(hs.e_candidato_textual(v, c), (v, c))

    def test_urls_em_texto(self):
        t = "veja https://a.example/x, e www.loja.com. Também http://b.example/y!"
        self.assertEqual(hs.urls_em_texto(t), ["https://a.example/x", "www.loja.com", "http://b.example/y"])
