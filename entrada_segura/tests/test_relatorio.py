import errno
import hashlib
import os
import re
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from entrada_segura import portao, relatorio
from entrada_segura.erros import FalhaPersistencia
from entrada_segura.portao import avaliar_producao
from entrada_segura.tests import suporte_sintetico as S
from entrada_segura.tests.suporte_sintetico import AGORA

RAIZ = Path(__file__).resolve().parents[2]


class Base(S.SemRede):
    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name).resolve()
        self.base = self.tmp / "evidencias"
        self.base.mkdir()
        self.lote = self.tmp / "lote"
        shutil.copytree(RAIZ / "curadoria_b" / "exemplos_ficticios", self.lote)       # fixture registrada: aceita em produção
        self.arq = ["ficha_valida.json"]

    def relatorio(self):
        return portao.Portao(S.config_sintetica()).avaliar(self.lote, self.arq)


class Diretorio(Base):
    def test_cria_diretorio_novo_a_cada_execucao(self):
        a = relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA)
        b = relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA)
        self.assertNotEqual(a, b)
        for d in (a, b):
            self.assertRegex(d.name, r"^execucao-20261120T120000Z-[0-9a-f]{8}$")
            self.assertTrue(d.is_dir())
            self.assertEqual(oct(d.stat().st_mode & 0o777), "0o700")

    def test_nao_reutiliza_diretorio_existente(self):
        relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA, sufixo="deadbeef")
        with self.assertRaises(FalhaPersistencia) as cm:
            relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA, sufixo="deadbeef")
        self.assertEqual(cm.exception.codigo, "diretorio_ja_existe")

    def test_base_invalida(self):
        os.symlink(self.base, self.tmp / "link")
        (self.tmp / "arquivo").write_bytes(b"x")
        for base, codigo in ((self.tmp / "nao_existe", "base_inexistente"), (self.tmp / "link", "base_invalida"), (self.tmp / "arquivo", "base_invalida")):
            with self.assertRaises(FalhaPersistencia) as cm:
                relatorio.criar_diretorio_evidencia(base, relogio=lambda: AGORA)
            self.assertEqual(cm.exception.codigo, codigo, base)

    def test_sufixo_invalido(self):
        with self.assertRaises(FalhaPersistencia):
            relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA, sufixo="../x")


class Persistencia(Base):
    def test_persiste_e_confere_o_hash(self):
        r = self.relatorio()
        d = relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA)
        c = relatorio.persistir(r, d)
        gravado = (d / "relatorio_entrada.json").read_bytes()
        self.assertEqual(gravado, relatorio.serializar(r))
        self.assertEqual((c.sha256, c.bytes), (hashlib.sha256(gravado).hexdigest(), len(gravado)))
        self.assertEqual(c.caminho_relativo, f"{d.name}/relatorio_entrada.json")
        self.assertEqual(oct((d / "relatorio_entrada.json").stat().st_mode & 0o777), "0o600")

    def test_nao_sobrescreve_relatorio_existente(self):
        r = self.relatorio()
        d = relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA)
        relatorio.persistir(r, d)
        original = (d / "relatorio_entrada.json").read_bytes()
        with self.assertRaises(FalhaPersistencia) as cm:
            relatorio.persistir(r, d)
        self.assertEqual(cm.exception.codigo, "relatorio_ja_existe")
        self.assertEqual((d / "relatorio_entrada.json").read_bytes(), original)

    def test_falhas_de_gravacao(self):
        r = self.relatorio()
        for nome, patch, codigo in (("disco_cheio", mock.patch.object(relatorio.os, "write", side_effect=OSError(errno.ENOSPC, "cheio")), "erro_ao_gravar"),
                                    ("fsync", mock.patch.object(relatorio.os, "fsync", side_effect=OSError(errno.EIO, "io")), "erro_ao_gravar"),
                                    ("escrita_sem_progresso", mock.patch.object(relatorio.os, "write", return_value=0), "escrita_incompleta")):
            d = relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA)
            with patch, self.assertRaises(FalhaPersistencia) as cm:
                relatorio.persistir(r, d)
            self.assertEqual(cm.exception.codigo, codigo, nome)

    def test_hash_divergente_na_releitura(self):
        r = self.relatorio()
        d = relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA)
        with mock.patch.object(relatorio.os, "read", return_value=b"corrompido"):
            with self.assertRaises(FalhaPersistencia) as cm:
                relatorio.persistir(r, d)
        self.assertEqual(cm.exception.codigo, "hash_divergente")

    def test_diretorio_invalido_ou_inexistente(self):
        r = self.relatorio()
        os.symlink(self.base, self.tmp / "link")
        for d in (self.tmp / "link", self.tmp / "nao_existe"):
            with self.assertRaises(FalhaPersistencia):
                relatorio.persistir(r, d)

    def test_somente_leitura(self):
        r = self.relatorio()
        d = relatorio.criar_diretorio_evidencia(self.base, relogio=lambda: AGORA)
        os.chmod(d, 0o500)
        self.addCleanup(os.chmod, d, 0o700)
        if os.geteuid() == 0:
            self.skipTest("executando como root: permissões de diretório não bloqueiam a gravação (coberto por simulação em test_falhas_de_gravacao)")
        with self.assertRaises(FalhaPersistencia):
            relatorio.persistir(r, d)


class ConsumoPermitido(Base):
    def test_aceita_com_comprovante_permite_o_consumo(self):
        res = avaliar_producao(self.lote, self.arq, base_evidencia=self.base)
        self.assertEqual(res.decisao.codigos, ("aceita_ficticio_reconhecido",))
        self.assertTrue(res.consumo_permitido)
        self.assertEqual(res.bytes_verificados.keys(), {"ficha_valida.json"})
        gravado = self.base / res.comprovante.caminho_relativo
        self.assertEqual(hashlib.sha256(gravado.read_bytes()).hexdigest(), res.comprovante.sha256)
        self.assertEqual(gravado.read_bytes(), relatorio.serializar(res.relatorio))

    def test_sem_base_de_evidencia_o_relatorio_so_existe_em_memoria(self):
        res = avaliar_producao(self.lote, self.arq)
        self.assertEqual(res.decisao.resultado, "aceita")
        self.assertIsNone(res.comprovante)
        self.assertFalse(res.consumo_permitido)
        self.assertTrue(res.relatorio.dados)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_falha_de_persistencia_bloqueia_o_consumo_mesmo_com_decisao_aceita(self):
        for base, esperado in ((self.tmp / "nao_existe", "base_inexistente"),):
            res = avaliar_producao(self.lote, self.arq, base_evidencia=base)
            self.assertEqual(res.decisao.resultado, "aceita")
            self.assertFalse(res.consumo_permitido)
            self.assertEqual(res.erro_persistencia, esperado)
        with mock.patch.object(relatorio.os, "write", side_effect=OSError(errno.ENOSPC, "cheio")):
            res = avaliar_producao(self.lote, self.arq, base_evidencia=self.base)
        self.assertEqual((res.decisao.resultado, res.consumo_permitido, res.erro_persistencia), ("aceita", False, "erro_ao_gravar"))
        with mock.patch.object(relatorio.os, "read", return_value=b"x"):
            res = avaliar_producao(self.lote, self.arq, base_evidencia=self.base)
        self.assertEqual((res.consumo_permitido, res.erro_persistencia), (False, "hash_divergente"))

    def test_recusa_gera_relatorio_em_memoria_e_persistido_sem_consumo(self):
        (self.lote / "ficha_valida.json").write_bytes(b"{}")
        res = avaliar_producao(self.lote, self.arq, base_evidencia=self.base)
        self.assertEqual((res.decisao.resultado, res.consumo_permitido, res.bytes_verificados), ("recusada", False, {}))
        self.assertIsNotNone(res.comprovante)                                       # a recusa também deixa evidência
        self.assertTrue(res.relatorio.dados)

    def test_cada_execucao_tem_seu_diretorio_e_nada_e_sobrescrito(self):
        a = avaliar_producao(self.lote, self.arq, base_evidencia=self.base)
        original = (self.base / a.comprovante.caminho_relativo).read_bytes()
        b = avaliar_producao(self.lote, self.arq, base_evidencia=self.base)
        self.assertNotEqual(a.comprovante.caminho_relativo, b.comprovante.caminho_relativo)
        self.assertEqual((self.base / a.comprovante.caminho_relativo).read_bytes(), original)
        self.assertEqual(len(list(self.base.iterdir())), 2)

    def test_consumo_exige_decisao_aceita_e_comprovante(self):
        from entrada_segura.portao import ResultadoEntrada
        from entrada_segura.relatorio import Comprovante, Decisao
        c = Comprovante("x/y", "0" * 64, 1)
        r = self.relatorio()
        for decisao, comp, esperado in ((Decisao("aceita", ()), c, True), (Decisao("aceita", ()), None, False), (Decisao("recusada", ()), c, False),
                                        (Decisao("recusada", ()), None, False)):
            self.assertIs(ResultadoEntrada(r, decisao, comp).consumo_permitido, esperado)
