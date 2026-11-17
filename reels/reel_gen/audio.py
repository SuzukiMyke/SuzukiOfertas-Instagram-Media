"""Arquitetura de áudio (preparada; NÃO usada no piloto, que é silencioso).

Modos:
- ``silent``: sem faixa de áudio (padrão) ou, com ``audio.silent_track = true``,
  uma faixa AAC silenciosa gerada pelo próprio FFmpeg (anullsrc).
- ``licensed``: faixas locais em ``reels/assets/audio_licensed/`` com licença
  documentada (validada em rules.py). Mixagem com volume/afade/amix, ducking
  opcional da música sob a voz e normalização loudnorm.

Narração/TTS: apenas o ponto de extensão ``VoiceProvider``; nenhuma implementação.
Qualquer voz exigirá licença comercial verificada. Nada é baixado ou gerado aqui.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .config import resolve_path
from .motion import _f

SAMPLE_RATE = 48000


class VoiceProvider(ABC):
    """Ponto de extensão para narração. Sem implementação nesta etapa."""

    license_id: str = ""

    @abstractmethod
    def synthesize(self, text: str, out_path: str) -> str:  # pragma: no cover
        """Gera o arquivo de voz e devolve o caminho. Exige licença comercial verificada."""


def build_audio(cfg: dict, first_index: int, total_s: float) -> tuple[list[str], list[str], str | None]:
    """Retorna (args_de_entrada, trechos_de_filtro, rótulo_de_saída | None)."""
    a = cfg["audio"]
    if a["mode"] == "silent":
        if not a["silent_track"]:
            return [], [], None
        inp = ["-f", "lavfi", "-t", _f(total_s), "-i", f"anullsrc=r={SAMPLE_RATE}:cl=stereo"]
        return inp, [f"[{first_index}:a]atrim=duration={_f(total_s)}[aout]"], "[aout]"

    inputs: list[str] = []
    parts: list[str] = []
    labels: list[str] = []
    music, voice = [], []
    for j, tr in enumerate(a["tracks"]):
        idx = first_index + j
        if tr["loop"]:
            inputs += ["-stream_loop", "-1"]
        inputs += ["-i", str(resolve_path(tr["file"]))]
        lab = f"a{j}"
        dur = max(total_s - tr["start"], 0.01)
        chain = [f"aresample={SAMPLE_RATE}", "aformat=channel_layouts=stereo",
                 f"atrim=duration={_f(dur)}", f"volume={_f(tr['gain_db'])}dB"]
        if tr["fade_in"] > 0:
            chain.append(f"afade=t=in:st=0:d={_f(tr['fade_in'])}")
        if tr["fade_out"] > 0:
            chain.append(f"afade=t=out:st={_f(max(dur - tr['fade_out'], 0))}:d={_f(tr['fade_out'])}")
        delay_ms = int(round(tr["start"] * 1000))
        if delay_ms:
            chain.append(f"adelay={delay_ms}:all=1")
        parts.append(f"[{idx}:a]{','.join(chain)}[{lab}]")
        (voice if tr["type"] == "voice" else music).append(lab)

    if a["ducking"] and music and voice:
        # música abaixa automaticamente sob a voz (sidechain)
        parts.append(f"[{']['.join(music)}]amix=inputs={len(music)}:normalize=0[mus]" if len(music) > 1
                     else f"[{music[0]}]anull[mus]")
        parts.append(f"[{']['.join(voice)}]amix=inputs={len(voice)}:normalize=0[voc]" if len(voice) > 1
                     else f"[{voice[0]}]anull[voc]")
        parts.append("[voc]asplit=2[voc1][vocsc]")
        parts.append("[mus][vocsc]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[duck]")
        labels = ["duck", "voc1"]
    else:
        labels = music + voice
    ln = a["loudnorm"]
    mix = (f"[{']['.join(labels)}]amix=inputs={len(labels)}:normalize=0:duration=longest,"
           if len(labels) > 1 else f"[{labels[0]}]")
    parts.append(f"{mix}loudnorm=I={_f(ln['I'])}:TP={_f(ln['TP'])}:LRA={_f(ln['LRA'])},"
                 f"aresample={SAMPLE_RATE},atrim=duration={_f(total_s)}[aout]")
    return inputs, parts, "[aout]"


def audio_output_args(label: str | None) -> list[str]:
    if label is None:
        return ["-an"]
    return ["-map", label, "-c:a", "aac", "-b:a", "160k", "-ar", str(SAMPLE_RATE), "-ac", "2"]
