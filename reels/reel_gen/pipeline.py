"""Orquestração: config -> linha do tempo -> camadas -> FFmpeg -> validação -> relatório."""
from __future__ import annotations

import json
import resource
import time
from pathlib import Path

from PIL import Image

from . import brand
from .config import REELS_ROOT, REPO_ROOT, ConfigError, load_config, resolve_path
from .ffmpeg_build import build_final_command, build_segment_command, run
from .motion import smoothness_ratio
from .layers import check_layers, layout_cta, layout_hook, layout_scene
from .rules import check_rules, scene_label
from .synth import brand_background
from .timeline import check_timeline, plan_timeline
from .validate import (check_video, consecutive_diffs, decoded_md5, extract_frame, frame_stddev, logo_mad, sha256,
                       tool_versions, write_report)

OUT_ROOT = REELS_ROOT / "out"


def _rel(p) -> str:
    try:
        return str(Path(p).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def _bg_file(cfg, src_path: str, focus, work: Path, name: str) -> tuple[str, Image.Image]:
    """Fundo pré-ampliado (supersample) para o zoompan + versão 1x para análise de contraste."""
    o = cfg["output"]
    ss = o["supersample"]
    out = work / f"{name}__bg.png"
    with Image.open(resolve_path(src_path)) as im:
        big = brand.cobrir(im, o["width"] * ss, o["height"] * ss, tuple(focus))
    big.save(out, compress_level=1)
    small = big.resize((o["width"], o["height"]), Image.BILINEAR)
    return str(out), small


def _brand_bg(cfg, work: Path, name: str) -> tuple[str, Image.Image]:
    o = cfg["output"]
    ss = o["supersample"]
    img = brand_background(cfg, o["width"] * ss, o["height"] * ss)
    out = work / f"{name}__bg.png"
    img.save(out, compress_level=1)
    return str(out), img.resize((o["width"], o["height"]), Image.BILINEAR)


def _hook_camera(scene_cam: dict) -> dict:
    """Padrão do gancho: leve aproximação que termina no enquadramento inicial da cena."""
    z = scene_cam["zoom_start"]
    return {"zoom_start": min(z + 0.06, 3.0), "zoom_end": z, "pan_start": scene_cam["pan_start"],
            "pan_end": scene_cam["pan_start"], "easing": "ease_out"}


CTA_CAMERA = {"zoom_start": 1.0, "zoom_end": 1.05, "pan_start": [0.5, 0.4], "pan_end": [0.5, 0.4],
              "easing": "ease_in_out"}


def prepare(cfg: dict, cta_only: bool = False, work_root: Path | None = None) -> dict:
    """Valida regras e tempos e gera todas as camadas PNG. Não chama o FFmpeg."""
    errors, warnings = check_rules(cfg)
    tl = plan_timeline(cfg, cta_only=cta_only)
    errors += check_timeline(tl, cfg, cta_only=cta_only)
    work = (work_root or OUT_ROOT / "work") / (cfg["id"] + ("_cta" if cta_only else ""))
    work.mkdir(parents=True, exist_ok=True)
    plan = {"timeline": tl, "segments": [], "work_dir": str(work)}
    if errors:  # erros de regra/tempo: não gera camadas
        plan["errors"], plan["warnings"] = errors, warnings
        return plan
    bg_cache: dict[int, tuple[str, Image.Image]] = {}
    for seg in tl.segments:
        if seg.kind == "scene":
            sc = cfg["scenes"][seg.index]
            if seg.index not in bg_cache:
                bg_cache[seg.index] = _bg_file(cfg, sc["source"]["path"], sc["source"].get("focus", [0.5, 0.5]),
                                               work, sc["id"])
            bg_path, bg_small = bg_cache[seg.index]
            lo = layout_scene(cfg, seg, sc, bg_small, work)
            sp = {"segment": seg, "bg_path": bg_path, "camera": sc["camera"], "dim": 0.0}
        elif seg.kind == "hook":
            hook = cfg["hook"]
            if hook["background"] == "brand":
                bg_path, bg_small = _brand_bg(cfg, work, "hook")
                cam, label = hook.get("camera", CTA_CAMERA), (
                    cfg["demo_label"]["text"] if cfg["demo_label"]["enabled"] else None)
            else:
                i = int(hook["background"].split(":")[1])
                sc = cfg["scenes"][i]
                if i not in bg_cache:
                    bg_cache[i] = _bg_file(cfg, sc["source"]["path"], sc["source"].get("focus", [0.5, 0.5]),
                                           work, sc["id"])
                bg_path, bg_small = bg_cache[i]
                cam, label = hook.get("camera", _hook_camera(sc["camera"])), scene_label(cfg, sc)
            lo = layout_hook(cfg, seg, bg_small, work, label)
            sp = {"segment": seg, "bg_path": bg_path, "camera": cam, "dim": cfg["animation"]["hook_dim"]}
        else:
            bg_path, bg_small = _brand_bg(cfg, work, "cta")
            lo = layout_cta(cfg, seg, bg_small, work)
            sp = {"segment": seg, "bg_path": bg_path, "camera": cfg["cta"].get("camera", CTA_CAMERA), "dim": 0.0}
        sp["layers"] = lo.layers
        errors += lo.errors
        errors += check_layers(lo.layers, cfg, seg.key)
        plan["segments"].append(sp)
    if cfg.get("cta") and not any(la.role == "logo" for sp in plan["segments"] if sp["segment"].kind == "cta"
                                  for la in sp["layers"]):
        errors.append("CTA sem logotipo")
    plan["errors"], plan["warnings"] = errors, warnings
    return plan


def plan_to_json(plan: dict) -> dict:
    return {
        "timeline": plan["timeline"].to_dict(),
        "segments": [{"key": sp["segment"].key, "kind": sp["segment"].kind, "bg": _rel(sp["bg_path"]),
                      "camera": sp["camera"], "dim": sp["dim"],
                      "layers": [{**la.to_dict(), "path": _rel(la.path)} for la in sp["layers"]]}
                     for sp in plan["segments"]],
        "errors": plan["errors"], "warnings": plan["warnings"],
    }


def render(plan: dict, cfg: dict, out_path: Path) -> dict:
    """Passe 1: um intermediário por segmento. Passe 2: xfade + codificação final."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = Path(plan["work_dir"])
    t0 = time.monotonic()
    seg_files, per_seg = [], []
    for sp in plan["segments"]:
        f = work / f"{sp['segment'].key}__seg.mp4"
        cmd = build_segment_command(sp, cfg, str(f))
        ts = time.monotonic()
        proc = run(cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg falhou no segmento {sp['segment'].key}:\n{proc.stderr[-4000:]}")
        per_seg.append({"segment": sp["segment"].key, "wall_s": round(time.monotonic() - ts, 2),
                        "inputs": cmd.count("-i")})
        seg_files.append(str(f))
    cmd = build_final_command(seg_files, plan, cfg, str(out_path))
    ts = time.monotonic()
    proc = run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou no passe final ({proc.returncode}):\n{proc.stderr[-4000:]}")
    final_s = round(time.monotonic() - ts, 2)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {"wall_s": round(time.monotonic() - t0, 2), "final_pass_s": final_s, "segments": per_seg,
            "peak_rss_mb": round(peak / 1024, 1),
            "peak_rss_note": "maior RSS entre os processos-filho (FFmpeg) desta execução",
            "threads": cfg["output"]["threads"], "preset": cfg["output"]["preset"]}


def verify(video: Path, cfg: dict, plan: dict, frames_dir: Path, cta_only: bool = False) -> tuple[list, list, list, dict]:
    """Checagens técnicas + quadros de verificação + logo + movimento. Retorna (checks, frames, warnings)."""
    v = cfg["validation"]
    o = cfg["output"]
    dr = None if cta_only else (v["duration_min"], v["duration_max"])
    tech = check_video(video, cfg, dr)
    checks = tech["checks"]
    warns: list[str] = []
    tl = plan["timeline"]
    total = tech["duration_s"]
    frames = []

    def grab(label, t):
        t = min(max(t, 0.0), total - 3.0 / o["fps"])
        p = extract_frame(video, t, frames_dir / f"{len(frames):02d}_{label}.jpg")
        frames.append({"label": label, "t": t, "path": _rel(p), "stddev": frame_stddev(p), "_abs": p})

    grab("inicio", 0.0)
    for sp in plan["segments"]:
        seg = sp["segment"]
        mid = seg.start + (seg.content_start + seg.content_end) / 2
        if seg.kind == "cta":
            mid = seg.end - 0.25
        grab(f"{seg.kind}_{seg.key}_meio", mid)
    grab("fim", total)
    for f in frames:
        checks.append({"check": f"quadro '{f['label']}' não uniforme", "ok": f["stddev"] >= v["min_frame_stddev"],
                       "detail": f"desvio-padrão {f['stddev']:.1f}", "blocking": True})

    # logo íntegro: compara o PNG da camada com o quadro decodificado
    by_label = {f["label"]: f for f in frames}
    for sp in plan["segments"]:
        seg = sp["segment"]
        for la in sp["layers"]:
            if la.role != "logo":
                continue
            fr = by_label[f"{seg.kind}_{seg.key}_meio"]
            mad = logo_mad(fr["_abs"], la)
            checks.append({"check": f"logo íntegro ({seg.key})", "ok": mad <= v["logo_max_mad"],
                           "detail": f"diferença média {mad:.2f} (máx. {v['logo_max_mad']})", "blocking": True})

    # movimento: quadros consecutivos num trecho sem animação de texto
    for sp in plan["segments"]:
        seg = sp["segment"]
        if seg.kind != "scene":
            continue
        anim = [la for la in sp["layers"] if la.anim not in ("static", "none")]
        q0 = max([seg.content_start] + [la.t_in + la.fade_in + 0.2 for la in anim])
        q1 = min([seg.content_end] + [la.t_out - la.fade_out for la in anim if la.fade_out > 0])
        n = int(min(max((q1 - q0) * o["fps"], 3), 12))
        diffs = consecutive_diffs(video, seg.start + q0, n, o["width"], o["height"])
        mean = sum(diffs) / len(diffs) if diffs else 0.0
        ratio = smoothness_ratio(diffs)
        checks.append({"check": f"movimento de câmera presente ({seg.key})", "ok": mean > 0.05,
                       "detail": f"diferença média entre quadros {mean:.3f}", "blocking": True})
        ok = ratio <= v["motion_spike_ratio"]
        checks.append({"check": f"movimento sem saltos ({seg.key})", "ok": ok,
                       "detail": f"máx/mediana = {ratio:.2f} em {len(diffs)} pares "
                                 f"(t={seg.start + q0:.2f}s; limite {v['motion_spike_ratio']})",
                       "blocking": False})
        if not ok:
            warns.append(f"{seg.key}: possível salto de movimento (razão {ratio:.2f})")
    for f in frames:
        f.pop("_abs")
    return checks, frames, warns, tech


def composition_checks(cfg: dict, plan: dict) -> list[dict]:
    tl = plan["timeline"]
    out = []
    hooks = tl.get("hook")
    if cfg.get("hook"):
        out.append({"check": f"gancho ≤ {cfg['validation']['hook_max']} s", "blocking": True,
                    "ok": all(s.duration <= cfg["validation"]["hook_max"] + 1e-6 for s in hooks),
                    "detail": ", ".join(f"{s.duration:.2f} s" for s in hooks)})
    ctas = tl.get("cta")
    if cfg.get("cta"):
        out.append({"check": f"CTA presente e ≥ {cfg['validation']['cta_min']} s", "blocking": True,
                    "ok": bool(ctas) and all(s.duration >= cfg["validation"]["cta_min"] - 1e-6 for s in ctas),
                    "detail": ", ".join(f"{s.duration:.2f} s" for s in ctas)})
    n_layers = sum(len(sp["layers"]) for sp in plan["segments"])
    out.append({"check": "camadas dentro da margem segura, fontes mínimas, contraste e logo",
                "ok": not any(("margem" in e or "px <" in e or "contraste" in e or "logo" in e)
                              for e in plan["errors"]),
                "detail": f"{n_layers} camadas verificadas por geometria", "blocking": True})
    min_c = min((la.contrast for sp in plan["segments"] for la in sp["layers"] if la.contrast is not None),
                default=None)
    if min_c is not None:
        out.append({"check": f"contraste mínimo ≥ {cfg['validation']['min_contrast']}", "blocking": True,
                    "ok": min_c >= cfg["validation"]["min_contrast"], "detail": f"pior caso {min_c:.2f}:1"})
    out.append({"check": "regras de conteúdo (seção 4)", "blocking": True,
                "ok": not plan["errors"], "detail": f"{len(plan['errors'])} erro(s)"})
    return out


def build(config_path: str | Path, out_root: Path | None = None, cta_only: bool = False) -> dict:
    """Pipeline completo. Retorna o relatório (também gravado em JSON/MD)."""
    out_root = Path(out_root or OUT_ROOT)
    t_start = time.monotonic()
    cfg = load_config(config_path)
    plan = prepare(cfg, cta_only=cta_only, work_root=out_root / "work")
    rid = cfg["id"] + ("_cta" if cta_only else "")
    report = {"id": rid, "config": _rel(config_path), "tools": tool_versions(),
              "timeline": plan["timeline"].to_dict(), "errors": list(plan["errors"]),
              "warnings": list(plan["warnings"]), "checks": [], "cta_only": cta_only,
              "sources": [] if cta_only else [
                  {"scene": s["id"], "category": s["category"], "path": s["source"]["path"],
                   "kind": s["source"]["kind"], "origin": s["source"]["origin"], "license": s["source"]["license"]}
                  for s in cfg["scenes"]]}
    work = Path(plan["work_dir"])
    (work / "plan.json").write_text(json.dumps(plan_to_json(plan), ensure_ascii=False, indent=2, default=str),
                                    encoding="utf-8")
    if plan["errors"]:
        report["approved_technical"] = False
        write_report(report, out_root / f"{rid}_report.json", out_root / f"{rid}_report.md")
        raise ConfigError(plan["errors"])
    filename = cfg["output"]["filename"]
    if cta_only:
        filename = filename[:-4] + "_cta.mp4"
    video = out_root / filename
    report["render"] = render(plan, cfg, video)
    report["video_path"] = _rel(video)
    checks, frames, warns, tech = verify(video, cfg, plan, out_root / "frames" / rid, cta_only=cta_only)
    report["checks"] = composition_checks(cfg, plan) + checks
    report["frames"] = frames
    report["warnings"] += warns
    report["duration_s"] = tech["duration_s"]
    report["size_bytes"] = tech["size_bytes"]
    report["video"] = tech["video"]
    report["sha256"] = sha256(video)
    report["frames_md5"] = decoded_md5(video)
    report["pipeline_wall_s"] = round(time.monotonic() - t_start, 2)
    failed = [c for c in report["checks"] if c["blocking"] and not c["ok"]]
    report["errors"] += [f"checagem falhou: {c['check']} ({c['detail']})" for c in failed]
    report["approved_technical"] = not report["errors"]
    report["status"] = "testado localmente (não validado com serviço real; não aprovado para produção)"
    write_report(report, out_root / f"{rid}_report.json", out_root / f"{rid}_report.md")
    return report


def render_cta_only(config_path: str | Path, out_root: Path | None = None) -> dict:
    """Renderiza e valida SOMENTE o CTA (reaproveitável em qualquer reel)."""
    return build(config_path, out_root=out_root, cta_only=True)


def validate_existing(config_path: str | Path, video: str | Path | None = None, out_root: Path | None = None) -> dict:
    """Revalida um MP4 já renderizado contra a config (sem renderizar)."""
    out_root = Path(out_root or OUT_ROOT)
    cfg = load_config(config_path)
    plan = prepare(cfg, work_root=out_root / "work")
    video = Path(video) if video else out_root / cfg["output"]["filename"]
    checks, frames, warns, tech = verify(video, cfg, plan, out_root / "frames" / cfg["id"])
    checks = composition_checks(cfg, plan) + checks
    errors = plan["errors"] + [f"checagem falhou: {c['check']} ({c['detail']})"
                               for c in checks if c["blocking"] and not c["ok"]]
    return {"id": cfg["id"], "video_path": _rel(video), "checks": checks, "frames": frames,
            "errors": errors, "warnings": plan["warnings"] + warns, "approved_technical": not errors,
            "duration_s": tech["duration_s"], "sha256": sha256(video)}
