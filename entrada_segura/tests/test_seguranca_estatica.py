"""Segurança estática (AST/texto) sobre ``entrada_segura/*.py`` (exceto ``tests/``), deriva de flags, dependência e documentação."""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

from entrada_segura import assinatura, politica

PACOTE = Path(__file__).resolve().parents[1]
RAIZ = PACOTE.parent
MODULOS = sorted(p for p in PACOTE.glob("*.py"))
PROIBIDOS_IMPORT = {"argparse", "subprocess", "socket", "urllib", "http", "ssl", "ctypes", "pickle", "shelve", "marshal", "importlib", "runpy", "os.environ"}
PROIBIDOS_NOMES = {"environ", "getenv", "argv", "__debug__", "eval", "exec", "compile", "__import__"}
OUTROS_PACOTES = ("produtos", "curadoria_b", "orquestrador_b2", "gerador", "reels", "reel_gen", "scripts")


def arvore(p: Path) -> ast.AST:
    return ast.parse(p.read_text(encoding="utf-8"))


def importados(t: ast.AST):
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield a.name, n
        elif isinstance(n, ast.ImportFrom):
            yield ("." * n.level) + (n.module or ""), n


class Estatica(unittest.TestCase):
    def test_modulos_encontrados(self):
        nomes = {p.name for p in MODULOS}
        self.assertTrue({"portao.py", "assinatura.py", "integridade.py", "classificacao.py", "politica.py"} <= nomes)

    def test_sem_main_cli_ambiente_ou_execucao_dinamica(self):
        self.assertFalse((PACOTE / "__main__.py").exists())
        for p in MODULOS:
            t = arvore(p)
            for nome, no in importados(t):
                self.assertNotIn(nome.split(".")[0], PROIBIDOS_IMPORT, f"{p.name}: import {nome}")
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    self.assertNotIn(n.id, PROIBIDOS_NOMES, f"{p.name}:{n.lineno}")
                if isinstance(n, ast.Attribute):
                    self.assertNotIn(n.attr, {"environ", "getenv", "argv"}, f"{p.name}:{n.lineno}")
                self.assertNotIsInstance(n, ast.Assert, f"{p.name}: assert não pode ser controle")
            texto = p.read_text(encoding="utf-8")
            for proibido in ("os.environ", "getenv", "sys.argv", "__debug__"):
                self.assertNotIn(proibido, texto.replace(f"``{proibido}``", ""), f"{p.name}: {proibido}")

    def test_apenas_biblioteca_padrao_e_cryptography_so_em_assinatura(self):
        padrao = set(sys.stdlib_module_names)
        for p in MODULOS:
            for nome, no in importados(arvore(p)):
                if nome.startswith("."):
                    continue
                raiz = nome.split(".")[0]
                if raiz == "cryptography":
                    self.assertEqual(p.name, "assinatura.py", f"{p.name}: cryptography fora de assinatura.py")
                    continue
                self.assertIn(raiz, padrao | {"entrada_segura"}, f"{p.name}: import de terceiro {nome}")

    def test_cryptography_preguicosa_e_so_ed25519_publica_e_invalidsignature(self):
        t = arvore(PACOTE / "assinatura.py")
        topo = [n for n in t.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any((getattr(n, "module", "") or "").startswith("cryptography") or any(a.name.startswith("cryptography") for a in getattr(n, "names", [])) for n in topo))
        funcao = next(n for n in ast.walk(t) if isinstance(n, ast.FunctionDef) and n.name == "_importar_cripto")
        achados = sorted((n.module, tuple(sorted(a.name for a in n.names))) for n in ast.walk(funcao) if isinstance(n, ast.ImportFrom))
        self.assertEqual(achados, [("cryptography.exceptions", ("InvalidSignature",)),
                                   ("cryptography.hazmat.primitives.asymmetric.ed25519", ("Ed25519PublicKey",))])
        todos = [nome for nome, _ in importados(t) if nome.startswith("cryptography")]
        self.assertEqual(len(todos), 2)

    def test_sem_fallback_nem_aritmetica_de_curva(self):
        for p in MODULOS:
            texto = p.read_text(encoding="utf-8")
            for sinal in ("sha512", "2**255", "2 ** 255", "pow(", "Ed25519PrivateKey", "from_private_bytes", ".sign(", "edwards", "x25519"):
                self.assertNotIn(sinal, texto, f"{p.name}: {sinal}")
        verificacoes = [n for p in MODULOS for n in ast.walk(arvore(p)) if isinstance(n, ast.Attribute) and n.attr == "verify"]
        self.assertEqual(len(verificacoes), 1)                              # única verificação: Ed25519PublicKey.verify

    def test_politica_de_producao(self):
        self.assertEqual(politica.PRODUCAO.ancoras, frozenset())
        self.assertIs(politica.PRODUCAO.dados_reais_habilitado, False)
        self.assertIs(politica.PRODUCAO.produtos_reais_habilitado, False)
        self.assertEqual((politica.PRODUCAO.max_arquivos, politica.PRODUCAO.max_bytes_arquivo, politica.PRODUCAO.max_bytes_total), (1000, 2 * 1024 * 1024, 64 * 1024 * 1024))
        self.assertEqual(politica.PRODUCAO.tolerancia_relogio.total_seconds(), 0)
        self.assertEqual(politica.PRODUCAO.validade_maxima_lote.days, 7)
        self.assertEqual(politica.PRODUCAO.janela_revogacao.total_seconds(), 24 * 3600)
        self.assertTrue(politica.PRODUCAO.exigir_garantia_forte)

    def test_nenhum_material_de_chave_privada_fora_de_tests(self):
        for p in MODULOS + [PACOTE / "README.md", PACOTE / "requirements.txt"]:
            texto = p.read_text(encoding="utf-8")
            for sinal in ("PRIVATE KEY", "SINTETICO-TESTE", "BEGIN OPENSSH", "BEGIN RSA"):
                self.assertNotIn(sinal, texto, f"{p.name}: {sinal}")
        com_privada = [p.name for p in (PACOTE / "tests").glob("*.py") if "Ed25519PrivateKey" in p.read_text(encoding="utf-8") and p.name != __file__.split("/")[-1]]
        self.assertEqual(com_privada, ["suporte_sintetico.py"])                       # chaves privadas SÓ no suporte sintético

    def test_pacote_nao_importa_outros_modulos_do_repositorio(self):
        for p in MODULOS:
            for nome, _ in importados(arvore(p)):
                self.assertNotIn(nome.split(".")[0], OUTROS_PACOTES, f"{p.name}: importa {nome}")

    def test_nada_fora_do_pacote_importa_ou_menciona_entrada_segura(self):
        """B3-A1 é isolada: nenhum ponto de entrada existente foi integrado (isso é a B3-A2)."""
        git = subprocess.run(["git", "ls-files", "*.py"], cwd=RAIZ, capture_output=True, text=True)
        arquivos = git.stdout.split() if git.returncode == 0 else [str(p.relative_to(RAIZ)) for p in RAIZ.rglob("*.py")]
        for rel in arquivos:
            if rel.startswith("entrada_segura/"):
                continue
            self.assertNotIn("entrada_segura", (RAIZ / rel).read_text(encoding="utf-8", errors="replace"), rel)

    def test_portao_e_config_so_sao_usados_dentro_do_pacote_e_seus_testes(self):
        for rel in subprocess.run(["git", "ls-files", "*.py"], cwd=RAIZ, capture_output=True, text=True).stdout.split():
            if rel.startswith("entrada_segura/"):
                continue
            texto = (RAIZ / rel).read_text(encoding="utf-8", errors="replace")
            for nome in ("ConfigVerificacao", "suporte_sintetico", "Portao("):
                self.assertNotIn(nome, texto, rel)

    def test_sem_estado_persistente_oculto(self):
        for p in MODULOS:
            texto = p.read_text(encoding="utf-8")
            for sinal in ("pickle", "shelve", "sqlite", "tempfile", ".cache", "expanduser"):
                self.assertNotIn(sinal, texto, f"{p.name}: {sinal}")


class DerivaDeFlags(unittest.TestCase):
    """Importa os módulos existentes SOMENTE aqui (teste): as constantes do pacote devem coincidir com as do repositório."""

    def test_flags_coincidem_com_as_do_repositorio(self):
        from curadoria_b.ficha import PRODUTOS_REAIS_HABILITADO
        from produtos.selecao_contrato import DADOS_REAIS_HABILITADO
        self.assertIs(politica.PRODUCAO.produtos_reais_habilitado, PRODUTOS_REAIS_HABILITADO)
        self.assertIs(politica.PRODUCAO.dados_reais_habilitado, DADOS_REAIS_HABILITADO)
        self.assertFalse(PRODUTOS_REAIS_HABILITADO or DADOS_REAIS_HABILITADO)


class Dependencia(unittest.TestCase):
    def test_requirements_unico_e_minimo_justificado(self):
        linhas = (PACOTE / "requirements.txt").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(linhas, ["cryptography>=50.0.1"])

    def test_nenhum_arquivo_de_dependencias_na_raiz_foi_criado(self):
        for nome in ("requirements.txt", "pyproject.toml", "setup.cfg", "setup.py", "Pipfile"):
            self.assertFalse((RAIZ / nome).exists(), nome)


class Documentacao(unittest.TestCase):
    def test_readme_registra_as_limitacoes(self):
        t = re.sub(r"\s+", " ", (PACOTE / "README.md").read_text(encoding="utf-8").replace("**", "").replace("`", "")).lower()
        for trecho in ("tolerância de relógio", "0 s", "repetição de uma lista", "estado local apagável", "publicação/metricool", "windows", "não foi implementada",
                       "recusa", "garantia_plataforma_insuficiente", "adversário que executa código no mesmo processo", "não são definitivos para fotografias",
                       "p-05", "b3-a2", "revogação instantânea", "reavaliadas antes do primeiro dado", "nenhuma integração operacional windows",
                       "compatibilidade windows ou ambiente linux", "não significa que o projeto esteja pronto para produtos reais", "âncora de produção é vazia",
                       "ancestrais da raiz", "link simbólico"):
            self.assertIn(trecho, t, trecho)

    def test_readme_nao_promete_revogacao_instantanea_nem_protecao_windows(self):
        t = re.sub(r"\s+", " ", (PACOTE / "README.md").read_text(encoding="utf-8").replace("**", "").replace("`", "")).lower()
        self.assertNotIn("revogação é instantânea", t)
        self.assertNotIn("protegido no windows", t)
        self.assertIn("não há garantia de revogação instantânea", t)
