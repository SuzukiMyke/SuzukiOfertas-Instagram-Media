"""Validação automática do MP4 (ffprobe + checagens de quadros) e relatório JSON/MD."""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from .motion import smoothness_ratio


def _run(cmd: list[str], timeout: int = 120, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=False, capture_output=True, text=text, timeout=timeout, check=False)


def tool_versions() -> dict:
    import PIL

    def first(cmd):
        try:
            r = _run(cmd)
            return (r.stdout or r.stderr).splitlines()[0].strip()
        except (OSError, IndexError):
            return "indisponível"
    enc = _run(["ffmpeg", "-hide_banner", "-encoders"]).stdout
    return {
        "python": platform.python_version(),
        "pillow": PIL.__version__,
        "ffmpeg": first(["ffmpeg", "-version"]),
        "ffprobe": first(["ffprobe", "-version"]),
        "libx264": "libx264" in enc,
        "aac": re.search(r"\baac\b", enc) is not None,
        "platform": platform.platform(),
    }


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def decoded_md5(path: str | Path) -> str:
    """Hash dos quadros DECODIFICADOS (framemd5). Igual => mesmo vídeo pixel a pixel.

    O x264 com mais de 1 thread pode variar bits do fluxo entre execuções sem mudar a
    imagem decodificada; com ``output.threads = 1`` o arquivo é idêntico byte a byte.
    """
    r = _run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(path),
              "-map", "0:v", "-f", "framemd5", "-"], timeout=300)
    lines = [ln for ln in r.stdout.splitlines() if ln and not ln.startswith("#")]
    return hashlib.md5("\n".join(lines).encode()).hexdigest()


def probe(path: str | Path) -> dict:
    r = _run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {r.stderr.strip()}")
    return json.loads(r.stdout)


def moov_before_mdat(path: str | Path) -> bool | None:
    """Lê as caixas de topo do MP4: True se 'moov' vem antes de 'mdat' (faststart)."""
    order = []
    with open(path, "rb") as f:
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            size = int.from_bytes(hdr[:4], "big")
            typ = hdr[4:8].decode("latin-1")
            if size == 1:
                size = int.from_bytes(f.read(8), "big")
                skip = size - 16
            elif size == 0:
                order.append(typ)
                break
            else:
                skip = size - 8
            order.append(typ)
            if typ in ("moov", "mdat") and "moov" in order and "mdat" in order:
                break
            f.seek(skip, 1)
    if "moov" not in order or "mdat" not in order:
        return None
    return order.index("moov") < order.index("mdat")


def _ratio(s: str) -> float:
    if not s or s in ("0/0", "N/A"):
        return 0.0
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b) if float(b) else 0.0
    return float(s)


def check_video(path: str | Path, cfg: dict, duration_range: tuple[float, float] | None) -> dict:
    """Checagens técnicas do contêiner/fluxos. Retorna {checks: [...], probe: {...}}."""
    o, v, a = cfg["output"], cfg["validation"], cfg["audio"]
    info = probe(path)
    fmt = info["format"]
    vs = [s for s in info["streams"] if s["codec_type"] == "video"]
    aus = [s for s in info["streams"] if s["codec_type"] == "audio"]
    checks = []

    def add(name, ok, detail, blocking=True):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "blocking": blocking})

    add("contêiner MP4", "mp4" in fmt.get("format_name", ""), fmt.get("format_name"))
    add("um fluxo de vídeo", len(vs) == 1, f"{len(vs)} fluxo(s)")
    if vs:
        s = vs[0]
        add("codec h264", s.get("codec_name") == "h264", s.get("codec_name"))
        add("pix_fmt yuv420p", s.get("pix_fmt") == "yuv420p", s.get("pix_fmt"))
        add("perfil High/Main", s.get("profile") in ("High", "Main"), s.get("profile"))
        add(f"resolução {o['width']}x{o['height']}", (s.get("width"), s.get("height")) == (o["width"], o["height"]),
            f"{s.get('width')}x{s.get('height')}")
        add("razão 9:16", s.get("width", 0) * 16 == s.get("height", 0) * 9, s.get("display_aspect_ratio"))
        rf, af = _ratio(s.get("r_frame_rate")), _ratio(s.get("avg_frame_rate"))
        add(f"fps {o['fps']} constante", abs(rf - o["fps"]) < 1e-3 and abs(af - o["fps"]) < 0.01,
            f"r={s.get('r_frame_rate')} avg={s.get('avg_frame_rate')}")
        sar = s.get("sample_aspect_ratio", "1:1")
        add("SAR 1:1", sar in ("1:1", "N/A", None), sar)
        vbr = int(s.get("bit_rate") or fmt.get("bit_rate") or 0)
        add(f"bitrate de vídeo ≤ {v['max_bitrate_mbps']} Mbps", vbr <= v["max_bitrate_mbps"] * 1e6,
            f"{vbr / 1e6:.2f} Mbps")
    dur = float(fmt.get("duration", 0))
    if duration_range:
        lo, hi = duration_range
        add(f"duração {lo}–{hi} s", lo - v["duration_tolerance"] <= dur <= hi + v["duration_tolerance"], f"{dur:.3f} s")
    add(f"duração ≤ {v['duration_hard_max']} s", dur <= v["duration_hard_max"], f"{dur:.3f} s")
    size = Path(path).stat().st_size
    add(f"tamanho ≤ {v['max_size_mb']} MB", size <= v["max_size_mb"] * 1e6, f"{size / 1e6:.2f} MB")
    add("moov no início (faststart)", moov_before_mdat(path) is True, str(moov_before_mdat(path)))
    if a["mode"] == "silent":
        if a["silent_track"]:
            add("faixa silenciosa AAC", len(aus) == 1 and aus[0].get("codec_name") == "aac", f"{len(aus)} faixa(s)")
        else:
            add("sem faixa de áudio (modo silent)", len(aus) == 0, f"{len(aus)} faixa(s)")
    else:
        ok = len(aus) == 1 and aus[0].get("codec_name") == "aac" and int(aus[0].get("sample_rate", 0)) >= 44100
        add("áudio AAC ≥ 44,1 kHz", ok, [(x.get("codec_name"), x.get("sample_rate")) for x in aus])
    return {"checks": checks, "duration_s": dur, "size_bytes": size,
            "video": {k: vs[0].get(k) for k in ("codec_name", "profile", "pix_fmt", "width", "height",
                                                 "r_frame_rate", "avg_frame_rate", "bit_rate", "nb_frames")} if vs else {}}


def extract_frame(video: str | Path, t: float, out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = _run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
              "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)])
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"falha ao extrair quadro em {t:.2f}s: {r.stderr.strip()}")
    return out


def frame_stddev(path: str | Path) -> float:
    with Image.open(path) as im:
        st = ImageStat.Stat(im.convert("RGB"))
        return sum(st.stddev) / 3


def consecutive_diffs(video: str | Path, t: float, n: int, w: int, h: int) -> list[float]:
    """Diferença média absoluta entre n quadros consecutivos (região central, cinza, resolução cheia)."""
    cw, ch = w // 2, h // 2
    r = _run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video),
              "-frames:v", str(n), "-vf", f"crop={cw}:{ch}:{(w - cw) // 2}:{(h - ch) // 2},format=gray",
              "-f", "rawvideo", "-"], text=False)
    raw = r.stdout
    fs = cw * ch
    frames = [Image.frombytes("L", (cw, ch), raw[i * fs:(i + 1) * fs]) for i in range(len(raw) // fs)]
    return [ImageStat.Stat(ImageChops.difference(frames[i], frames[i + 1])).mean[0] for i in range(len(frames) - 1)]


def logo_mad(frame: str | Path, layer) -> float:
    """Diferença média entre o logo esperado e o quadro (pixels com alfa alto)."""
    with Image.open(frame) as fr, Image.open(layer.path) as lg:
        crop = fr.convert("RGB").crop((layer.x, layer.y, layer.x + layer.w, layer.y + layer.h))
        lg = lg.convert("RGBA")
        mask = lg.getchannel("A").point(lambda a: 255 if a >= 200 else 0)
        diff = ImageChops.difference(crop, lg.convert("RGB")).convert("L")
        st = ImageStat.Stat(diff, mask)
        return st.mean[0] if st.count[0] else float("inf")


# ---------------------------------------------------------------- relatório
def write_report(report: dict, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(report_markdown(report), encoding="utf-8")


def report_markdown(r: dict) -> str:
    ok = "✔" if r["approved_technical"] else "✘"
    L = [f"# Relatório do reel `{r['id']}`", "",
         f"- Resultado técnico automático: **{ok} {'sem erros bloqueantes' if r['approved_technical'] else 'COM ERROS'}**",
         "- Estado: implementado e testado localmente. NÃO validado com serviço real; NÃO aprovado para produção.",
         f"- Arquivo: `{r.get('video_path')}`",
         f"- SHA-256: `{r.get('sha256')}`",
         f"- MD5 dos quadros decodificados (framemd5): `{r.get('frames_md5')}`",
         f"- Duração: {r.get('duration_s', 0):.3f} s · Tamanho: {r.get('size_bytes', 0) / 1e6:.2f} MB",
         f"- Render: {r.get('render', {}).get('wall_s', '–')} s · pico de memória do FFmpeg: "
         f"{r.get('render', {}).get('peak_rss_mb', '–')} MB", "",
         "## Ferramentas", ""]
    for k, v in r.get("tools", {}).items():
        L.append(f"- {k}: {v}")
    L += ["", "## Linha do tempo", "", "| Segmento | Início (s) | Fim (s) | Duração (s) | Transição de entrada |",
          "|---|---|---|---|---|"]
    for s in r.get("timeline", {}).get("segments", []):
        ti = s["transition_in"]
        L.append(f"| {s['key']} ({s['kind']}) | {s['start_s']:.3f} | {s['end_s']:.3f} | {s['duration_s']:.3f} | "
                 f"{(ti['type'] + ' ' + format(ti['duration'], '.2f') + ' s') if ti else '—'} |")
    L += ["", "## Checagens", "", "| Checagem | OK | Detalhe |", "|---|---|---|"]
    for c in r.get("checks", []):
        L.append(f"| {c['check']}{'' if c['blocking'] else ' (aviso)'} | {'✔' if c['ok'] else '✘'} | {c['detail']} |")
    if r.get("errors"):
        L += ["", "## Erros bloqueantes", ""] + [f"- {e}" for e in r["errors"]]
    if r.get("warnings"):
        L += ["", "## Avisos", ""] + [f"- {w}" for w in r["warnings"]]
    if r.get("sources"):
        L += ["", "## Origem das imagens", "", "| Cena | Categoria | Arquivo | Tipo | Origem | Licença |",
              "|---|---|---|---|---|---|"]
        for s in r["sources"]:
            L.append(f"| {s['scene']} | {s['category']} | `{s['path']}` | {s['kind']} | {s['origin']} | {s['license']} |")
    if r.get("frames"):
        L += ["", "## Quadros de verificação", ""]
        for f in r["frames"]:
            L.append(f"- `{f['path']}` — {f['label']} (t={f['t']:.2f}s, desvio-padrão {f['stddev']:.1f})")
    return "\n".join(L) + "\n"
