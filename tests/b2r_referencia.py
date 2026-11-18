"""Hashes de REFERÊNCIA do comportamento anterior à B2R (capturados no commit-base ef25672 antes de qualquer alteração).

``calcular()`` recalcula, no código atual, os mesmos valores com os parâmetros PADRÃO; ``b2r_referencia.json`` guarda os valores do
commit-base. Os dois devem ser idênticos no mesmo ambiente (mesma versão do Pillow/libjpeg). Regerar só com decisão explícita:
``python3 -m tests.b2r_referencia --gravar`` (nunca para "consertar" uma regressão).
"""
from __future__ import annotations

import hashlib
import io
import json
import platform
import shutil
import sys
import tempfile
import zlib
from pathlib import Path

import PIL
from PIL import Image, features

from gerador import fundo_marca
from gerador import identidade as idv
from gerador.layouts import LAYOUTS

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = Path(__file__).resolve().parent / "b2r_referencia.json"
COMMIT_BASE = "ef256724578d87b7aa60b457b991f447dd671963"
FIXTURE = RAIZ / "curadoria_b" / "exemplos_ficticios" / "ficha_valida.json"
SLIDES_ANTIGOS = {
    "curto": {"titulo": "OLÁ", "destaque": "MUNDO", "texto": "Texto curto."},
    "medio": {"titulo": "PANELA DE PRESSÃO", "destaque": "FICTÍCIA 5 LITROS", "texto": "Loja Fictícia · Arte ilustrativa"},
    "longo": {"titulo": "CARACTERÍSTICA", "destaque": "COMPROVADA", "texto": "Capacidade de cinco litros para toda a família"},
}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def hashes_layouts_antigos() -> dict:
    foto = fundo_marca.gerar_fundo(0)
    out = {}
    for layout in ("foto_topo", "foto_cheia", "cartao"):
        for nome, base in SLIDES_ANTIGOS.items():
            img, areas = LAYOUTS[layout](foto, {"layout": layout, **base}, 2, 4)
            out[f"{layout}/{nome}"] = {"pixels": _sha(img.convert("RGB").tobytes()), "areas": {k: list(v) for k, v in sorted(areas.items())}}
    return out


FIXTURE_RELOGIO = "2026-11-17T15:00:00Z"


def _versao(recurso: str):
    try:
        return features.version(recurso) if features.check(recurso) else None
    except Exception:                                                  # recurso desconhecido nesta versão do Pillow
        return None


def sonda_png() -> str:
    """SHA-256 do PNG de uma imagem sintética fixa, gravada com os MESMOS parâmetros dos slides (``save(..., "PNG")``). Mede o
    comportamento do codificador (Pillow + zlib/zlib-ng) em vez de presumi-lo pelos números de versão."""
    im = Image.new("RGB", (256, 256))
    im.putdata([((x * 7 + y * 13 + (x * y) % 251) % 256, (x ^ y) % 256, (x * 3 + (y // 5) * 11) % 256) for y in range(256) for x in range(256)])
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return _sha(buf.getvalue())


def _fontes_usadas() -> dict:
    achadas = {}
    for tipo, nomes in idv.FONTES.items():
        for nome in nomes:
            caminho = next((Path(pasta) / nome for pasta in idv._PASTAS if (Path(pasta) / nome).exists()), None)
            if caminho:
                achadas[tipo] = {"arquivo": nome, "sha256": _sha(caminho.read_bytes())}
                break
    return achadas


def impressao_ambiente() -> dict:
    """Impressão digital MEDIDA do ambiente atual (versões efetivas + sonda do codificador PNG + fontes realmente usadas)."""
    zv = _versao("zlib")
    return {"python": platform.python_version(), "pillow": PIL.__version__, "zlib": zv, "zlibNg": bool(zv and "ng" in str(zv).lower()),
            "zlibPython": zlib.ZLIB_VERSION, "libjpeg": _versao("libjpeg_turbo") or _versao("jpg"), "freetype": _versao("freetype2"),
            "raqm": _versao("raqm"), "fontes": _fontes_usadas(), "sondaPng": sonda_png()}


def pixels_canonicos(arquivo) -> dict:
    """Conteúdo DECODIFICADO de uma imagem, sem conversão de modo: ``{modo, largura, altura, pixels}``. O hash cobre o modo, as dimensões e os
    bytes brutos de ``Image.tobytes()`` no modo original, então uma troca de modo ou de dimensão altera o hash (e o modo é comparado à parte)."""
    with Image.open(arquivo) as im:
        im.load()
        cab = f"{im.mode}|{im.width}x{im.height}|".encode()
        return {"modo": im.mode, "largura": im.width, "altura": im.height, "pixels": _sha(cab + im.tobytes())}


def capturar_b2(estilo: str | None = None) -> dict:
    """Executa o fluxo B2 (fixture, relógio e parâmetros da captura histórica) e devolve TODOS os valores comparáveis, incluindo o conteúdo
    decodificado dos PNGs e da folha. ``estilo`` só é repassado quando informado (o código histórico não tinha o parâmetro)."""
    from orquestrador_b2.fluxo import executar
    from produtos.tempo import parse_data
    tmp = Path(tempfile.mkdtemp(prefix="b2ref_"))
    try:
        extra = {"estilo": estilo} if estilo else {}
        rel = executar(FIXTURE, tmp / "s", parse_data(FIXTURE_RELOGIO), aprovar_fundo_ficticio=True, **extra)
        slides = [{"arquivo": s["arquivo"], "jpegSha256": s["sha256"], "png": s["png"], "pngSha256": s["pngSha256"],
                   "pngConteudo": pixels_canonicos(tmp / "s" / "slides_png" / s["png"])} for s in rel["slides"]]
        folha = tmp / "s" / "folha_de_contato.png"
        return {"status": rel["status"], "estilo": rel.get("estilo"), "fundo": rel["fundo"]["sha256"],
                "carrossel": json.loads(json.dumps(rel["carrossel"], sort_keys=True)),
                "slides": slides, "folha": {"sha256": rel["arquivos"]["folha"]["sha256"], "conteudo": pixels_canonicos(folha)}}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def hashes_b2_antigo() -> dict:
    """Formato histórico (chave ``b2`` do JSON): status, fundo, slides (arquivo, SHA-256 do JPEG, SHA-256 do PNG), folha e carrossel."""
    c = capturar_b2()
    return {"status": c["status"], "fundo": c["fundo"], "slides": [(s["arquivo"], s["jpegSha256"], s["pngSha256"]) for s in c["slides"]],
            "folha": c["folha"]["sha256"], "carrossel": c["carrossel"]}


def ambiente_equivalente(atual: dict, ref_ambiente: dict | None) -> tuple[bool, str]:
    """``(equivalente, motivo)``: os bytes comprimidos dos PNGs só podem ser comparados quando há EVIDÊNCIA de que o codificador é o mesmo
    da reprodução verificada: mesmo Pillow, mesma zlib (incluindo zlib-ng) E mesma sonda de codificação. Sem evidência → ``False``."""
    verificada = (ref_ambiente or {}).get("reproducaoVerificada")
    if not isinstance(verificada, dict):
        return False, "a referência não traz uma reprodução verificada do codificador PNG"
    for campo in ("pillow", "zlib", "zlibNg", "sondaPng"):
        if verificada.get(campo) in (None, ""):
            return False, f"evidência insuficiente na referência: campo '{campo}' ausente"
        if atual.get(campo) in (None, ""):
            return False, f"evidência insuficiente no ambiente atual: campo '{campo}' ausente"
        if verificada[campo] != atual[campo]:
            return False, f"codificador diferente do verificado ({campo}: {atual[campo]!r} ≠ {verificada[campo]!r})"
    return True, "mesmo Pillow, mesma zlib e mesma sonda de codificação PNG da reprodução verificada"


def comparar_b2(atual: dict, ref_b2: dict, ref_conteudo: dict | None, ambiente_atual: dict, ref_ambiente: dict | None) -> dict:
    """Compara uma captura (``capturar_b2``) com a referência histórica. Devolve ``{"erros", "bytesPngComparados", "motivoBytesPng"}``.

    SEMPRE (qualquer ambiente): status, fundo, carrossel, nome/quantidade/ordem dos slides, SHA-256 dos JPEGs e, para cada PNG e para a
    folha, hash dos pixels decodificados + largura + altura + modo. Só quando o ambiente é comprovadamente equivalente: SHA-256 dos bytes
    dos PNGs e da folha. Nunca há ``skip``: a dispensa dos bytes comprimidos é registrada em ``motivoBytesPng``."""
    erros = []
    for campo in ("status", "fundo", "carrossel"):
        if atual.get(campo) != ref_b2.get(campo):
            erros.append(f"{campo} diverge da referência")
    ref_slides = [tuple(x) for x in ref_b2["slides"]]
    nomes, ref_nomes = [s["arquivo"] for s in atual["slides"]], [x[0] for x in ref_slides]
    if nomes != ref_nomes:
        erros.append(f"slides (nome, quantidade ou ordem) divergem: {nomes} ≠ {ref_nomes}")
    if not ref_conteudo or "slides" not in ref_conteudo or "folha" not in ref_conteudo:
        erros.append("a referência não traz 'b2Conteudo' (pixels, dimensões e modo): a verificação de conteúdo não pode ser dispensada")
        ref_conteudo = {"slides": [], "folha": {}}
    equivalente, motivo = ambiente_equivalente(ambiente_atual, ref_ambiente)
    ref_c = {c["arquivo"]: c for c in ref_conteudo["slides"]}
    for s, (arq, jpg, png) in zip(atual["slides"], ref_slides):
        if s["jpegSha256"] != jpg:
            erros.append(f"{arq}: SHA-256 do JPEG diverge")
        esperado = (ref_c.get(arq) or {}).get("conteudo")
        if esperado is None:
            erros.append(f"{arq}: sem conteúdo de referência")
        else:
            for k, rotulo in (("modo", "modo de cor"), ("largura", "largura"), ("altura", "altura"), ("pixels", "pixels decodificados")):
                if s["pngConteudo"][k] != esperado[k]:
                    erros.append(f"{arq}: {rotulo} do PNG diverge")
        if equivalente and s["pngSha256"] != png:
            erros.append(f"{arq}: SHA-256 dos bytes do PNG diverge (ambiente de codificação equivalente)")
    esperado = ref_conteudo["folha"].get("conteudo")
    if esperado is None:
        erros.append("folha: sem conteúdo de referência")
    else:
        for k, rotulo in (("modo", "modo de cor"), ("largura", "largura"), ("altura", "altura"), ("pixels", "pixels decodificados")):
            if atual["folha"]["conteudo"][k] != esperado[k]:
                erros.append(f"folha: {rotulo} diverge")
    if equivalente and atual["folha"]["sha256"] != ref_b2["folha"]:
        erros.append("folha: SHA-256 dos bytes do PNG diverge (ambiente de codificação equivalente)")
    return {"erros": erros, "bytesPngComparados": equivalente,
            "motivoBytesPng": motivo if equivalente else "comparação dos bytes comprimidos dispensada: " + motivo}


def comparar_deterministico(a: dict, b: dict) -> list[str]:
    """Diferenças entre duas execuções locais (mesma entrada e relógio): JPEGs, PNGs, folha e conteúdo devem ser IDÊNTICOS byte a byte."""
    erros = []
    if [s["arquivo"] for s in a["slides"]] != [s["arquivo"] for s in b["slides"]]:
        return ["slides (nome ou ordem) diferem entre as duas execuções"]
    for x, y in zip(a["slides"], b["slides"]):
        for k in ("jpegSha256", "pngSha256", "pngConteudo"):
            if x[k] != y[k]:
                erros.append(f"{x['arquivo']}: {k} difere entre as duas execuções")
    if a["folha"] != b["folha"]:
        erros.append("folha difere entre as duas execuções")
    erros += [f"{k} difere entre as duas execuções" for k in ("status", "fundo", "carrossel") if a[k] != b[k]]
    return erros


def verificar_b2(estilo: str | None = None) -> dict:
    """Captura + comparação com ``b2r_referencia.json`` (uso dos testes). Inclui a captura e o ambiente medido no resultado."""
    ref = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    captura, ambiente = capturar_b2(estilo), impressao_ambiente()
    return {**comparar_b2(captura, ref["b2"], ref.get("b2Conteudo"), ambiente, ref.get("ambiente")), "captura": captura, "ambiente": ambiente}


def calcular() -> dict:
    return {
        "fundos": {str(v): _sha(fundo_marca.fundo_bytes(v)) for v in range(fundo_marca.VARIANTES)},
        "layouts": hashes_layouts_antigos(),
        "b2": hashes_b2_antigo(),
    }


def main() -> int:
    if "--ambiente" in sys.argv:
        print(json.dumps(impressao_ambiente(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if "--gravar" in sys.argv:
        if ARQUIVO.exists():
            print("recusado: a referência histórica já existe e não pode ser regravada (DT-37)", file=sys.stderr)
            return 2
        ARQUIVO.write_text(json.dumps({"commitBase": COMMIT_BASE, **calcular()}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        print("referência gravada em", ARQUIVO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
