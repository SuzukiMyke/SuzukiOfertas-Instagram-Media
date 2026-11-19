import inspect
import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest import mock

from entrada_segura import atestado, classificacao, integridade, portao, relatorio
from entrada_segura.politica import PRODUCAO
from entrada_segura.portao import Portao, avaliar_producao
from entrada_segura.tests import suporte_sintetico as S
from entrada_segura.tests.suporte_sintetico import AGORA, INTRUSO, iso

RAIZ = Path(__file__).resolve().parents[2]
REAL = ("https://loja.com/produto/1",)


class Base(S.SemRede):
    def setUp(self):
        super().setUp()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name).resolve()
        self.lote, self.aut, self.rev = self.tmp / "lote", self.tmp / "aut", self.tmp / "rev"
        S.escrever_revogacoes(self.rev)

    def montar(self, urls=("https://www.lojaficticia.example/produto/a001",), **kw):
        self.arq = S.lote_ficticio(self.lote, urls, **kw)
        return self.arq

    def cfg(self, *, registrado=False, dados=False, produtos=False, **kw):
        conjuntos = (S.conjunto_exato(self.lote, self.arq),) if registrado else ()
        return S.config_sintetica(conjuntos=conjuntos, dados_reais_habilitado=dados, produtos_reais_habilitado=produtos, **kw)

    def avaliar(self, cfg, *, atestar=False, **kw):
        if atestar:
            S.escrever_atestado(self.aut, self.lote, self.arq, **(atestar if isinstance(atestar, dict) else {}))
        return Portao(cfg).avaliar(self.lote, self.arq, pasta_autorizacao=self.aut if atestar else None, pasta_revogacao=self.rev, **kw)

    def codigos(self, r):
        return r.decisao.codigos


class FicticioDesconhecido(Base):
    def test_ficticio_aceito_com_flags_false_e_atestado_ignorado(self):
        self.montar()
        for atestar in (False, True):
            r = self.avaliar(self.cfg(registrado=True), atestar=atestar)
            self.assertEqual((r.decisao.resultado, r.decisao.codigos), ("aceita", ("aceita_ficticio_reconhecido",)))
            self.assertEqual(r.autorizacao["resultado"], "nao_aplicavel")
            self.assertEqual(r.autorizacao["codigo"], "atestado_ignorado_ficticio" if atestar else "ficticio_nao_exige_autorizacao")
            self.assertEqual(r.bytes_verificados.keys(), set(self.arq))

    def test_ficticio_aceito_independente_das_flags(self):
        self.montar()
        for d in (False, True):
            for p in (False, True):
                self.assertEqual(self.avaliar(self.cfg(registrado=True, dados=d, produtos=p)).decisao.codigos, ("aceita_ficticio_reconhecido",))

    def test_desconhecido_sempre_recusado_mesmo_com_atestado_valido_e_flags_true(self):
        self.montar()                                       # hosts reservados SEM procedência
        for d, p in ((False, False), (True, True)):
            r = self.avaliar(self.cfg(dados=d, produtos=p), atestar=True)
            self.assertEqual((r.decisao.resultado, r.decisao.codigos), ("recusada", ("recusada_desconhecido",)))
            self.assertEqual(r.classificacao["classe"], "desconhecido")
            self.assertEqual(r.autorizacao["resultado"], "nao_aplicavel")
            self.assertEqual(r.bytes_verificados, {})

    def test_um_byte_alterado_no_lote_registrado_perde_a_procedencia(self):
        self.montar()
        cfg = self.cfg(registrado=True)
        (self.lote / "produto_A001.json").write_bytes(b'{"id":"A001","urls":["https://www.lojaficticia.example/x"]}')
        r = self.avaliar(cfg)
        self.assertEqual(r.decisao.codigos, ("recusada_desconhecido",))


class PotencialmenteReal(Base):
    def setUp(self):
        super().setUp()
        self.montar(REAL)

    def test_flags_false_recusam_mesmo_com_atestado_valido_registrado_como_evidencia(self):
        r = self.avaliar(self.cfg(), atestar=True)
        self.assertEqual(r.decisao.codigos, ("recusada_flag_global_desabilitada",))
        self.assertEqual(r.classificacao["classe"], "potencialmente_real")
        self.assertEqual(r.autorizacao["resultado"], "valida")                 # a autorização aparece SÓ no registro 2
        self.assertNotIn("valida", json.dumps(r.classificacao))
        self.assertNotIn("valida", json.dumps(r.decisao.codigos))

    def test_so_uma_flag_nao_basta(self):
        for d, p in ((True, False), (False, True)):
            r = self.avaliar(self.cfg(dados=d, produtos=p), atestar=True)
            self.assertEqual(r.decisao.codigos, ("recusada_flag_global_desabilitada",))

    def test_so_a_configuracao_sintetica_com_flags_true_e_atestado_valido_aceita(self):
        r = self.avaliar(self.cfg(dados=True, produtos=True), atestar=True)
        self.assertEqual((r.decisao.resultado, r.decisao.codigos), ("aceita", ("aceita_potencialmente_real_autorizado",)))
        self.assertEqual(r.autorizacao["resultado"], "valida")
        self.assertEqual(r.bytes_verificados.keys(), set(self.arq))

    def test_flags_true_sem_atestado_ou_com_atestado_defeituoso(self):
        cfg = self.cfg(dados=True, produtos=True)
        self.assertEqual(self.avaliar(cfg).decisao.codigos[0], "recusada_sem_autorizacao")
        casos = [("recusada_autorizacao_invalida", dict(chave=INTRUSO)), ("recusada_autorizacao_expirada", dict(validoAte=iso(AGORA - timedelta(seconds=1)))),
                 ("recusada_escopo", dict(escopo={"contrato": "1.1", "usos": ["carrossel"], "produtosMax": 10, "publicacao": True})),
                 ("recusada_autorizacao_invalida", dict(nonce="zz"))]
        for codigo, ov in casos:
            self.assertEqual(self.avaliar(cfg, atestar=ov).decisao.codigos[0], codigo, ov)

    def test_revogacao(self):
        cfg = self.cfg(dados=True, produtos=True)
        S.escrever_revogacoes(self.rev, revogados=[{"tipo": "nonce", "valor": S.NONCE, "revogadoEm": iso(AGORA), "motivo": "outro"}])
        self.assertEqual(self.avaliar(cfg, atestar=True).decisao.codigos[0], "recusada_revogada")
        S.escrever_revogacoes(self.rev)
        S.escrever_atestado(self.aut, self.lote, self.arq)
        r = Portao(replace(cfg, relogio=lambda: AGORA + timedelta(hours=13))).avaliar(self.lote, self.arq, pasta_autorizacao=self.aut, pasta_revogacao=self.rev)
        self.assertEqual(r.decisao.codigos[0], "recusada_revogacao_nao_comprovada_atual")

    def test_host_real_http_com_atestado_e_flags_false(self):
        self.montar(("http://loja.com/p",))
        r = self.avaliar(self.cfg(), atestar=True)
        self.assertEqual(r.decisao.codigos, ("recusada_flag_global_desabilitada",))
        self.assertIn("esquema_nao_https", r.classificacao["motivos"])

    def test_http_reservado_com_conjunto_sintetico_e_ficticio_sem_rede(self):
        self.montar(("http://a.example/x",))
        r = self.avaliar(self.cfg(registrado=True))                       # a trava de rede (SemRede) falharia se houvesse tentativa
        self.assertEqual(r.decisao.codigos, ("aceita_ficticio_reconhecido",))
        self.assertIn("esquema_nao_https", r.classificacao["motivos"])


class Producao(Base):
    def copiar(self, origem: str) -> tuple[Path, list[str]]:
        dest = self.tmp / "copia"
        shutil.copytree(RAIZ / origem, dest)
        arq = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
        return dest, arq

    def test_assinatura_do_ponto_de_entrada_sem_configuracao(self):
        self.assertEqual(list(inspect.signature(avaliar_producao).parameters), ["raiz_lote", "arquivos", "base_evidencia", "pasta_autorizacao", "pasta_revogacao"])

    def test_producao_usa_so_a_politica_de_producao(self):
        self.assertEqual(PRODUCAO.ancoras, frozenset())
        self.assertFalse(PRODUCAO.dados_reais_habilitado or PRODUCAO.produtos_reais_habilitado)

    def test_fixtures_historicas_registradas_sao_aceitas_com_flags_false(self):
        for origem in ("curadoria_b/exemplos_ficticios", "produtos/exemplos_ficticios_v1_1/exportacoes/A", "produtos/exemplos_ficticios_v1_1/exportacoes",
                       "orquestrador_b2/exemplos_ficticios"):
            dest, arq = self.copiar(origem)
            res = avaliar_producao(dest, arq)
            self.assertEqual((res.decisao.resultado, res.decisao.codigos), ("aceita", ("aceita_ficticio_reconhecido",)), origem)
            self.assertFalse(res.consumo_permitido)                                  # sem evidência persistida
            shutil.rmtree(dest)

    def test_fixture_adulterada_e_recusada(self):
        dest, arq = self.copiar("curadoria_b/exemplos_ficticios")
        p = dest / "ficha_valida.json"
        p.write_bytes(p.read_bytes() + b" ")
        self.assertEqual(avaliar_producao(dest, arq).decisao.codigos, ("recusada_desconhecido",))

    def test_combinacao_de_arquivos_reconhecidos_nao_e_lote_confiavel(self):
        dest = self.tmp / "mix"
        dest.mkdir()
        shutil.copy(RAIZ / "curadoria_b/exemplos_ficticios/ficha_valida.json", dest / "ficha_valida.json")
        shutil.copy(RAIZ / "orquestrador_b2/exemplos_ficticios/ficha_tecnologia_fone.json", dest / "ficha_tecnologia_fone.json")
        res = avaliar_producao(dest, ["ficha_tecnologia_fone.json", "ficha_valida.json"])
        self.assertEqual(res.decisao.codigos, ("recusada_desconhecido",))
        self.assertIn("conjunto_nao_reconhecido", res.relatorio.classificacao["motivos"])

    def test_producao_nunca_aceita_real_nem_desconhecido_nem_com_atestado_sintetico_valido(self):
        for urls, esperado in ((REAL, "recusada_flag_global_desabilitada"), (("https://a.example/x",), "recusada_desconhecido")):
            self.montar(urls)
            S.escrever_atestado(self.aut, self.lote, self.arq)                        # assinado por chave SINTÉTICA válida para a config de teste
            res = avaliar_producao(self.lote, self.arq, pasta_autorizacao=self.aut, pasta_revogacao=self.rev)
            self.assertEqual((res.decisao.resultado, res.decisao.codigos[0]), ("recusada", esperado))
            self.assertFalse(res.consumo_permitido)
            if esperado == "recusada_flag_global_desabilitada":
                self.assertEqual((res.relatorio.autorizacao["resultado"], res.relatorio.autorizacao["codigo"]), ("invalida", "ancora_desconhecida"))
            shutil.rmtree(self.lote)

    def test_atestado_valido_para_a_config_de_teste_e_invalido_em_producao(self):
        self.montar(REAL)
        S.escrever_atestado(self.aut, self.lote, self.arq)
        sintetica = Portao(self.cfg(dados=True, produtos=True)).avaliar(self.lote, self.arq, pasta_autorizacao=self.aut, pasta_revogacao=self.rev)
        self.assertEqual(sintetica.decisao.codigos, ("aceita_potencialmente_real_autorizado",))
        prod = avaliar_producao(self.lote, self.arq, pasta_autorizacao=self.aut, pasta_revogacao=self.rev)
        self.assertEqual(prod.decisao.resultado, "recusada")

    def test_producao_com_atestado_em_lote_ficticio_continua_ignorando(self):
        dest, arq = self.copiar("curadoria_b/exemplos_ficticios")
        res = avaliar_producao(dest, arq, pasta_autorizacao=self.aut)
        self.assertEqual(res.decisao.codigos, ("aceita_ficticio_reconhecido",))
        self.assertEqual(res.relatorio.autorizacao["codigo"], "atestado_ignorado_ficticio")


class Recusas(Base):
    def test_integridade(self):
        self.montar()
        (self.lote / "extra.json").write_bytes(b"{}")
        r = self.avaliar(self.cfg(registrado=True))
        self.assertEqual(r.decisao.codigos, ("recusada_integridade", "arquivo_extra"))
        self.assertIsNone(r.classificacao["classe"])
        self.assertEqual(r.autorizacao["resultado"], "nao_aplicavel")
        self.assertEqual(r.bytes_verificados, {})

    def test_plataforma_insuficiente_recusa_sem_ler(self):
        self.montar()
        with mock.patch.object(portao, "nivel_de_garantia", return_value=integridade.NivelGarantia.INSUFICIENTE), \
                mock.patch.object(portao, "ler_lote", side_effect=AssertionError("leu o lote")):
            r = self.avaliar(self.cfg(registrado=True))
        self.assertEqual(r.decisao.codigos, ("recusada_garantia_plataforma_insuficiente", "garantia_plataforma_insuficiente"))
        self.assertEqual(r.dados["plataforma"]["nivelDeGarantia"], "INSUFICIENTE")

    def test_relatorio_registra_o_nivel_e_nao_alega_protecao_windows(self):
        self.montar()
        r = self.avaliar(self.cfg(registrado=True))
        self.assertEqual(r.dados["plataforma"]["nivelDeGarantia"], "FORTE")
        self.assertNotIn("windows", json.dumps(r.dados).lower())

    def test_raiz_simbolica_recusada_pelo_portao(self):
        self.montar()
        import os
        os.symlink(self.lote, self.tmp / "link")
        r = Portao(self.cfg(registrado=True)).avaliar(self.tmp / "link", self.arq)
        self.assertEqual(r.decisao.codigos, ("recusada_integridade", "raiz_simbolica"))


class FailClosed(Base):
    def setUp(self):
        super().setUp()
        self.montar(REAL)
        S.escrever_atestado(self.aut, self.lote, self.arq)

    def rodar(self):
        return Portao(self.cfg(dados=True, produtos=True)).avaliar(self.lote, self.arq, pasta_autorizacao=self.aut, pasta_revogacao=self.rev)

    def test_excecao_injetada_em_cada_etapa(self):
        for alvo in ("ler_lote", "classificar"):
            with mock.patch.object(portao, alvo, side_effect=RuntimeError("injetado")):
                self.assertEqual(self.rodar().decisao.codigos, ("recusada_erro_interno",), alvo)
        with mock.patch.object(portao, "nivel_de_garantia", side_effect=RuntimeError("injetado")):
            self.assertEqual(self.rodar().decisao.codigos, ("recusada_erro_interno",))
        with mock.patch.object(portao.atestado, "avaliar", side_effect=RuntimeError("injetado")):
            self.assertEqual(self.rodar().decisao.codigos, ("recusada_erro_interno",))
        with mock.patch.object(atestado.assinatura, "verificar", side_effect=RuntimeError("injetado")):
            self.assertEqual(self.rodar().decisao.codigos[0], "recusada_erro_interno")
        with mock.patch.object(portao.rel, "montar", side_effect=RuntimeError("injetado")):
            r = self.rodar()
            self.assertEqual(r.decisao.codigos, ("recusada_erro_interno",))

    def test_excecao_no_relatorio_em_producao(self):
        with mock.patch.object(portao.rel, "montar", side_effect=RuntimeError("injetado")):
            res = avaliar_producao(self.lote, self.arq, base_evidencia=self.tmp)
        self.assertEqual(res.decisao.codigos, ("recusada_erro_interno",))
        self.assertFalse(res.consumo_permitido)

    def test_relogio_invalido(self):
        for relogio in (lambda: None, lambda: AGORA.replace(tzinfo=None), lambda: (_ for _ in ()).throw(RuntimeError("x"))):
            r = Portao(self.cfg(relogio=relogio)).avaliar(self.lote, self.arq)
            self.assertEqual(r.decisao.codigos, ("recusada_erro_interno",))

    def test_entradas_hostis_nao_travam_nem_aceitam(self):
        casos = {"json_gigante": b'{"a":"' + b"x" * (2 * 1024 * 1024 + 10) + b'"}', "aninhado": b"[" * 100000 + b"]" * 100000, "aleatorio": bytes(range(256)) * 50,
                 "nulos": b"\x00" * 1000, "vazio": b""}
        for nome, conteudo in casos.items():
            lote = self.tmp / f"hostil_{nome}"
            lote.mkdir()
            (lote / "x.json").write_bytes(conteudo)
            r = Portao(self.cfg()).avaliar(lote, ["x.json"])
            self.assertEqual(r.decisao.resultado, "recusada", nome)
            self.assertEqual(r.bytes_verificados, {}, nome)


class Registros(Base):
    def test_tres_registros_separados_sempre_presentes(self):
        self.montar(REAL)
        for r in (self.avaliar(self.cfg(), atestar=True), self.avaliar(self.cfg(dados=True, produtos=True), atestar=True)):
            self.assertTrue({"classificacao", "autorizacao", "decisao"} <= set(r.dados))
            self.assertEqual(set(r.classificacao), {"classe", "motivos", "hostsAvaliados", "totalHosts", "conjunto"})
            self.assertEqual(set(r.autorizacao), {"resultado", "codigo", "aplicavel", "fingerprint", "nonce", "validoAte", "revogacao"})
            self.assertEqual(set(r.dados["decisao"]), {"resultado", "codigos"})

    def test_classificacao_nao_depende_da_autorizacao(self):
        self.montar(REAL)
        sem = self.avaliar(self.cfg()).classificacao
        com = self.avaliar(self.cfg(), atestar=True).classificacao
        puro = classificacao.classificar({a: (self.lote / a).read_bytes() for a in self.arq}, self.cfg())
        self.assertEqual(sem, com)
        self.assertEqual(sem["classe"], puro.classe)

    def test_relogio_lido_uma_vez(self):
        self.montar()
        n = []
        cfg = self.cfg(registrado=True, relogio=lambda: n.append(1) or AGORA)
        Portao(cfg).avaliar(self.lote, self.arq)
        self.assertEqual(len(n), 1)
        n.clear()
        with mock.patch.object(portao, "PRODUCAO", replace(PRODUCAO, relogio=lambda: n.append(1) or AGORA)):
            avaliar_producao(self.lote, self.arq)
        self.assertEqual(len(n), 1)

    def test_relatorio_deterministico_sem_caminhos_absolutos_nem_urls_completas(self):
        self.montar(("https://loja.com/segredo?token=abc", "http://a.example/x"))
        a = relatorio.serializar(self.avaliar(self.cfg(), atestar=True))
        b = relatorio.serializar(self.avaliar(self.cfg(), atestar=True))
        self.assertEqual(a, b)
        texto = a.decode()
        for proibido in (str(self.tmp), "https://", "http://", "token", "segredo", "PRIVATE KEY", "/tmp/"):
            self.assertNotIn(proibido, texto)
        self.assertIn("loja.com", texto)

    def test_relatorio_dispensa_hash_do_diretorio_de_evidencia(self):
        self.montar()
        r = self.avaliar(self.cfg(registrado=True))
        self.assertNotIn("execucao-", relatorio.serializar(r).decode())
