"""Garantias estáticas e dinâmicas: sem rede, sem agente, sem bancos/cofre/credenciais."""
import re
import socket
import unittest
from pathlib import Path

from produtos.pipeline import processar
from produtos.tests.base import AGORA, EXEMPLOS, Base

PACOTE = Path(__file__).resolve().parents[1]
FONTES = [p for p in PACOTE.glob("*.py")]

IMPORTS_PROIBIDOS = ("urllib.request", "urllib3", "http.client", "http.server", "socket", "requests", "httpx",
                     "aiohttp", "ftplib", "smtplib", "telnetlib", "xmlrpc", "subprocess", "sqlite3", "ssl",
                     "webbrowser", "shutil")


class SemRedeTest(Base):
    def test_a_trava_de_rede_dos_testes_funciona(self):
        with self.assertRaises(AssertionError):
            socket.create_connection(("exemplo.example", 443))
        with self.assertRaises(AssertionError):
            socket.getaddrinfo("exemplo.example", 443)
        with self.assertRaises(AssertionError):
            with socket.socket() as s:
                s.connect(("127.0.0.1", 9))

    def test_pipeline_completo_roda_com_rede_bloqueada(self):
        # qualquer tentativa de conexão levantaria AssertionError (ver Base.setUp)
        resumo = processar(EXEMPLOS / "troca", self.saida, AGORA, decisoes_arquivo=EXEMPLOS / "decisoes" / "decisoes_exemplo.json")
        self.assertEqual(resumo["fichas"], 7)

    def test_nenhum_modulo_importa_rede_processos_ou_banco(self):
        for arq in FONTES:
            fonte = arq.read_text(encoding="utf-8")
            for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", fonte, re.M):
                alvo = (m.group(1) or m.group(2)).replace(" ", "")
                for modulo in alvo.split(","):
                    for proibido in IMPORTS_PROIBIDOS:
                        self.assertFalse(modulo == proibido or modulo.startswith(proibido + "."), (arq.name, modulo))

    def test_nenhum_modulo_acessa_ambiente_cofre_ou_agente(self):
        for arq in FONTES:
            fonte = arq.read_text(encoding="utf-8")
            for padrao in ("os.environ", "getenv", "os.system", "Popen", "urlopen", "SuzukiOfertas-AgenteAutomatico/",
                           ".db\"", ".db'", "awin-catalog", "vault", "Metricool", "metricool", "api.telegram", "cloudflare"):
                if arq.name == "esquema.py" and padrao in ("vault", "SuzukiOfertas-AgenteAutomatico/"):
                    continue          # esquema.py cita 'vault'/'cofre' só na lista de nomes de campo PROIBIDOS
                self.assertFalse(padrao in fonte, (arq.name, padrao))

    def test_modulo_de_fragmento_so_importa_config_e_regras_do_gerador(self):
        fonte = (PACOTE / "reel_fragmento.py").read_text(encoding="utf-8")
        importados = set(re.findall(r"from reel_gen\.(\w+) import", fonte))
        self.assertEqual(importados, {"config", "rules"})        # nunca pipeline/ffmpeg_build/audio/motion
        self.assertNotIn("import reel_gen", fonte)

    def test_apenas_biblioteca_padrao(self):
        stdlib = set(__import__("sys").stdlib_module_names)
        for arq in FONTES:
            for m in re.finditer(r"^(?:from\s+([\w]+)[\w.]*\s+import|import\s+([\w]+))", arq.read_text(encoding="utf-8"), re.M):
                raiz = m.group(1) or m.group(2)
                self.assertTrue(raiz in stdlib or raiz in ("produtos", "reel_gen"), (arq.name, raiz))
