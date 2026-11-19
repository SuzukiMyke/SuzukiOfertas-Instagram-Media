import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest import mock

from entrada_segura import assinatura, atestado, canonico, integridade, revogacao
from entrada_segura.assinatura import PREFIXO_ATESTADO, PREFIXO_REVOGACOES
from entrada_segura.erros import ErroRevogacao
from entrada_segura.politica import PRODUCAO
from entrada_segura.tests import suporte_sintetico as S
from entrada_segura.tests.suporte_sintetico import AGORA, ANCORA1, ANCORA2, INTRUSO, REMOVER, iso


class Base(S.SemRede):
    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name).resolve()
        self.lote, self.aut, self.rev = self.tmp / "lote", self.tmp / "aut", self.tmp / "rev"
        self.arq = S.lote_ficticio(self.lote)
        self.cfg = S.config_sintetica()
        S.escrever_revogacoes(self.rev)

    def lido(self):
        return integridade.ler_lote(self.lote, self.arq, self.cfg)

    def avaliar(self, cfg=None, agora=AGORA, aut=True, rev=True):
        return atestado.avaliar(self.aut if aut else None, self.rev if rev else None, self.lido(), cfg or self.cfg, agora)

    def atestar(self, **kw):
        return S.escrever_atestado(self.aut, self.lote, self.arq, **kw)

    def esperar(self, resultado, codigo, **kw):
        r = self.avaliar(**kw)
        self.assertEqual((r.resultado, r.codigo), (resultado, codigo), r)
        self.assertNotEqual(r.resultado, "valida")
        return r


class Valido(Base):
    def test_atestado_valido(self):
        self.atestar()
        r = self.avaliar()
        self.assertEqual((r.resultado, r.codigo, r.aplicavel), ("valida", "autorizacao_valida", True))
        self.assertEqual((r.fingerprint, r.nonce), (ANCORA1.fingerprint, S.NONCE))
        self.assertEqual(r.revogacao, {"estado": "atual", "sequencia": 5, "frescorAte": iso(AGORA + timedelta(hours=12))})

    def test_em_producao_a_ancora_vazia_invalida_qualquer_atestado(self):
        self.atestar()
        r = self.avaliar(cfg=replace(PRODUCAO, relogio=lambda: AGORA))
        self.assertEqual((r.resultado, r.codigo), ("invalida", "ancora_desconhecida"))

    def test_nunca_levanta_excecao(self):
        self.atestar()
        with mock.patch.object(assinatura, "verificar", side_effect=RuntimeError("x")):
            self.esperar("invalida", "erro_interno")


class Assinatura(Base):
    def test_assinatura_chave_e_dominio(self):
        self.atestar(chave=INTRUSO)
        self.esperar("invalida", "ancora_desconhecida")
        doc, _ = self.atestar()
        flip = doc.replace(S.NONCE.encode(), (("cd") * 16).encode())
        self.atestar(doc_bytes=flip, sig_bytes=ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, doc))
        self.esperar("invalida", "assinatura_invalida")
        self.atestar(sig_bytes=ANCORA1.arquivo_assinatura(PREFIXO_REVOGACOES, doc))                # assinatura de OUTRO domínio
        self.esperar("invalida", "assinatura_invalida")

    def test_fingerprint_do_campo_diferente_da_chave(self):
        self.atestar(aprovadorFingerprint=ANCORA2.fingerprint)
        self.esperar("invalida", "fingerprint_divergente")

    def test_algoritmo_e_arquivo_de_assinatura(self):
        doc, _ = self.atestar()
        self.atestar(sig_bytes=ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, doc, algoritmo="rsa"))
        self.esperar("invalida", "algoritmo_ou_versao")
        self.atestar(sig_bytes=b"lixo")
        self.esperar("invalida", "assinatura_nao_canonica")

    def test_dependencia_ausente(self):
        self.atestar()
        with mock.patch.object(assinatura, "_importar_cripto", side_effect=ImportError("simulado")):
            self.esperar("invalida", "dependencia_ausente")


class Alvo(Base):
    def test_lote_alterado_depois_do_atestado(self):
        self.atestar()
        (self.lote / "produto_A001.json").write_bytes(b'{"id":"A001","outro":1}')
        self.esperar("invalida", "lote_diferente")

    def test_arquivo_a_mais_ou_a_menos(self):
        self.atestar()
        (self.lote / "extra.json").write_bytes(b"{}")
        self.arq.append("extra.json")
        self.esperar("invalida", "lote_diferente")
        self.arq.remove("extra.json")
        (self.lote / "extra.json").unlink()
        self.atestar(arquivos=S.hashes_do_lote(self.lote, self.arq)[:-1])
        self.esperar("invalida", "lote_diferente")

    def test_ordem_ou_duplicata_na_lista_de_arquivos(self):
        h = S.hashes_do_lote(self.lote, self.arq)
        self.atestar(arquivos=list(reversed(h)))
        self.esperar("invalida", "arquivos_invalidos")
        self.atestar(arquivos=h + [h[-1]])
        self.esperar("invalida", "arquivos_invalidos")

    def test_hash_ou_bytes_diferentes(self):
        h = S.hashes_do_lote(self.lote, self.arq)
        h[0] = {**h[0], "sha256": "f" * 64}
        self.atestar(arquivos=h)
        self.esperar("invalida", "lote_diferente")
        h = S.hashes_do_lote(self.lote, self.arq)
        h[0] = {**h[0], "bytes": h[0]["bytes"] + 1}
        self.atestar(arquivos=h)
        self.esperar("invalida", "lote_diferente")

    def test_manifesto(self):
        self.atestar(manifestoSha256="0" * 64)
        self.esperar("invalida", "manifesto_divergente")
        self.atestar(manifestoSha256="XYZ")
        self.esperar("invalida", "manifesto_sha_invalido")

    def test_lote_sem_manifesto(self):
        lote2, aut2 = self.tmp / "lote2", self.tmp / "aut2"
        arq2 = S.lote_ficticio(lote2, manifesto=False)
        S.escrever_atestado(aut2, lote2, arq2)
        lido = integridade.ler_lote(lote2, arq2, self.cfg)
        r = atestado.avaliar(aut2, self.rev, lido, self.cfg, AGORA)
        self.assertEqual((r.resultado, r.codigo), ("invalida", "manifesto_ausente"))


class Escopo(Base):
    def test_escopo(self):
        ok = {"contrato": "1.1", "usos": ["carrossel"], "produtosMax": 10, "publicacao": False}
        self.atestar(escopo=ok)
        self.assertEqual(self.avaliar().resultado, "valida")
        for usos in (["carrossel", "reels", "story"], ["story"]):
            self.atestar(escopo={**ok, "usos": usos})
            self.assertEqual(self.avaliar().resultado, "valida")
        for nome, esc in {"desconhecido": {**ok, "usos": ["publicar"]}, "vazio": {**ok, "usos": []}, "repetido": {**ok, "usos": ["story", "story"]},
                          "publicacao_true": {**ok, "publicacao": True}, "publicacao_ausente": {k: v for k, v in ok.items() if k != "publicacao"},
                          "contrato": {**ok, "contrato": "1.0"}, "max_zero": {**ok, "produtosMax": 0}, "max_alto": {**ok, "produtosMax": 1001},
                          "max_bool": {**ok, "produtosMax": True}, "campo_extra": {**ok, "extra": 1}, "nao_objeto": "x", "usos_str": {**ok, "usos": "carrossel"}}.items():
            self.atestar(escopo=esc)
            r = self.avaliar()
            self.assertEqual((r.resultado, r.codigo), ("invalida", "escopo_invalido"), nome)

    def test_escopo_ausente(self):
        self.atestar(escopo=REMOVER)
        self.esperar("invalida", "campos_invalidos")


class Validade(Base):
    def test_vencido_e_limite_de_7_dias(self):
        self.atestar(validoAte=iso(AGORA - timedelta(seconds=1)))
        self.esperar("expirada", "atestado_expirado")
        self.atestar(validoAte=iso(AGORA))                                                           # exatamente agora: ainda válido
        self.assertEqual(self.avaliar().resultado, "valida")
        e = AGORA - timedelta(hours=1)
        self.atestar(emitidoEm=iso(e), validoAte=iso(e + timedelta(days=7)))
        self.assertEqual(self.avaliar().resultado, "valida")
        self.atestar(emitidoEm=iso(e), validoAte=iso(e + timedelta(days=7, seconds=1)))
        self.esperar("invalida", "janela_excedida")
        self.atestar(emitidoEm=iso(AGORA - timedelta(hours=1)), validoAte=iso(AGORA - timedelta(hours=1)))
        self.esperar("expirada", "atestado_expirado")

    def test_valido_ate_antes_de_emitido(self):
        self.atestar(emitidoEm=iso(AGORA + timedelta(days=1)), validoAte=iso(AGORA + timedelta(days=2)))
        self.esperar("invalida", "relogio_no_futuro")

    def test_emitido_no_futuro_com_tolerancia_zero(self):
        self.atestar(emitidoEm=iso(AGORA))
        self.assertEqual(self.avaliar().resultado, "valida")
        self.atestar(emitidoEm=iso(AGORA + timedelta(seconds=1)))
        self.esperar("invalida", "relogio_no_futuro")
        self.assertEqual(self.avaliar(cfg=replace(self.cfg, tolerancia_relogio=timedelta(seconds=1))).resultado, "valida")

    def test_relogio_no_futuro_expira(self):
        self.atestar()
        self.esperar("expirada", "atestado_expirado", agora=AGORA + timedelta(days=3))

    def test_datas_malformadas(self):
        for v in ("2026-11-20", "2026-11-20T12:00:00", "2026-11-20T12:00:00+00:00", "2026-13-40T12:00:00Z", "", 5):
            self.atestar(validoAte=v)
            self.esperar("invalida", "data_invalida")


class Campos(Base):
    def test_campos_tipos_e_forma(self):
        casos = {"nonce_ausente": dict(nonce=REMOVER), "nonce_curto": dict(nonce="ab" * 15), "nonce_maiusculo": dict(nonce="AB" * 16), "nonce_longo": dict(nonce="ab" * 33),
                 "campo_extra": dict(extra="x"), "tipo": dict(tipo="outra_coisa"), "versao": dict(schemaVersion="2"), "regras": dict(versaoRegras="19"),
                 "declaracao": dict(declaracao="Eu autorizo"), "lote_id": dict(loteId="com espaço"), "fp": dict(aprovadorFingerprint="abc")}
        for nome, ov in casos.items():
            self.atestar(**ov)
            r = self.avaliar()
            self.assertEqual(r.resultado, "invalida", nome)
            self.assertIn(r.codigo, {"campos_invalidos", "nonce_invalido", "tipo_ou_versao_invalidos", "declaracao_invalida", "lote_id_invalido", "fingerprint_invalido"}, nome)

    def test_json_nao_canonico_ou_ilegivel(self):
        doc, _ = self.atestar()
        for ruim in (doc + b"\n", doc.replace(b",", b", ", 1), b"{", b"", b"[]"):
            self.atestar(doc_bytes=ruim, sig_bytes=ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, ruim))
            r = self.avaliar()
            self.assertEqual(r.resultado, "invalida")
            self.assertIn(r.codigo, {"nao_canonico", "campos_invalidos"})

    def test_pasta_ausente_ou_com_extras(self):
        self.esperar("invalida", "autorizacao_ausente", aut=False)
        self.aut.mkdir()
        self.esperar("invalida", "autorizacao_ausente")
        self.atestar()
        (self.aut / "extra.txt").write_bytes(b"x")
        self.esperar("invalida", "autorizacao_ilegivel")

    def test_atestado_nao_e_transferivel(self):
        self.atestar()
        outra = self.tmp / "outro_lote"
        arq2 = S.lote_ficticio(outra, urls=("https://www.outra.example/a",))
        lido = integridade.ler_lote(outra, arq2, self.cfg)
        r = atestado.avaliar(self.aut, self.rev, lido, self.cfg, AGORA)
        self.assertEqual((r.resultado, r.codigo), ("invalida", "lote_diferente"))


class Revogacoes(Base):
    def carregar(self, agora=AGORA, cfg=None):
        return revogacao.carregar(self.rev, cfg or self.cfg, agora)

    def erro(self, **kw):
        with self.assertRaises(ErroRevogacao) as cm:
            self.carregar(**kw)
        return cm.exception.codigo

    def test_lista_valida(self):
        L = self.carregar()
        self.assertEqual((L.sequencia, L.valido_ate), (5, iso(AGORA + timedelta(hours=12))))

    def test_nonce_e_hash_revogados(self):
        self.atestar()
        S.escrever_revogacoes(self.rev, revogados=[{"tipo": "nonce", "valor": S.NONCE, "revogadoEm": iso(AGORA), "motivo": "erro_de_revisao"}])
        self.esperar("revogada", "revogada")
        man = S.sha((self.lote / "manifest.json").read_bytes())
        S.escrever_revogacoes(self.rev, revogados=[{"tipo": "sha256", "valor": man, "revogadoEm": iso(AGORA), "motivo": "lote_substituido"}])
        self.esperar("revogada", "revogada")
        arq = S.sha((self.lote / "produto_A001.json").read_bytes())
        S.escrever_revogacoes(self.rev, revogados=[{"tipo": "sha256", "valor": arq, "revogadoEm": iso(AGORA), "motivo": "outro"}])
        self.esperar("revogada", "revogada")
        S.escrever_revogacoes(self.rev, revogados=[{"tipo": "nonce", "valor": "cd" * 16, "revogadoEm": iso(AGORA), "motivo": "outro"}])   # outro nonce: não afeta
        self.assertEqual(self.avaliar().resultado, "valida")

    def test_lista_ausente_ilegivel_invalida_ou_de_outra_chave(self):
        self.atestar()
        self.esperar("revogacao_nao_comprovada_atual", "lista_ausente", rev=False)
        import shutil
        shutil.rmtree(self.rev)
        self.esperar("revogacao_nao_comprovada_atual", "lista_ausente")
        S.escrever_revogacoes(self.rev, chave=INTRUSO)
        self.esperar("revogacao_nao_comprovada_atual", "ancora_desconhecida")
        S.escrever_revogacoes(self.rev, doc_bytes=b"{", sig_bytes=b"{")
        self.esperar("revogacao_nao_comprovada_atual", "lista_nao_canonica")
        (self.rev / "extra").write_bytes(b"x")
        self.esperar("revogacao_nao_comprovada_atual", "lista_ilegivel")

    def test_carimbo_vencido_e_janela(self):
        self.assertEqual(self.erro(agora=AGORA + timedelta(hours=12, seconds=1)), "carimbo_vencido")
        self.assertEqual(self.carregar(agora=AGORA + timedelta(hours=12)).sequencia, 5)
        e = AGORA - timedelta(hours=1)
        S.escrever_revogacoes(self.rev, emitidoEm=iso(e), validoAte=iso(e + timedelta(hours=24)))
        self.assertEqual(self.carregar().sequencia, 5)
        S.escrever_revogacoes(self.rev, emitidoEm=iso(e), validoAte=iso(e + timedelta(hours=24, seconds=1)))
        self.assertEqual(self.erro(), "janela_excedida")
        S.escrever_revogacoes(self.rev, emitidoEm=iso(AGORA), validoAte=iso(AGORA))
        self.assertEqual(self.erro(), "janela_excedida")

    def test_nao_comprovada_atual_no_atestado(self):
        self.atestar()
        self.esperar("revogacao_nao_comprovada_atual", "carimbo_vencido", agora=AGORA + timedelta(hours=13))

    def test_sequencia_regressiva_e_relogio_no_futuro(self):
        self.assertEqual(self.erro(cfg=replace(self.cfg, sequencia_minima_revogacao=6)), "sequencia_regressiva")
        self.assertEqual(self.carregar(cfg=replace(self.cfg, sequencia_minima_revogacao=5)).sequencia, 5)
        S.escrever_revogacoes(self.rev, emitidoEm=iso(AGORA + timedelta(seconds=1)))
        self.assertEqual(self.erro(), "relogio_no_futuro")
        S.escrever_revogacoes(self.rev, emitidoEm=iso(AGORA))
        self.assertEqual(self.carregar().sequencia, 5)

    def test_dominios_nao_se_misturam(self):
        doc, _ = self.atestar()
        S.escrever_revogacoes(self.rev, sig_bytes=ANCORA1.arquivo_assinatura(PREFIXO_ATESTADO, canonico.serializar(S.dados_revogacoes())))  # assinatura de ATESTADO como lista
        self.assertEqual(self.erro(), "assinatura_invalida")
        S.escrever_revogacoes(self.rev)
        self.atestar(sig_bytes=ANCORA1.arquivo_assinatura(PREFIXO_REVOGACOES, doc))                                                     # assinatura de LISTA como atestado
        self.esperar("invalida", "assinatura_invalida")

    def test_campos_da_lista(self):
        casos = {"seq_negativa": dict(sequencia=-1), "seq_bool": dict(sequencia=True), "seq_texto": dict(sequencia="5"), "tipo": dict(tipo="x"), "extra": dict(extra=1),
                 "sem_revogados": dict(revogados=REMOVER), "item_ruim": dict(revogados=[{"tipo": "x"}]),
                 "motivo_livre": dict(revogados=[{"tipo": "nonce", "valor": "ab" * 16, "revogadoEm": iso(AGORA), "motivo": "porque sim"}]),
                 "valor_curto": dict(revogados=[{"tipo": "sha256", "valor": "ab", "revogadoEm": iso(AGORA), "motivo": "outro"}]),
                 "duplicado": dict(revogados=[{"tipo": "nonce", "valor": "ab" * 16, "revogadoEm": iso(AGORA), "motivo": "outro"}] * 2),
                 "fp_ruim": dict(aprovadorFingerprint="x"), "data": dict(emitidoEm="ontem")}
        for nome, ov in casos.items():
            S.escrever_revogacoes(self.rev, **ov)
            with self.assertRaises(ErroRevogacao, msg=nome):
                self.carregar()

    def test_fingerprint_do_campo_diferente_da_chave(self):
        S.escrever_revogacoes(self.rev, aprovadorFingerprint=ANCORA2.fingerprint)
        self.assertEqual(self.erro(), "fingerprint_divergente")

    def test_nenhum_estado_persistente_e_criado(self):
        antes = sorted(p.name for p in self.tmp.rglob("*"))
        self.carregar()
        self.carregar()
        self.assertEqual(sorted(p.name for p in self.tmp.rglob("*")), antes)

    def test_revalidacao_a_cada_avaliacao(self):
        """Lote aceito em T0; lista nova com revogação em T1 ⇒ a nova avaliação recusa (revalidação, sem garantia de instantaneidade)."""
        self.atestar()
        self.assertEqual(self.avaliar().resultado, "valida")
        S.escrever_revogacoes(self.rev, sequencia=6, revogados=[{"tipo": "nonce", "valor": S.NONCE, "revogadoEm": iso(AGORA), "motivo": "autorizacao_retirada"}])
        self.assertEqual(self.avaliar(agora=AGORA + timedelta(minutes=1)).resultado, "revogada")
