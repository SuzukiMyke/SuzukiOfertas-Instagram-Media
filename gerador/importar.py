"""Importação de fotografias externas (ex.: Gemini Nano Banana) para o catálogo.

- Aceita JPG, PNG e WebP; valida formato real (não só a extensão),
  integridade e dimensões mínimas.
- Guarda o original byte a byte em photos/originais/.
- Cria a versão interna em JPEG (qualidade 95, sem subamostragem de cor),
  aplicando a orientação EXIF e preservando o perfil ICC. Nunca redimensiona
  de forma desproporcional: a imagem interna tem as mesmas dimensões do original
  (só reduz, proporcionalmente, se exceder LADO_MAXIMO).
- Evita duplicatas pelo SHA-256 do arquivo original.
- Entra sempre com status "pendente", salvo aprovação explícita com nome.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from PIL import Image, ImageOps

from .catalogo import Catalogo, agora_utc, sha256_arquivo

FORMATOS_ACEITOS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
LADO_MINIMO = 768        # abaixo disso a foto fica borrada num slide 1080 px
LADO_MAXIMO = 4096       # reduz proporcionalmente acima disso
MAX_PIXELS = 40_000_000  # proteção contra arquivos gigantes/corrompidos


class ErroImportacao(Exception):
    pass


def _nome_seguro(nome: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", nome).strip("._") or "imagem"
    return base[:80]


def validar_imagem(caminho: Path) -> dict:
    """Retorna {formato, largura, altura}; levanta ErroImportacao se inválida."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroImportacao(f"Arquivo não encontrado: {caminho}")
    try:
        with Image.open(caminho) as im:
            formato = im.format
            im.verify()  # checa integridade da estrutura
        with Image.open(caminho) as im:
            im.load()  # decodifica de fato (pega arquivos truncados)
            im = ImageOps.exif_transpose(im)
            largura, altura = im.size
    except ErroImportacao:
        raise
    except Exception as e:  # Pillow lança vários tipos para arquivos ruins
        raise ErroImportacao(f"Imagem corrompida ou ilegível: {e}") from e
    if formato not in FORMATOS_ACEITOS:
        raise ErroImportacao(f"Formato não aceito: {formato}. Use JPG, PNG ou WebP.")
    if largura * altura > MAX_PIXELS:
        raise ErroImportacao(f"Imagem grande demais: {largura}x{altura}.")
    if min(largura, altura) < LADO_MINIMO:
        raise ErroImportacao(
            f"Resolução insuficiente: {largura}x{altura} (mínimo {LADO_MINIMO}px no menor lado)."
        )
    return {"formato": formato, "largura": largura, "altura": altura}


def _converter_interno(origem: Path, destino: Path) -> tuple[int, int]:
    with Image.open(origem) as im:
        icc = im.info.get("icc_profile")
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            fundo = Image.new("RGB", im.size, (255, 255, 255))
            fundo.paste(im, mask=im.getchannel("A"))
            im = fundo
        else:
            im = im.convert("RGB")
        if max(im.size) > LADO_MAXIMO:
            im.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)  # proporcional
        kwargs = {"quality": 95, "subsampling": 0, "optimize": True}
        if icc:
            kwargs["icc_profile"] = icc
        destino.parent.mkdir(parents=True, exist_ok=True)
        im.save(destino, "JPEG", **kwargs)
        return im.size


def importar(
    arquivo: Path,
    provedor: str = "nano-banana",
    catalogo: Catalogo | None = None,
    origem: str = "ia",
    descricao: str = "",
    prompt: str | None = None,
    restricoes: list[str] | None = None,
    aprovado_por: str | None = None,
    nota_aprovacao: str | None = None,
) -> tuple[str, bool]:
    """Importa a imagem. Retorna (id, nova). Se já existir (mesmo hash), nova=False."""
    cat = catalogo or Catalogo()
    arquivo = Path(arquivo)
    info = validar_imagem(arquivo)
    sha = sha256_arquivo(arquivo)
    existente = cat.por_hash(sha)
    if existente:
        return existente, False

    if origem not in ("ia", "fotografia-real"):
        raise ErroImportacao("origem deve ser 'ia' ou 'fotografia-real'.")
    foto_id = cat.proximo_id(provedor)
    ext = FORMATOS_ACEITOS[info["formato"]]
    rel_original = f"photos/originais/{foto_id}__{_nome_seguro(arquivo.stem)}.{ext}"
    rel_interno = f"photos/{foto_id}.jpg"
    (cat.raiz / rel_original).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arquivo, cat.raiz / rel_original)
    largura, altura = _converter_interno(arquivo, cat.raiz / rel_interno)

    padrao = ["Não usar como foto de produto real", "Não alterar logotipos de terceiros"]
    if origem == "ia":
        padrao.insert(0, "Imagem gerada por IA: não representar como fotografia real")
    meta = {
        "id": foto_id,
        "provedor": provedor,
        "nome_arquivo_original": arquivo.name,
        "sha256_original": sha,
        "sha256": sha256_arquivo(cat.raiz / rel_interno),
        "largura": largura,
        "altura": altura,
        "formato_original": info["formato"],
        "data": agora_utc(),
        "tipo_data": "importacao",
        "origem": origem,
        "descricao": descricao,
        "prompt": prompt,
        "restricoes_uso": restricoes if restricoes is not None else padrao,
        "caminho_github": rel_interno,
        "caminho_original": rel_original,
    }
    cat.adicionar(foto_id, meta)
    if aprovado_por:
        cat.definir_aprovacao(foto_id, "aprovada", aprovado_por, nota_aprovacao)
    cat.salvar()
    return foto_id, True
