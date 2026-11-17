"""Modo 1.1: portão de pré-publicação/agendamento (§6) e política de títulos (§7.1)."""
import unittest
from datetime import timedelta

from produtos import prepublicacao as pp
from produtos.politica_titulos import ALTA, MEDIA, NENHUM, avaliar_titulo, identificacao_para_peca
from produtos.tests.base import AGORA, Base


def ficha(**over):
    f = {"origem": "A", "preco": {"amountCents": 1000, "verifiedAt": "2026-11-17T14:00:00Z", "validUntil": "2026-11-17T20:00:00Z",
                                  "verification": "ao_vivo"}, "availability": "in_stock"}
    f["preco"].update(over.pop("preco", {}))
    f.update(over)
    return f


PRECO = {"id": "p", "tipo": "preco", "funcao": "essencial", "tem_variante_sem": False}
CTA = {"id": "c", "tipo": "oferta", "funcao": "acessoria", "tem_variante_sem": True}
CTA_SEM_VARIANTE = {**CTA, "tem_variante_sem": False}


def portao(f=None, t=AGORA, alegacoes=(PRECO,), aprovado=1000, **kw):
    return pp.avaliar_portao(f or ficha(), preco_aprovado_centavos=aprovado, t_publicacao=t, alegacoes=list(alegacoes), **kw)


class PortaoTest(Base):
    def test_liberar_publicacao_imediata_dentro_da_janela(self):
        r = portao()
        self.assertEqual((r["acao"], r["alegacoes_comerciais"]), (pp.LIBERAR, ["p"]))
        self.assertEqual(r["valido_ate"], "2026-11-17T20:00:00Z")

    def test_margem_e_limite_inclusivo(self):
        fim = AGORA + timedelta(hours=5)                         # 20:00
        self.assertEqual(portao(t=fim - timedelta(minutes=30))["acao"], pp.LIBERAR)
        self.assertEqual(portao(t=fim - timedelta(minutes=30) + timedelta(seconds=1))["acao"], pp.BLOQUEAR)
        self.assertEqual(portao(t=fim - timedelta(minutes=10), margem_min=10)["acao"], pp.LIBERAR)

    def test_agendamento_avalia_o_horario_efetivo_e_deve_ser_reavaliado(self):
        self.assertEqual(portao(t=AGORA + timedelta(hours=1))["acao"], pp.LIBERAR)
        r = portao(t=AGORA + timedelta(hours=8))                 # mesmo preço, horário agendado depois da janela
        self.assertEqual(r["acao"], pp.BLOQUEAR)
        self.assertEqual(r["avaliado_para"], "2026-11-17T23:00:00Z")

    def test_teto_de_24h_vale_mesmo_com_validuntil_maior(self):
        f = ficha(preco={"verifiedAt": "2026-11-17T10:00:00Z", "validUntil": "2026-11-20T10:00:00Z"})
        self.assertEqual(pp.janela_comercial(f["preco"]).strftime("%Y-%m-%dT%H:%M:%SZ"), "2026-11-18T10:00:00Z")
        self.assertEqual(portao(f, t=AGORA + timedelta(hours=20))["acao"], pp.BLOQUEAR)

    def test_alegacao_acessoria_e_omitida_se_ha_variante_e_bloqueada_se_nao_ha(self):
        r = portao(t=AGORA + timedelta(hours=9), alegacoes=(CTA,))
        self.assertEqual((r["acao"], r["alegacoes_comerciais"]), (pp.OMITIR, []))
        self.assertEqual(portao(t=AGORA + timedelta(hours=9), alegacoes=(CTA_SEM_VARIANTE,))["acao"], pp.BLOQUEAR)

    def test_essencial_bloqueia_mesmo_com_acessoria_omissivel(self):
        self.assertEqual(portao(t=AGORA + timedelta(hours=9), alegacoes=(PRECO, CTA))["acao"], pp.BLOQUEAR)

    def test_condicoes_de_falha(self):
        casos = [dict(f=ficha(origem="B")), dict(f=ficha(preco={"verification": "catalogo_sem_verificacao"})),
                 dict(f=ficha(availability="out_of_stock")), dict(aprovado=999), dict(aprovado=None),
                 dict(f=ficha(preco={"validUntil": None}))]
        for kw in casos:
            self.assertEqual(portao(**kw)["acao"], pp.BLOQUEAR, kw)

    def test_menor_preco_exige_prova_explicita(self):
        mp = {"id": "m", "tipo": "menor_preco", "funcao": "acessoria", "tem_variante_sem": True}
        self.assertEqual(portao(alegacoes=(PRECO, mp))["acao"], pp.OMITIR)
        self.assertEqual(portao(alegacoes=(PRECO, mp), prova_menor_preco=True)["alegacoes_comerciais"], ["p", "m"])

    def test_sem_alegacao_comercial_libera_vazio(self):
        r = portao(f=ficha(origem="B"), alegacoes=())
        self.assertEqual((r["acao"], r["alegacoes_comerciais"]), (pp.LIBERAR, []))

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            pp.avaliar_portao(ficha(), preco_aprovado_centavos=1000, t_publicacao=AGORA.replace(tzinfo=None), alegacoes=[])
        with self.assertRaises(ValueError):
            portao(alegacoes=({"id": "x", "tipo": "preco", "funcao": "talvez"},))

    def test_funcao_pura_nao_altera_a_ficha(self):
        f = ficha()
        import copy
        antes = copy.deepcopy(f)
        portao(f)
        self.assertEqual(f, antes)


class TitulosTest(Base):
    def test_niveis(self):
        self.assertEqual(avaliar_titulo("Panela de Pressão 5L")["nivel"], NENHUM)
        for t in ("Fone Original Premium", "Kit GRÁTIS", "Chaleira em oferta", "Sérum emagrece rápido", "Produto Nº 1 do país",
                  "Menor preço garantido", "Item exclusivo Inmetro", "Tênis 50% OFF"):
            self.assertEqual(avaliar_titulo(t)["nivel"], ALTA, t)
        for t in ("Power bank 10000 mAh", "SSD 512 GB", "Fone potente", "Caixa à prova d'água", "Garrafa 100% inox", "Carregador 65W"):
            self.assertEqual(avaliar_titulo(t)["nivel"], MEDIA, t)

    def test_alta_prevalece_sobre_media_e_nao_ha_falso_positivo_de_palavra_parcial(self):
        self.assertEqual(avaliar_titulo("Fone potente original")["nivel"], ALTA)
        self.assertEqual(avaliar_titulo("Organizador oficinal")["nivel"], NENHUM)

    def test_identificacao_na_peca(self):
        self.assertEqual(identificacao_para_peca("Panela", "Casa > Panelas", "Loja X")["acao"], "usar_titulo")
        m = identificacao_para_peca("Fone potente", "Eletrônicos > Fones", "Loja X")
        self.assertEqual((m["acao"], m["revisaoHumanaObrigatoria"]), ("usar_titulo", True))
        a = identificacao_para_peca("Fone ORIGINAL", "Eletrônicos > Fones", "Loja X")
        self.assertEqual((a["acao"], a["texto"]), ("variante_sem_titulo", "Fones na Loja X"))
        self.assertEqual(identificacao_para_peca("Fone ORIGINAL", None, "Loja X")["acao"], "bloquear")

    def test_titulo_nunca_e_editado(self):
        self.assertEqual(identificacao_para_peca("Panela 5L", None, "L")["texto"], "Panela 5L")


if __name__ == "__main__":
    unittest.main()
