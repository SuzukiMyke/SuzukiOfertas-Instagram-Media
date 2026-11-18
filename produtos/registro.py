"""Deduplicação, histórico e arquivamento (GOAL 5.4).

Chave: ``provider + product.id``. Vale o ``exportedAt`` mais recente (empate: maior ``exportId``,
determinístico). Versões antigas ficam no histórico — nada é descartado em silêncio. Arquivos com
mais de ``arquivo_dias`` são **arquivados** (listados, nunca reutilizados automaticamente).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .leitor import Lido
from .tempo import parse_data


@dataclass
class Versao:
    arquivo: str
    sha256: str
    dados: dict
    exportada_em: datetime

    @property
    def export_id(self) -> str:
        return self.dados["exportId"]

    @property
    def chave(self) -> tuple[str, str]:
        p = self.dados["product"]
        return p["provider"], p["id"]

    @property
    def centavos(self) -> int | None:           # None só na curadoria manual (preço nulo, contrato 1.1)
        return self.dados["price"]["amountCents"]

    def resumo(self, situacao: str) -> dict:
        d = self.dados
        return {"exportId": self.export_id, "exportedAt": d["exportedAt"], "arquivo": self.arquivo,
                "sha256": self.sha256, "fonte": d["source"]["kind"], "amountCents": self.centavos,
                "currency": d["price"]["currency"], "situacao": situacao}


@dataclass
class Produto:
    chave: tuple[str, str]
    versoes: list[Versao]             # ordenadas da mais recente para a mais antiga (inclui arquivadas)
    arquivadas: set[str] = field(default_factory=set)   # exportIds arquivados

    @property
    def vigente(self) -> Versao:
        return self.versoes[0]


@dataclass
class Registro:
    produtos: dict[tuple[str, str], Produto]
    arquivados: list[dict]            # produtos cujas versões estão todas arquivadas
    duplicatas_export_id: list[dict]

    def historico(self) -> list[dict]:
        saida = []
        for chave in sorted(list(self.produtos) + [(a["provider"], a["productId"]) for a in self.arquivados]):
            if chave in self.produtos:
                p = self.produtos[chave]
                itens = [v.resumo("vigente" if i == 0 else "substituida") if v.export_id not in p.arquivadas
                         else v.resumo("arquivada") for i, v in enumerate(p.versoes)]
                saida.append({"provider": chave[0], "productId": chave[1], "versoes": itens})
        for a in self.arquivados:
            saida.append({"provider": a["provider"], "productId": a["productId"], "versoes": a["versoes"]})
        saida.sort(key=lambda h: (h["provider"], h["productId"]))
        return saida


def montar(lidos: list[Lido], agora: datetime, *, arquivo_dias: int | None = 30) -> Registro:
    corte = agora - timedelta(days=arquivo_dias) if arquivo_dias else None
    vistos: dict[str, Versao] = {}
    duplicatas: list[dict] = []
    for l in lidos:                                   # lidos já vêm ordenados por nome de arquivo
        v = Versao(l.arquivo, l.sha256, l.dados, parse_data(l.dados["exportedAt"]))
        if v.export_id in vistos:
            duplicatas.append({"exportId": v.export_id, "mantido": vistos[v.export_id].arquivo,
                               "descartado": v.arquivo,
                               "conteudoIgual": vistos[v.export_id].sha256 == v.sha256})
            continue
        vistos[v.export_id] = v

    grupos: dict[tuple[str, str], list[Versao]] = {}
    for v in vistos.values():
        grupos.setdefault(v.chave, []).append(v)

    produtos: dict[tuple[str, str], Produto] = {}
    arquivados: list[dict] = []
    for chave, vs in grupos.items():
        vs.sort(key=lambda v: (v.exportada_em, v.export_id), reverse=True)
        arq = {v.export_id for v in vs if corte and v.exportada_em < corte}
        if len(arq) == len(vs):
            arquivados.append({"provider": chave[0], "productId": chave[1],
                               "motivo": f"todas as versões com mais de {arquivo_dias} dias",
                               "versoes": [v.resumo("arquivada") for v in vs]})
            continue
        # versões arquivadas ficam só no histórico; vigente = a mais recente não arquivada
        ativas = [v for v in vs if v.export_id not in arq]
        resto = [v for v in vs if v.export_id in arq]
        produtos[chave] = Produto(chave, ativas + resto, arq)
    return Registro(produtos, sorted(arquivados, key=lambda a: (a["provider"], a["productId"])), duplicatas)
