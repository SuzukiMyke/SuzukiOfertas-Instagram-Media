"""Orquestração do modo 1.1 (adoção EXPLÍCITA; contrato v1.1 §11). O modo 1.0 (``pipeline.processar``) não muda.

Entrada: pasta de exportações com ``A/`` e ``B/`` (cada uma com o seu ``manifest.json``), somente leitura; arquivos humanos
somente leitura (``decisoes.json``, ``permissoes_fotos.json``, ``termos_programas.json``) e pasta do repositório de fotos
(somente leitura). Saída: fichas e relatórios numa pasta própria, que **nunca** pode ficar dentro de nenhuma entrada (S2).

O que NÃO existe e continua desabilitado: reverificação do preço no instante da publicação; verificação de autoria
dos commits (S3, ``nao_verificavel``); importador de fotos; exportador do agente.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import decisoes as dec, estados, permissoes, registro
from .avaliacao_v11 import ConfiguracaoV11, avaliar_v11
from .fichas import nome_arquivo
from .fichas_v11 import montar_v11, para_markdown_v11
from .leitor_v11 import LETRAS, ler_lote
from .tempo import formatar

_HEX = re.compile(r"^[0-9a-f]{7,40}$")
REPOS_COMMIT = ("dados", "decisoes", "fotos")


def _dentro(a: Path, b: Path) -> bool:
    a, b = a.resolve(), b.resolve()
    return a == b or b in a.parents


def _gravar_json(caminho: Path, obj) -> None:
    caminho.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def processar_v11(exportacoes: Path | str, saida: Path | str, agora: datetime, *,
                  decisoes_arquivo=None, permissoes_arquivo=None, termos_arquivo=None, fotos_dir=None,
                  cfg: ConfiguracaoV11 | None = None, commits_lidos: dict | None = None) -> dict:
    cfg = cfg or ConfiguracaoV11()
    if cfg.contrato != "1.1":
        raise ValueError("processar_v11 exige ConfiguracaoV11 (contrato 1.1)")
    exportacoes, saida = Path(exportacoes), Path(saida)
    entradas = [exportacoes] + [Path(x) for x in (decisoes_arquivo, permissoes_arquivo, termos_arquivo, fotos_dir) if x]
    for e in entradas:                                     # S2: o leitor nunca grava em Dados/Decisoes/Fotos
        if _dentro(saida, e) or _dentro(e, saida):
            raise ValueError("a pasta de saída não pode conter nem ficar dentro de nenhuma entrada (somente leitura)")
    commits = {}
    for k, v in (commits_lidos or {}).items():
        if k not in REPOS_COMMIT or not isinstance(v, str) or not _HEX.match(v):
            raise ValueError("commits_lidos: use chaves dados/decisoes/fotos com SHA hexadecimal (7 a 40 caracteres)")
        commits[k] = v

    lotes = {l: ler_lote(exportacoes / l, agora, l, tolerancia_futuro_min=cfg.tolerancia_futuro_min) for l in LETRAS}
    reg_a = registro.montar(lotes["A"].leitura.lidos, agora, arquivo_dias=cfg.arquivo_dias)
    reg_b = registro.montar(lotes["B"].leitura.lidos, agora, arquivo_dias=cfg.arquivo_dias)
    produtos = {**reg_b.produtos, **reg_a.produtos}            # A prevalece sobre B para o mesmo provedor+id
    em_a_e_b = sorted(f"{k[0]}/{k[1]}" for k in set(reg_a.produtos) & set(reg_b.produtos))

    decs = dec.carregar(decisoes_arquivo)
    reg_h = permissoes.carregar(termos_arquivo, permissoes_arquivo)

    resultado = []
    for chave in sorted(produtos):
        prod = produtos[chave]
        d = prod.vigente.dados
        foto = permissoes.avaliar_foto(chave[0], chave[1], reg_h, fotos_dir,
                                       (d.get("photo") or {}).get("url"))
        av = avaliar_v11(prod, decs.por_produto.get(chave, []), agora, cfg, foto)
        resultado.append(montar_v11(prod, av, agora))

    pasta = saida / "fichas"
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in pasta.iterdir():
        if velho.is_file() and velho.suffix in (".json", ".md"):
            velho.unlink()
    contagem: dict[str, int] = {}
    for ficha in resultado:
        base = nome_arquivo(ficha["produto"]["provider"], ficha["produto"]["id"])
        _gravar_json(pasta / f"{base}.json", ficha)
        (pasta / f"{base}.md").write_text(para_markdown_v11(ficha), encoding="utf-8")
        contagem[ficha["estado"]] = contagem.get(ficha["estado"], 0) + 1

    hist = {(h["provider"], h["productId"]): h for h in reg_b.historico()}
    hist.update({(h["provider"], h["productId"]): h for h in reg_a.historico()})
    _gravar_json(saida / "historico.json", [hist[k] for k in sorted(hist)])
    rejeitados = [dict(r.como_dict(), lote=l) for l in LETRAS for r in lotes[l].leitura.rejeitados]
    _gravar_json(saida / "rejeitados.json", rejeitados)
    _gravar_json(saida / "arquivados.json", sorted(reg_a.arquivados + reg_b.arquivados,
                                                    key=lambda a: (a["provider"], a["productId"])))
    resumo = {
        "contrato": "1.1",
        "geradoEm": formatar(agora),
        "parametros": {"revalidacaoHoras": cfg.revalidacao_horas, "tetoRevalidacaoHoras": 24, "fatosDias": cfg.fatos_dias,
                       "margemPublicacaoMin": cfg.margem_publicacao_min, "arquivoDias": cfg.arquivo_dias},
        "lotes": {l: lotes[l].resumo() for l in LETRAS},
        "fichas": len(resultado), "fichasPorEstado": dict(sorted(contagem.items())),
        "rejeitados": len(rejeitados),
        "rejeitadosPorDestino": {d: sum(1 for r in rejeitados if r["destino"] == d) for d in sorted({r["destino"] for r in rejeitados})},
        "arquivados": len(reg_a.arquivados) + len(reg_b.arquivados),
        "produtosEmAeB": em_a_e_b,
        "duplicatasExportId": reg_a.duplicatas_export_id + reg_b.duplicatas_export_id,
        "ignoradosEmSilencio": {l: lotes[l].leitura.ignorados for l in LETRAS},
        "commitsLidos": commits,
        "verificacoes": {
            "autoriaDeCommit": "nao_verificavel (S3 desabilitada: depende de o Cloud expor autoria e de lista configurada)",
            "reverificacaoNoMomentoDaPublicacao": "inexistente (capacidade reservada; vale só a janela declarada)",
            "repositorioDeFotos": "informado" if fotos_dir else "nao_informado (nenhuma foto utilizável)",
        },
        "avisos": [a for l in LETRAS for a in lotes[l].motivos if lotes[l].status in ("pasta_ausente", "vazio")]
                  + decs.avisos + reg_h.avisos,
    }
    _gravar_json(saida / "resumo.json", resumo)
    return resumo
