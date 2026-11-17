"""Montador dos comandos FFmpeg (listas de argumentos; nunca executados via shell).

Render em DOIS PASSES para manter memória e CPU baixas:

1. Um comando por segmento (gancho, cenas, CTA):
   fundo 2x --format=rgb24--> zoompan (easing) --> [drawbox de escurecimento]
     --> overlay(camada 1, fade alfa + deslize) --> ... --> yuv420p
   gravado como intermediário H.264 de alta qualidade (``output.intermediate_crf``).
2. Um comando final que encadeia os intermediários com xfade (offset = início do
   segmento na linha do tempo), adiciona o áudio (se houver) e codifica o MP4 final.

Motivo: em passe único (36 entradas num só grafo) o pico medido foi ~1,1 GB; em dois
passes, com decodificadores de 1 thread no passe final, fica em ~0,5 GB.
"""
from __future__ import annotations

import subprocess

from .audio import audio_output_args, build_audio
from .motion import _f, overlay_xy, zoompan_filter

BASE = ["-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
BITEXACT = ["-fflags", "+bitexact", "-flags:v", "+bitexact", "-map_metadata", "-1"]


def _layer_chain(la, in_idx: int, label: str) -> str:
    f = [f"[{in_idx}:v]format=rgba"]
    if la.anim != "static" and la.fade_in > 0:
        f.append(f"fade=t=in:st={_f(la.t_in)}:d={_f(la.fade_in)}:alpha=1")
    if la.anim != "static" and la.fade_out > 0:
        f.append(f"fade=t=out:st={_f(max(la.t_out - la.fade_out, 0))}:d={_f(la.fade_out)}:alpha=1")
    return ",".join(f) + f"[{label}]"


def segment_graph(sp: dict, cfg: dict) -> tuple[list[str], str]:
    """Entradas e filter_complex de UM segmento. Saída rotulada [vout]."""
    o = cfg["output"]
    W, H, fps = o["width"], o["height"], o["fps"]
    seg = sp["segment"]
    dur = _f(seg.duration)
    inputs = ["-i", sp["bg_path"]]
    parts = [f"[0:v]format=rgb24,{zoompan_filter(sp['camera'], seg.frames, W, H, fps)},setsar=1,format=rgb24[b]"]
    cur = "b"
    if sp.get("dim", 0) > 0:
        parts.append(f"[b]drawbox=x=0:y=0:w=iw:h=ih:color=black@{_f(sp['dim'])}:t=fill[d]")
        cur = "d"
    for j, la in enumerate(sp["layers"]):
        idx = j + 1
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", dur, "-i", la.path]
        parts.append(_layer_chain(la, idx, f"l{j}"))
        if la.anim in ("slide_up", "slide_left"):
            x, y = overlay_xy(la.x, la.y, la.anim, la.slide_px, la.t_in, la.fade_in + 0.15)
            ev = "frame"
        else:
            x, y, ev = str(la.x), str(la.y), "init"
        parts.append(f"[{cur}][l{j}]overlay=x='{x}':y='{y}':format=rgb:eval={ev}:shortest=0[o{j}]")
        cur = f"o{j}"
    parts.append(f"[{cur}]trim=end_frame={seg.frames},setpts=PTS-STARTPTS,format=yuv420p,setsar=1[vout]")
    return inputs, ";".join(parts)


def build_segment_command(sp: dict, cfg: dict, out_path: str, ffmpeg: str = "ffmpeg") -> list[str]:
    o = cfg["output"]
    inputs, graph = segment_graph(sp, cfg)
    return [ffmpeg, *BASE, "-filter_complex_threads", str(o["threads"]), *inputs,
            "-filter_complex", graph, "-map", "[vout]", "-an",
            "-c:v", "libx264", "-preset", o["preset"], "-crf", str(o["intermediate_crf"]),
            "-pix_fmt", "yuv420p", "-r", str(o["fps"]), "-threads", str(o["threads"]),
            "-frames:v", str(sp["segment"].frames), *BITEXACT, out_path]


def final_graph(plan: dict) -> tuple[str, str]:
    """xfade encadeado entre os intermediários (entradas 0..n-1)."""
    segs = [sp["segment"] for sp in plan["segments"]]
    fps = plan["timeline"].fps
    parts = [f"[{k}:v]setpts=PTS-STARTPTS,settb=AVTB,fps={fps},setsar=1[v{k}]" for k in range(len(segs))]
    cur = "v0"
    for k in range(1, len(segs)):
        tr = segs[k].trans_in
        parts.append(f"[{cur}][v{k}]xfade=transition={tr['type']}:duration={_f(tr['duration'])}"
                     f":offset={_f(segs[k].start)}[x{k}]")
        cur = f"x{k}"
    parts.append(f"[{cur}]format=yuv420p,setsar=1[vout]")
    return ";".join(parts), "[vout]"


def build_final_command(seg_files: list[str], plan: dict, cfg: dict, out_path: str,
                        ffmpeg: str = "ffmpeg") -> list[str]:
    o = cfg["output"]
    inputs: list[str] = []
    for f, sp in zip(seg_files, plan["segments"]):
        # -itsoffset faz o FFmpeg ler cada intermediário só quando a linha do tempo chega nele
        # (sem isso todos são decodificados em paralelo e os quadros ficam enfileirados na memória)
        # -threads 1 no decodificador: cada entrada com threads automáticas somava ~70 MB
        inputs += ["-threads", "1", "-itsoffset", _f(sp["segment"].start), "-i", f]
    graph, vlabel = final_graph(plan)
    total = plan["timeline"].total
    a_in, a_parts, a_label = build_audio(cfg, len(seg_files), total)
    if a_parts:
        graph = graph + ";" + ";".join(a_parts)
    maxrate = o["max_bitrate_mbps"]
    return [ffmpeg, *BASE, "-filter_complex_threads", str(o["threads"]),
            *inputs, *a_in,
            "-filter_complex", graph,
            "-map", vlabel,
            *audio_output_args(a_label),
            "-c:v", "libx264", "-profile:v", "high", "-preset", o["preset"], "-crf", str(o["crf"]),
            "-maxrate", f"{_f(maxrate)}M", "-bufsize", f"{_f(maxrate * 2)}M",
            "-pix_fmt", "yuv420p", "-r", str(o["fps"]), "-threads", str(o["threads"]),
            "-t", _f(total),
            "-movflags", "+faststart",
            *BITEXACT,
            out_path]


def run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    """Executa sem shell; somente lista de argumentos."""
    if not isinstance(cmd, list):
        raise TypeError("cmd deve ser lista de argumentos")
    return subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=timeout, check=False)
