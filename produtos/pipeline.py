"""Orquestração: pasta de troca (somente leitura) -> fichas, histórico e relatórios na pasta de saída."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import avaliacao, decisoes as dec, fichas, leitor, registro
from .avaliacao import Configuracao
from .tempo import formatar


def _dentro(a: Path, b: Path) -> bool:
    a, b = a.resolve(), b.resolve()
    return a == b or b in a.parents


def _gravar_json(caminho: Path, obj) -> None:
    caminho.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def processar(troca: Path | str, saida: Path | str, agora: datetime, *, decisoes_arquivo: Path | str | None = None,
              cfg: Configuracao | None = None) -> dict:
    """Executa o fluxo completo. Devolve o resumo (também gravado em ``saida/resumo.json``)."""
    cfg = cfg or Configuracao()
    if cfg.contrato != "1.0":
        raise ValueError("este fluxo é o modo 1.0; o modo 1.1 é explícito: use pipeline_v11.processar_v11")
    troca, saida = Path(troca), Path(saida)
    if _dentro(saida, troca) or _dentro(troca, saida / "fichas"):
        raise ValueError("a pasta de saída não pode ficar dentro da pasta de troca (que é somente leitura)")

    lei = leitor.ler_pasta(troca, agora, tolerancia_futuro_min=cfg.tolerancia_futuro_min)
    reg = registro.montar(lei.lidos, agora, arquivo_dias=cfg.arquivo_dias)
    decs = dec.carregar(decisoes_arquivo)

    resultado = []
    for chave in sorted(reg.produtos):
        prod = reg.produtos[chave]
        av = avaliacao.avaliar(prod, decs.por_produto.get(chave, []), agora, cfg)
        resultado.append((fichas.montar(prod, av, agora), av))

    pasta = saida / "fichas"
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in pasta.iterdir():                       # só arquivos gerados por este módulo na pasta de saída
        if velho.is_file() and velho.suffix in (".json", ".md"):
            velho.unlink()
    contagem: dict[str, int] = {}
    for ficha, _ in resultado:
        base = fichas.nome_arquivo(ficha["produto"]["provider"], ficha["produto"]["id"])
        _gravar_json(pasta / f"{base}.json", ficha)
        (pasta / f"{base}.md").write_text(fichas.para_markdown(ficha), encoding="utf-8")
        contagem[ficha["estado"]] = contagem.get(ficha["estado"], 0) + 1

    _gravar_json(saida / "historico.json", reg.historico())
    rejeitados = [r.como_dict() for r in lei.rejeitados]
    _gravar_json(saida / "rejeitados.json", rejeitados)
    _gravar_json(saida / "arquivados.json", reg.arquivados)
    resumo = {
        "geradoEm": formatar(agora),
        "parametros": {"revalidacaoHoras": cfg.revalidacao_horas, "arquivoDias": cfg.arquivo_dias},
        "manifestoPresente": lei.manifesto_presente,
        "fichas": len(resultado), "fichasPorEstado": dict(sorted(contagem.items())),
        "rejeitados": len(rejeitados),
        "rejeitadosPorDestino": {d: sum(1 for r in rejeitados if r["destino"] == d)
                                 for d in sorted({r["destino"] for r in rejeitados})},
        "arquivados": len(reg.arquivados),
        "duplicatasExportId": reg.duplicatas_export_id,
        "ignoradosEmSilencio": lei.ignorados,
        "avisos": lei.avisos + decs.avisos,
    }
    _gravar_json(saida / "resumo.json", resumo)
    return resumo
