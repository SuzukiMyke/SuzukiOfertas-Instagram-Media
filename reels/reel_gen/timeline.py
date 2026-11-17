"""Planejador de linha do tempo: segmentos, tempos, transições (xfade) e janelas de texto.

Todas as durações são arredondadas para quadros inteiros (``round(d*fps)``) para
que os offsets do xfade coincidam exatamente com a grade de quadros.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .motion import frames_for

DEFAULT_TRANSITION = {"type": "fade", "duration": 0.4}


@dataclass
class Segment:
    kind: str                 # hook | scene | cta
    key: str                  # id único (hook, s1, ..., cta)
    index: int                # índice da cena (hook/cta: -1)
    frames: int
    fps: int
    trans_in: dict | None = None    # transição que ENTRA neste segmento
    trans_out: dict | None = None   # transição que SAI deste segmento
    start: float = 0.0              # início na linha do tempo final (= offset do xfade)
    extra: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.frames / self.fps

    @property
    def end(self) -> float:
        return self.start + self.duration

    @property
    def content_start(self) -> float:
        """Primeiro instante (local) em que a cena está totalmente visível."""
        return self.trans_in["duration"] if self.trans_in else 0.0

    @property
    def content_end(self) -> float:
        """Último instante (local) antes de a transição de saída começar."""
        return self.duration - (self.trans_out["duration"] if self.trans_out else 0.0)


@dataclass
class Timeline:
    segments: list[Segment]
    fps: int
    errors: list[str]

    @property
    def total(self) -> float:
        return self.segments[-1].end if self.segments else 0.0

    def get(self, kind: str) -> list[Segment]:
        return [s for s in self.segments if s.kind == kind]

    def to_dict(self) -> dict:
        return {
            "fps": self.fps,
            "total_s": round(self.total, 4),
            "segments": [{
                "kind": s.kind, "key": s.key, "start_s": round(s.start, 4), "end_s": round(s.end, 4),
                "duration_s": round(s.duration, 4), "frames": s.frames,
                "transition_in": s.trans_in, "transition_out": s.trans_out,
            } for s in self.segments],
        }


def _quantize_tr(tr: dict, fps: int) -> dict:
    return {"type": tr["type"], "duration": frames_for(tr["duration"], fps) / fps}


def plan_timeline(cfg: dict, cta_only: bool = False) -> Timeline:
    fps = cfg["output"]["fps"]
    errs: list[str] = []
    segs: list[Segment] = []
    if not cta_only:
        hook = cfg.get("hook")
        if hook:
            segs.append(Segment("hook", "hook", -1, frames_for(hook["duration"], fps), fps,
                                trans_out=_quantize_tr(hook.get("transition_out", DEFAULT_TRANSITION), fps)))
        for i, sc in enumerate(cfg["scenes"]):
            segs.append(Segment("scene", sc["id"], i, frames_for(sc["duration"], fps), fps,
                                trans_out=_quantize_tr(sc.get("transition_out", DEFAULT_TRANSITION), fps)))
    if cfg.get("cta"):
        segs.append(Segment("cta", "cta", -1, frames_for(cfg["cta"]["duration"], fps), fps))
    elif cta_only:
        errs.append("cta ausente: não há o que renderizar")

    if segs:
        segs[-1].trans_out = None  # o último segmento não tem transição de saída
    keys = [s.key for s in segs]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        errs.append(f"ids de segmento repetidos: {sorted(dup)}")

    t = 0.0
    for i, s in enumerate(segs):
        if i == 0:
            s.start = 0.0
        else:
            s.trans_in = segs[i - 1].trans_out
            s.start = t - s.trans_in["duration"]
        t = s.start + s.duration
        # sanidade das transições
        tin = s.trans_in["duration"] if s.trans_in else 0.0
        tout = s.trans_out["duration"] if s.trans_out else 0.0
        if tin + tout >= s.duration:
            errs.append(f"{s.key}: transições ({tin:.2f}+{tout:.2f} s) consomem toda a duração ({s.duration:.2f} s)")
    return Timeline(segs, fps, errs)


def check_timeline(tl: Timeline, cfg: dict, cta_only: bool = False) -> list[str]:
    """Regras de tempo: gancho <= hook_max, CTA >= cta_min, duração total."""
    v = cfg["validation"]
    errs = list(tl.errors)
    for s in tl.get("hook"):
        if s.duration > v["hook_max"] + 1e-6:
            errs.append(f"gancho com {s.duration:.2f} s (máximo {v['hook_max']} s)")
    ctas = tl.get("cta")
    if cfg.get("cta"):
        for s in ctas:
            if s.duration < v["cta_min"] - 1e-6:
                errs.append(f"CTA com {s.duration:.2f} s (mínimo {v['cta_min']} s)")
    if not cta_only:
        lo = v["duration_min"] - v["duration_tolerance"]
        hi = v["duration_max"] + v["duration_tolerance"]
        if not (lo <= tl.total <= hi):
            errs.append(f"duração total planejada {tl.total:.2f} s fora de [{v['duration_min']}, {v['duration_max']}] s")
        if tl.total > v["duration_hard_max"]:
            errs.append(f"duração {tl.total:.2f} s acima do teto de {v['duration_hard_max']} s")
    return errs
