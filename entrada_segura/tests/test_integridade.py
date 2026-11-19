import errno
import hashlib
import os
import socket
import stat
import tempfile
import types
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from entrada_segura import integridade as ig
from entrada_segura.erros import ErroIntegridade
from entrada_segura.politica import PRODUCAO

PADRAO = object()
PEQUENA = replace(PRODUCAO, max_arquivos=5, max_bytes_arquivo=100, max_bytes_total=150)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name).resolve()
        self.lote = self.tmp / "lote"
        (self.lote / "sub").mkdir(parents=True)
        (self.lote / "a.json").write_bytes(b'{"a":1}')
        (self.lote / "sub" / "b.txt").write_bytes(b"bb")
        self.arq = ["a.json", "sub/b.txt"]

    def ler(self, arquivos=PADRAO, raiz=None, config=PRODUCAO, **kw):
        return ig.ler_lote(self.lote if raiz is None else raiz, self.arq if arquivos is PADRAO else arquivos, config, **kw)

    def codigo(self, arquivos=PADRAO, raiz=None, config=PRODUCAO, **kw):
        with self.assertRaises(ErroIntegridade) as cm:
            self.ler(arquivos, raiz, config, **kw)
        return cm.exception.codigo


class Leitura(Base):
    def test_leitura_unica_com_bytes_e_hashes_consistentes(self):
        r = self.ler()
        self.assertEqual(r.arquivos, {"a.json": b'{"a":1}', "sub/b.txt": b"bb"})
        self.assertEqual(r.total_bytes, 9)
        self.assertEqual([h["caminhoRelativo"] for h in r.hashes], ["a.json", "sub/b.txt"])
        for h in r.hashes:
            self.assertEqual(h["sha256"], hashlib.sha256(r.arquivos[h["caminhoRelativo"]]).hexdigest())
            self.assertEqual(h["bytes"], len(r.arquivos[h["caminhoRelativo"]]))
        self.assertEqual(r.raiz_resolvida, str(self.lote))

    def test_nao_abre_o_caminho_depois_da_leitura(self):
        """Hash e parse usam os bytes já lidos; o caminho não é reaberto (cada arquivo é aberto exatamente uma vez)."""
        abertos = []
        real = os.open

        def espiao(nome, flags, *a, **k):
            abertos.append(nome)
            return real(nome, flags, *a, **k)
        with mock.patch.object(ig.os, "open", side_effect=espiao), mock.patch.object(ig, "nivel_de_garantia", return_value=ig.NivelGarantia.FORTE):
            self.ler()
        self.assertEqual(abertos.count("a.json"), 1)
        self.assertEqual(abertos.count("b.txt"), 1)

    def test_referencias_externas_nao_sao_seguidas(self):
        sentinela = self.tmp / "SENTINELA_EXTERNA.txt"
        sentinela.write_bytes(b"nao ler")
        (self.lote / "a.json").write_bytes(('{"u":"https://a.example","caminho":"%s","rel":"../SENTINELA_EXTERNA.txt"}' % sentinela).encode())
        abertos = []
        real = os.open

        def espiao(nome, flags, *a, **k):
            abertos.append(str(nome))
            return real(nome, flags, *a, **k)
        with mock.patch.object(ig.os, "open", side_effect=espiao), mock.patch.object(ig, "nivel_de_garantia", return_value=ig.NivelGarantia.FORTE):
            self.ler()
        self.assertFalse(any("SENTINELA" in a for a in abertos))

    def test_lista_vazia_ou_invalida(self):
        for arq in ([], None, "a.json", 5):
            self.assertEqual(self.codigo(arq), "lista_de_arquivos_invalida")


class Caminhos(Base):
    def test_caminhos_proibidos(self):
        casos = ["../x", "a/../b", "/etc/passwd", "a\\b", "a//b", "./a.json", "a/./b", "a/", "", "a:b", "a\x00b", "a\nb", "a\x7fb", "x" * 241, "/".join(["d"] * 9) + "/f"]
        for c in casos:
            self.assertEqual(self.codigo([c]), "caminho_invalido", repr(c))

    def test_unicode_nao_nfc_e_duplicatas(self):
        import unicodedata
        nfd = unicodedata.normalize("NFD", "á.json")
        self.assertEqual(self.codigo([nfd]), "caminho_invalido")
        self.assertEqual(self.codigo(["A.json", "a.json"]), "caminho_duplicado")
        self.assertEqual(self.codigo(["a.json", "a.json"]), "caminho_duplicado")

    def test_nome_com_caixa_diferente_nao_e_aceito_como_igual(self):
        self.assertEqual(self.codigo(["A.json", "sub/b.txt"]), "arquivo_extra")                  # a.json presente não é A.json


class ListaFechada(Base):
    def test_extra_oculto_e_temporario(self):
        for nome in (".oculto.json", "x.tmp", "sub/.escondido"):
            (self.lote / nome).write_bytes(b"x")
            self.assertEqual(self.codigo(), "arquivo_extra", nome)
            (self.lote / nome).unlink()

    def test_arquivo_ausente(self):
        (self.lote / "a.json").unlink()
        self.assertEqual(self.codigo(), "arquivo_ausente")
        self.assertEqual(self.codigo(["a.json", "sub/b.txt", "novo.json"]), "arquivo_ausente")

    def test_diretorio_vazio_nao_e_arquivo(self):
        (self.lote / "vazio").mkdir()
        self.assertEqual(self.ler().total_bytes, 9)
        self.assertEqual(self.codigo(["a.json", "sub/b.txt", "vazio"]), "arquivo_ausente")

    def test_pedir_um_diretorio_como_arquivo(self):
        self.assertEqual(self.codigo(["a.json", "sub/b.txt", "sub"]), "arquivo_ausente")


class Links(Base):
    def test_symlink_em_arquivo_solicitado(self):
        (self.lote / "a.json").unlink()
        os.symlink(self.tmp / "externo.json", self.lote / "a.json")
        (self.tmp / "externo.json").write_bytes(b"x")
        self.assertEqual(self.codigo(), "link_simbolico")

    def test_symlink_extra_na_listagem(self):
        os.symlink(self.lote / "a.json", self.lote / "atalho.json")
        self.assertEqual(self.codigo(), "link_simbolico")

    def test_symlink_em_diretorio_intermediario(self):
        outro = self.tmp / "outro"
        outro.mkdir()
        (outro / "b.txt").write_bytes(b"bb")
        import shutil
        shutil.rmtree(self.lote / "sub")
        os.symlink(outro, self.lote / "sub")
        self.assertEqual(self.codigo(), "link_simbolico")

    def test_raiz_simbolica_e_recusada_mesmo_com_destino_valido(self):
        link = self.tmp / "lote_link"
        os.symlink(self.lote, link)
        self.assertEqual(self.codigo(raiz=link), "raiz_simbolica")
        self.assertEqual(self.codigo(raiz=str(link)), "raiz_simbolica")

    def test_raiz_simbolica_recusada_antes_do_realpath(self):
        link = self.tmp / "lote_link"
        os.symlink(self.lote, link)
        with mock.patch.object(ig.os.path, "realpath", side_effect=AssertionError("realpath chamado antes da recusa")) as rp:
            self.assertEqual(self.codigo(raiz=link), "raiz_simbolica")
            rp.assert_not_called()

    def test_raiz_simbolica_para_diretorio_inexistente(self):
        link = self.tmp / "pendente"
        os.symlink(self.tmp / "nao_existe", link)
        self.assertEqual(self.codigo(raiz=link), "raiz_simbolica")

    def test_ancestral_simbolico_da_raiz_e_confiavel_e_documentado(self):
        ancestral = self.tmp / "ancestral"
        os.symlink(self.tmp, ancestral)
        r = self.ler(raiz=ancestral / "lote")
        self.assertEqual(r.raiz_resolvida, str(self.lote))                       # limite documentado: ancestrais do operador são confiáveis

    def test_raiz_trocada_por_link_durante_a_abertura(self):
        antigo = self.tmp / "lote_antigo"

        def gancho(evento, _):
            if evento == "apos_abrir_raiz":                                      # o operador (ou um adversário) troca a raiz por um link
                os.rename(self.lote, antigo)
                os.symlink(antigo, self.lote)
        self.assertEqual(self.codigo(_gancho=gancho), "raiz_alterada")

    def test_hardlink(self):
        os.link(self.lote / "a.json", self.tmp / "fora.json")
        self.assertEqual(self.codigo(), "hardlink")
        os.unlink(self.tmp / "fora.json")
        os.link(self.lote / "a.json", self.lote / "dois.json")
        self.assertEqual(self.codigo(["a.json", "dois.json", "sub/b.txt"]), "hardlink")


class Especiais(Base):
    def test_fifo(self):
        os.mkfifo(self.lote / "fila")
        self.assertEqual(self.codigo(), "arquivo_especial")

    def test_fifo_solicitada_nao_bloqueia(self):
        os.mkfifo(self.lote / "fila")
        self.assertEqual(self.codigo(["a.json", "sub/b.txt", "fila"]), "arquivo_especial")

    def test_socket(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(s.close)
        s.bind(str(self.lote / "s.sock"))
        self.assertEqual(self.codigo(), "arquivo_especial")

    def test_dispositivo(self):
        try:
            os.mknod(self.lote / "dev", stat.S_IFCHR | 0o600, os.makedev(1, 3))
        except (PermissionError, OSError) as e:
            self.skipTest(f"sistema de arquivos/privilégio não permite criar dispositivo ({e.__class__.__name__})")
        self.assertEqual(self.codigo(), "arquivo_especial")


class Limites(Base):
    def test_arquivo_acima_do_limite(self):
        (self.lote / "a.json").write_bytes(b"x" * 101)
        self.assertEqual(self.codigo(config=PEQUENA), "arquivo_grande")
        (self.lote / "a.json").write_bytes(b"x" * 100)
        self.assertEqual(len(self.ler(config=PEQUENA).arquivos["a.json"]), 100)

    def test_excesso_de_arquivos_e_de_bytes(self):
        for i in range(6):
            (self.lote / f"f{i}.txt").write_bytes(b"x")
        self.assertEqual(self.codigo(["a.json", "sub/b.txt"] + [f"f{i}.txt" for i in range(6)], config=PEQUENA), "excesso_de_arquivos")
        for i in range(6):
            (self.lote / f"f{i}.txt").unlink()
        (self.lote / "a.json").write_bytes(b"x" * 100)
        (self.lote / "sub" / "b.txt").write_bytes(b"y" * 60)
        self.assertEqual(self.codigo(config=PEQUENA), "excesso_de_bytes")

    def test_excesso_de_arquivos_na_listagem(self):
        for i in range(6):
            (self.lote / f"f{i}.txt").write_bytes(b"x")
        self.assertEqual(self.codigo(config=PEQUENA), "excesso_de_arquivos")

    def test_diretorios_aninhados_demais(self):
        p = self.lote
        for i in range(10):
            p = p / f"d{i}"
            p.mkdir()
        self.assertEqual(self.codigo(), "profundidade_excedida")


class MontagemEAlteracao(Base):
    def test_ponto_de_montagem_simulado_por_st_dev(self):
        real = os.fstat

        def fstat(fd):
            st = real(fd)
            if not stat.S_ISREG(st.st_mode):
                return st
            d = {k: getattr(st, k) for k in dir(st) if k.startswith("st_")}
            d["st_dev"] = st.st_dev + 1                                          # arquivo em "outro dispositivo"
            return types.SimpleNamespace(**d)
        with mock.patch.object(ig.os, "fstat", side_effect=fstat):
            self.assertEqual(self.codigo(), "ponto_de_montagem")

    def test_arquivo_trocado_por_link_entre_stat_e_abertura(self):
        def gancho(evento, rel):
            if evento == "apos_stat" and rel == "a.json":
                (self.lote / "a.json").unlink()
                (self.tmp / "alvo.json").write_bytes(b"alvo")
                os.symlink(self.tmp / "alvo.json", self.lote / "a.json")
        self.assertEqual(self.codigo(_gancho=gancho), "link_simbolico")

    def test_arquivo_trocado_por_fifo_entre_stat_e_abertura(self):
        def gancho(evento, rel):
            if evento == "apos_stat" and rel == "a.json":
                (self.lote / "a.json").unlink()
                os.mkfifo(self.lote / "a.json")
        self.assertEqual(self.codigo(_gancho=gancho), "arquivo_especial")

    def test_arquivo_trocado_por_outro_regular_entre_stat_e_abertura_devolve_bytes_consistentes(self):
        def gancho(evento, rel):
            if evento == "apos_stat" and rel == "a.json":
                (self.lote / "a.json").unlink()
                (self.lote / "a.json").write_bytes(b'{"trocado":1}')
        r = self.ler(_gancho=gancho)                                             # o que foi aberto é o que foi lido e hasheado
        self.assertEqual(r.arquivos["a.json"], b'{"trocado":1}')
        self.assertEqual(r.hashes[0]["sha256"], hashlib.sha256(b'{"trocado":1}').hexdigest())

    def test_arquivo_alterado_durante_a_leitura(self):
        def gancho(evento, rel):
            if evento == "apos_leitura" and rel == "a.json":
                (self.lote / "a.json").write_bytes(b'{"a":2,"x":"mais bytes"}')
        self.assertEqual(self.codigo(_gancho=gancho), "lote_alterado_durante_leitura")

    def test_arquivo_reescrito_com_mesmo_tamanho_muda_mtime(self):
        def gancho(evento, rel):
            if evento == "apos_leitura" and rel == "a.json":
                os.utime(self.lote / "a.json", ns=(1, 1))
        self.assertEqual(self.codigo(_gancho=gancho), "lote_alterado_durante_leitura")

    def test_arquivo_extra_aparece_durante_a_leitura(self):
        def gancho(evento, rel):
            if evento == "apos_leitura" and rel == "sub/b.txt":
                (self.lote / "novo.json").write_bytes(b"x")
        self.assertEqual(self.codigo(_gancho=gancho), "lote_alterado_durante_leitura")

    def test_arquivo_removido_durante_a_leitura(self):
        def gancho(evento, rel):
            if evento == "apos_leitura" and rel == "sub/b.txt":
                (self.lote / "a.json").unlink()
        self.assertEqual(self.codigo(_gancho=gancho), "lote_alterado_durante_leitura")

    def test_troca_antes_da_leitura_devolve_bytes_consistentes_com_o_hash(self):
        def gancho(evento, rel):
            if evento == "apos_listagem":
                (self.lote / "a.json").write_bytes(b'{"a":1}')                  # mesma coisa: nada muda
        r = self.ler(_gancho=gancho)
        self.assertEqual(hashlib.sha256(r.arquivos["a.json"]).hexdigest(), r.hashes[0]["sha256"])


class ErrosDeSO(Base):
    def test_erros_de_so_viram_recusa_com_codigo(self):
        casos = {errno.EACCES: "acesso_negado", errno.EMFILE: "limite_de_descritores", errno.EIO: "erro_de_so", errno.ENOENT: "arquivo_ausente"}
        for e, esperado in casos.items():
            with mock.patch.object(ig.os, "read", side_effect=OSError(e, "simulado")):
                self.assertEqual(self.codigo(), esperado, e)

    def test_erro_ao_abrir(self):
        with mock.patch.object(ig.os, "open", side_effect=OSError(errno.EMFILE, "simulado")), mock.patch.object(ig, "nivel_de_garantia", return_value=ig.NivelGarantia.FORTE):
            self.assertEqual(self.codigo(), "limite_de_descritores")

    def test_raiz_inexistente_ou_nao_diretorio(self):
        self.assertEqual(self.codigo(raiz=self.tmp / "nao_existe"), "arquivo_ausente")
        self.assertEqual(self.codigo(raiz=self.lote / "a.json"), "raiz_nao_diretorio")
        self.assertEqual(self.codigo(raiz=""), "raiz_invalida")

    def test_descritores_sao_fechados(self):
        antes = len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else None
        for _ in range(3):
            self.ler()
            self.codigo(["a.json", "sub/b.txt", "inexistente"])
        if antes is not None:
            self.assertLessEqual(len(os.listdir("/proc/self/fd")), antes + 1)


def _falso_os(**sobrescritas):
    base = dict(name="posix", O_NOFOLLOW=1, O_DIRECTORY=2, O_CLOEXEC=3, O_NONBLOCK=4, O_NOCTTY=5, O_RDONLY=0, fstat=lambda fd: None)
    f = types.SimpleNamespace(**base)
    f.open, f.stat, f.scandir = (lambda *a: None), (lambda *a: None), (lambda *a: None)
    f.supports_dir_fd, f.supports_follow_symlinks, f.supports_fd = {f.open, f.stat}, {f.stat}, {f.scandir}
    for k, v in sobrescritas.items():
        if v is None:
            f.__dict__.pop(k, None)
        else:
            setattr(f, k, v)
    return f


class Plataformas(Base):
    def test_forte_em_posix_com_recursos(self):
        self.assertIs(ig.nivel_de_garantia(), ig.NivelGarantia.FORTE)
        self.assertIs(ig.nivel_de_garantia(_falso_os(), types.SimpleNamespace(platform="linux")), ig.NivelGarantia.FORTE)

    def test_simulacoes_insuficientes(self):
        linux = types.SimpleNamespace(platform="linux")
        casos = {"windows_os": (_falso_os(name="nt"), linux), "windows_sys": (_falso_os(), types.SimpleNamespace(platform="win32")),
                 "cygwin": (_falso_os(), types.SimpleNamespace(platform="cygwin")),
                 "sem_nofollow": (_falso_os(O_NOFOLLOW=None), linux), "sem_directory": (_falso_os(O_DIRECTORY=None), linux),
                 "sem_cloexec": (_falso_os(O_CLOEXEC=None), linux), "sem_dir_fd": (_falso_os(supports_dir_fd=set()), linux),
                 "sem_follow_symlinks": (_falso_os(supports_follow_symlinks=set()), linux), "sem_scandir_fd": (_falso_os(supports_fd=set()), linux),
                 "sem_fstat": (_falso_os(fstat=None), linux), "objeto_estranho": (object(), linux)}
        for nome, (o, s) in casos.items():
            self.assertIs(ig.nivel_de_garantia(o, s), ig.NivelGarantia.INSUFICIENTE, nome)

    def test_plataforma_insuficiente_recusa_sem_tentar_ler(self):
        with mock.patch.object(ig, "nivel_de_garantia", return_value=ig.NivelGarantia.INSUFICIENTE), \
                mock.patch.object(ig.os, "open", side_effect=AssertionError("tentou abrir")) as op, \
                mock.patch.object(ig.os, "lstat", side_effect=AssertionError("tentou consultar")), \
                mock.patch.object(ig.os, "scandir", side_effect=AssertionError("tentou listar")):
            self.assertEqual(self.codigo(), "garantia_plataforma_insuficiente")
            op.assert_not_called()

    def test_deteccao_de_reparse_simulada_nao_alega_protecao_real(self):
        self.assertTrue(ig.e_ponto_de_reparse(types.SimpleNamespace(st_file_attributes=0x400)))
        self.assertTrue(ig.e_ponto_de_reparse(types.SimpleNamespace(st_file_attributes=0x420)))
        self.assertFalse(ig.e_ponto_de_reparse(types.SimpleNamespace(st_file_attributes=0x20)))
        self.assertFalse(ig.e_ponto_de_reparse(types.SimpleNamespace()))
