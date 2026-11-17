"""Apoio dos testes do modo 1.1: lotes A/B com manifesto, registros humanos e repositório de fotos fictícios."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from produtos.tests.base import AGORA, Base, produto_a, produto_b, uid  # noqa: F401  (reexportados)

FOTO_BYTES = b"\xff\xd8\xff\xe0" + b"FOTO-SINTETICA-DE-TESTE" * 20       # assinatura JPEG + conteúdo fictício
FOTO_SHA = hashlib.sha256(FOTO_BYTES).hexdigest()
EVIDENCIA_BYTES = "termo fictício de teste\n".encode()
EVIDENCIA_SHA = hashlib.sha256(EVIDENCIA_BYTES).hexdigest()


def gravar_lote(pasta: Path, arquivos: dict, *, manifesto: bool | dict = True) -> Path:
    """Grava ``arquivos`` ({nome: objeto|bytes}) e, por último, o ``manifest.json`` (``manifesto=False`` omite)."""
    pasta.mkdir(parents=True, exist_ok=True)
    itens = []
    for nome, obj in arquivos.items():
        b = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        (pasta / nome).write_bytes(b)
        itens.append({"name": nome, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)})
    if manifesto is True:
        (pasta / "manifest.json").write_text(json.dumps({"manifestVersion": "1.0", "count": len(itens), "files": itens}))
    elif isinstance(manifesto, dict):
        (pasta / "manifest.json").write_text(json.dumps(manifesto))
    return pasta


def termo(**over) -> dict:
    t = {"termoId": "T1", "programa": "Programa Fictício", "tipoEvidencia": "termo_programa", "escopo": "provider:EXEMPLO_A",
         "referencia": "https://programa.ficticio.example/termos", "arquivoEvidencia": "termo.txt",
         "evidenciaSha256": EVIDENCIA_SHA, "capturadoEm": "2026-11-10T12:00:00Z", "autor": "Maria Revisora"}
    t.update(over)
    return t


def permissao(pid="A001", **over) -> dict:
    p = {"provider": "EXEMPLO_A", "productId": pid, "status": "confirmada", "termoId": "T1", "fotoSha256": FOTO_SHA,
         "autor": "Maria Revisora", "data": "2026-11-17T14:00:00Z", "motivo": "conferida (fictício)"}
    p.update(over)
    return p


class BaseV11(Base):
    def setUp(self):
        super().setUp()
        self.exp = self.tmp / "exportacoes"
        self.hum = self.tmp / "decisoes"
        self.fotos = self.tmp / "fotos_repo"
        self.hum.mkdir()
        (self.fotos / "fotos").mkdir(parents=True)
        (self.fotos / "evidencias").mkdir()
        (self.fotos / "fotos" / f"{FOTO_SHA}.jpg").write_bytes(FOTO_BYTES)
        (self.fotos / "evidencias" / "termo.txt").write_bytes(EVIDENCIA_BYTES)

    def humanos(self, *, termos=None, permissoes=None, decisoes=None):
        out = {}
        for nome, chave, itens in (("termos_programas.json", "termos", [termo()] if termos is None else termos),
                                   ("permissoes_fotos.json", "permissoes", [permissao()] if permissoes is None else permissoes)):
            p = self.hum / nome
            p.write_text(json.dumps({"schemaVersion": "1.0", chave: itens}))
            out[chave] = p
        d = self.hum / "decisoes.json"
        d.write_text(json.dumps({"decisoesVersion": "1.0", "decisoes": decisoes or []}))
        return dict(termos_arquivo=out["termos"], permissoes_arquivo=out["permissoes"], decisoes_arquivo=d,
                    fotos_dir=self.fotos)

    def decisao(self, n, pid, decisao="aprovado_para_rascunho", provider="EXEMPLO_A", data="2026-11-17T14:30:00Z"):
        return {"provider": provider, "productId": pid, "exportId": uid(n), "decisao": decisao,
                "autor": "Maria Revisora", "data": data, "motivo": "teste"}

    def rodar(self, a=None, b=None, agora=AGORA, cfg=None, humanos=None, **kw):
        from produtos.pipeline_v11 import processar_v11
        if a is not None:
            gravar_lote(self.exp / "A", a)
        if b is not None:
            gravar_lote(self.exp / "B", b)
        self.exp.mkdir(exist_ok=True)
        h = self.humanos() if humanos is None else humanos
        resumo = processar_v11(self.exp, self.saida, agora, cfg=cfg, **{**h, **kw})
        fichas = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (self.saida / "fichas").glob("*.json")}
        return resumo, fichas


def instantaneo(pasta: Path) -> dict:
    return {str(p.relative_to(pasta)): (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None, p.lstat().st_mtime_ns)
            for p in sorted(pasta.rglob("*"))}
