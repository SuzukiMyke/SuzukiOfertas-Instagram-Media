"""Provedor automático: Cloudflare Workers AI / FLUX.1 schnell.

Segurança de custo:
- Só gera com confirmar=True (na CLI: --confirmar).
- Limite diário de neurônios contado a partir do catálogo (padrão 9000,
  abaixo da cota gratuita diária de 10 000). Nunca faz upgrade de plano.
- Máximo de imagens por execução (padrão 3).
- A autenticação é injetada pelo proxy (Network Secret); o token enviado
  aqui é um valor fictício e nenhum segredo é lido ou gravado.
"""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.request
from pathlib import Path

from PIL import Image

from .catalogo import Catalogo, agora_utc, sha256_arquivo

MODELO = "@cf/black-forest-labs/flux-1-schnell"
PASSOS = 4
NEURONIOS_ESTIMADOS = 172.8      # consumo medido na etapa 4.8 (4 passos, 1024x1024)
LIMITE_DIARIO = float(os.environ.get("FLUX_LIMITE_NEURONIOS_DIA", "9000"))
MAX_POR_EXECUCAO = int(os.environ.get("FLUX_MAX_IMAGENS", "3"))
SUFIXO_PADRAO = ", no people, no visible brands, no logos, no writing, no watermarks"


class ErroCota(Exception):
    pass


def _chamar_api(prompt: str) -> tuple[bytes, float]:
    conta = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not conta:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID não definido.")
    url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{MODELO}"
    corpo = json.dumps({"prompt": prompt, "steps": PASSOS}).encode()
    req = urllib.request.Request(
        url, data=corpo, method="POST",
        headers={"Authorization": "Bearer proxy-injeta", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        neur_header = r.headers.get("Cf-Ai-Neurons")
        dados = json.loads(r.read())
    if not dados.get("success"):
        raise RuntimeError(f"Falha na API: {dados.get('errors')}")
    res = dados["result"]
    neur = float(neur_header or res.get("usage", {}).get("neurons") or NEURONIOS_ESTIMADOS)
    return base64.b64decode(res["image"]), neur


def verificar_cota(cat: Catalogo, quantidade: int) -> None:
    if quantidade > MAX_POR_EXECUCAO:
        raise ErroCota(f"Pedido de {quantidade} imagens excede o máximo por execução ({MAX_POR_EXECUCAO}).")
    previsto = cat.neuronios_hoje() + quantidade * NEURONIOS_ESTIMADOS
    if previsto > LIMITE_DIARIO:
        raise ErroCota(
            f"Cota diária protegida: uso previsto {previsto:.1f} > limite {LIMITE_DIARIO:.0f} neurônios."
        )


def gerar(prompt: str, confirmar: bool = False, catalogo: Catalogo | None = None,
          descricao: str = "", chamar_api=_chamar_api) -> str:
    """Gera UMA foto, salva em photos/<id>.jpg e registra no catálogo."""
    if not confirmar:
        raise RuntimeError("Geração de IA bloqueada: passe confirmar=True (CLI: --confirmar).")
    cat = catalogo or Catalogo()
    verificar_cota(cat, 1)
    texto = prompt if "no logos" in prompt else prompt.rstrip(". ") + SUFIXO_PADRAO
    dados, neur = chamar_api(texto)
    foto_id = cat.proximo_id("cloudflare-flux")
    rel = f"photos/{foto_id}.jpg"
    destino = cat.raiz / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(dados))
    if im.format == "JPEG":
        destino.write_bytes(dados)
    else:
        im.convert("RGB").save(destino, "JPEG", quality=95, subsampling=0)
    sha = sha256_arquivo(destino)
    cat.adicionar(foto_id, {
        "id": foto_id,
        "provedor": "cloudflare-flux",
        "modelo": MODELO,
        "passos": PASSOS,
        "prompt": texto,
        "nome_arquivo_original": None,
        "sha256_original": sha,
        "sha256": sha,
        "largura": im.width,
        "altura": im.height,
        "data": agora_utc(),
        "tipo_data": "geracao",
        "origem": "ia",
        "descricao": descricao,
        "consumo_neuronios": round(neur, 2),
        "restricoes_uso": ["Imagem gerada por IA: não representar como fotografia real",
                           "Não usar como foto de produto real"],
        "caminho_github": rel,
    })
    cat.salvar()
    return foto_id
