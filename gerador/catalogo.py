"""Catálogo de fotografias (photos/catalogo.json).

Cada foto tem um ID interno estável (ex.: "flux-0001", "nb-0001") usado
pelos carrosséis. O arquivo de catálogo é a única fonte de verdade sobre
origem, hash, aprovação e restrições de uso.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPO_GITHUB = "SuzukiMyke/SuzukiOfertas-Instagram-Media"

# Prefixo de ID por provedor.
PROVEDORES = {
    "cloudflare-flux": "flux",
    "nano-banana": "nb",
    "foto-real": "real",
}
STATUS_VALIDOS = ("pendente", "aprovada", "rejeitada")


def agora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


class Catalogo:
    def __init__(self, raiz: Path = RAIZ):
        self.raiz = Path(raiz)
        self.arquivo = self.raiz / "photos" / "catalogo.json"
        if self.arquivo.exists():
            self.dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        else:
            self.dados = {"versao": 1, "fotos": {}}

    # ---------- leitura ----------
    @property
    def fotos(self) -> dict:
        return self.dados["fotos"]

    def obter(self, foto_id: str) -> dict:
        if foto_id not in self.fotos:
            raise KeyError(f"Foto '{foto_id}' não existe no catálogo.")
        return self.fotos[foto_id]

    def caminho(self, foto_id: str) -> Path:
        return self.raiz / self.obter(foto_id)["caminho_github"]

    def por_hash(self, sha: str) -> str | None:
        for fid, meta in self.fotos.items():
            if sha in (meta.get("sha256_original"), meta.get("sha256")):
                return fid
        return None

    def proximo_id(self, provedor: str) -> str:
        prefixo = PROVEDORES[provedor]
        nums = [int(i.split("-")[1]) for i in self.fotos if i.startswith(prefixo + "-")]
        return f"{prefixo}-{(max(nums) + 1 if nums else 1):04d}"

    def neuronios_hoje(self) -> float:
        hoje = agora_utc()[:10]
        return sum(
            float(m.get("consumo_neuronios") or 0)
            for m in self.fotos.values()
            if m.get("provedor") == "cloudflare-flux" and str(m.get("data", "")).startswith(hoje)
        )

    # ---------- escrita ----------
    def adicionar(self, foto_id: str, meta: dict) -> None:
        if foto_id in self.fotos:
            raise ValueError(f"ID duplicado: {foto_id}")
        meta.setdefault("aprovacao", {"status": "pendente", "por": None, "data": None, "nota": None})
        meta["repositorio"] = REPO_GITHUB
        self.fotos[foto_id] = meta

    def definir_aprovacao(self, foto_id: str, status: str, por: str, nota: str | None = None) -> dict:
        if status not in STATUS_VALIDOS:
            raise ValueError(f"Status inválido: {status}")
        if status != "pendente" and not (por or "").strip():
            raise ValueError("Aprovação/rejeição exige o nome de quem decidiu (--por).")
        meta = self.obter(foto_id)
        meta["aprovacao"] = {"status": status, "por": por, "data": agora_utc(), "nota": nota}
        return meta

    def salvar(self) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        texto = json.dumps(self.dados, ensure_ascii=False, indent=2, sort_keys=False)
        self.arquivo.write_text(texto + "\n", encoding="utf-8")

