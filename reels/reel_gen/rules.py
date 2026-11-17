"""Regras de confiabilidade e segurança de conteúdo (erros bloqueantes).

Lê a política em ``configs/content_policy.json`` (termos proibidos, canais oficiais,
campos comerciais que exigem verificação). Nada aqui faz acesso à rede.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .config import POLICY_FILE, REELS_ROOT, REPO_ROOT, load_json, resolve_path, strip_comments

AUDIO_DIR = REELS_ROOT / "assets" / "audio_licensed"
_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def load_policy(path: Path = POLICY_FILE) -> dict:
    return strip_comments(load_json(path))


def fold(s: str) -> str:
    """minúsculas, sem acentos, espaços normalizados (para comparar termos)."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def is_remote(p: str) -> bool:
    return bool(_URL_RE.match(p.strip())) or p.strip().startswith("//")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def check_local_file(p: str, where: str, errs: list[str], root: Path = REPO_ROOT) -> Path | None:
    if is_remote(p):
        errs.append(f"{where}: URL remota proibida ({p}); use apenas arquivos locais do repositório")
        return None
    full = resolve_path(p)
    if not _inside(full, root):
        errs.append(f"{where}: caminho fora de {root.name}/ não é permitido ({p})")
        return None
    if not full.is_file():
        errs.append(f"{where}: arquivo não encontrado ({p})")
        return None
    return full


def text_fields(cfg: dict):
    """Gera (onde, texto) para todo texto que aparece na tela."""
    if cfg.get("demo_label", {}).get("enabled"):
        yield "demo_label.text", cfg["demo_label"]["text"]
    hook = cfg.get("hook")
    if hook:
        for i, ln in enumerate(hook["lines"]):
            yield f"hook.lines[{i}]", ln
    for i, sc in enumerate(cfg["scenes"]):
        for k in ("category", "title", "subtitle", "label", "badge", "price", "discount", "stock", "rating"):
            if sc.get(k):
                yield f"scenes[{i}].{k}", sc[k]
        for j, h in enumerate(sc.get("highlights", [])):
            yield f"scenes[{i}].highlights[{j}].text", h["text"]
    cta = cfg.get("cta")
    if cta:
        yield "cta.headline", cta["headline"]
        yield "cta.disclosure", cta["disclosure"]
        for j, b in enumerate(cta["buttons"]):
            yield f"cta.buttons[{j}]", b
    for k, ch in (cfg.get("channels") or {}).items():
        yield f"channels.{k}.label", ch["label"]
        yield f"channels.{k}.display", ch["display"]


def forbidden_terms(cfg: dict, policy: dict) -> list[str]:
    extra = (cfg.get("policy") or {}).get("extra_forbidden_terms", [])
    return [fold(t) for t in list(policy["forbidden_terms"]) + list(extra)]


def find_forbidden(text: str, terms: list[str]) -> list[str]:
    ft = fold(text)
    hits = []
    for term in terms:
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", ft):
            hits.append(term)
    return hits


def scene_label(cfg: dict, scene: dict) -> str | None:
    """Rótulo exibido na tela para a cena (None para foto real sem rótulo)."""
    kind = scene["source"]["kind"]
    if scene.get("label"):
        return scene["label"]
    if kind == "synthetic_demo":
        return cfg["demo_label"]["text"] if cfg["demo_label"]["enabled"] else None
    if kind == "illustrative":
        return cfg["illustrative_label"]
    return None


def resolve_buttons(cfg: dict) -> list[tuple[str, dict]]:
    """Botões do CTA -> [(chave_canal, canal)]. Casamento por chave ou rótulo (sem acento/caixa)."""
    chans = cfg.get("channels") or {}
    out = []
    for b in cfg["cta"]["buttons"]:
        fb = fold(b)
        match = [(k, c) for k, c in chans.items() if fold(k) == fb or fold(c["label"]) == fb]
        out.append(match[0] if match else (b, None))
    return out


def check_rules(cfg: dict, policy: dict | None = None) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Erros são bloqueantes."""
    policy = policy or load_policy()
    errs: list[str] = []
    warns: list[str] = []
    terms = forbidden_terms(cfg, policy)
    commercial = policy["commercial_fields_requiring_verification"]
    official = policy["official_channels"]

    # logo
    check_local_file(cfg["logo"]["path"], "logo.path", errs)

    # cenas
    cats = []
    for i, sc in enumerate(cfg["scenes"]):
        where = f"scenes[{i}]"
        src = sc["source"]
        if src["kind"] not in policy["allowed_source_kinds"]:
            errs.append(f"{where}.source.kind: '{src['kind']}' não permitido pela política")
        check_local_file(src["path"], f"{where}.source.path", errs)
        if not src.get("origin", "").strip():
            errs.append(f"{where}.source.origin: obrigatório")
        if not src.get("license", "").strip():
            errs.append(f"{where}.source.license: obrigatório")
        if src["kind"] != "real_photo":
            if not (scene_label(cfg, sc) or "").strip():
                errs.append(f"{where}: imagem '{src['kind']}' exige rótulo na tela "
                            f"(ative demo_label ou defina scenes[{i}].label)")
            if src["kind"] == "synthetic_demo" and not cfg["demo_label"]["enabled"]:
                errs.append(f"{where}: material sintético exige demo_label.enabled = true")
            if sc.get("product_model"):
                errs.append(f"{where}.product_model: imagem não real não pode representar modelo específico de produto")
        present = [k for k in commercial if str(sc.get(k, "")).strip()]
        if present:
            if not (str(sc.get("verified_at", "")).strip() and str(sc.get("source_url", "")).strip()):
                errs.append(f"{where}: {present} exige verified_at e source_url")
            elif not re.match(r"^https://", sc["source_url"]):
                errs.append(f"{where}.source_url: deve ser https://")
            if src["kind"] != "real_photo":
                errs.append(f"{where}: {present} só pode acompanhar foto real do produto (kind=real_photo)")
        for j, h in enumerate(sc.get("highlights", [])):
            if h["at"] >= sc["duration"]:
                errs.append(f"{where}.highlights[{j}].at: {h['at']} s fora da duração da cena ({sc['duration']} s)")
        cats.append(fold(sc["category"]))
    if len(set(cats)) < len(cats):
        warns.append("há cenas com a mesma categoria")

    # gancho
    hook = cfg.get("hook")
    if hook and hook["background"].startswith("scene:"):
        idx = int(hook["background"].split(":")[1])
        if idx >= len(cfg["scenes"]):
            errs.append(f"hook.background: cena {idx} não existe")

    # termos proibidos
    for where, txt in text_fields(cfg):
        for term in find_forbidden(txt, terms):
            errs.append(f"{where}: termo proibido '{term}' em {txt!r}")

    # CTA e canais
    cta = cfg.get("cta")
    chans = cfg.get("channels") or {}
    for k, ch in chans.items():
        if k not in official:
            errs.append(f"channels.{k}: canal não registrado na política (permitidos: {sorted(official)})")
        elif ch["url"].rstrip("/") != official[k].rstrip("/"):
            errs.append(f"channels.{k}.url: difere do canal oficial registrado")
    if cta:
        if not cta["disclosure"].strip():
            errs.append("cta.disclosure: obrigatório quando há CTA")
        if not cta["independent_background"]:
            warns.append("cta.independent_background = false: CTA não poderá ser reaproveitado isoladamente")
        for b, ch in resolve_buttons(cfg):
            if ch is None:
                errs.append(f"cta.buttons: '{b}' não corresponde a nenhum canal em channels")

    # áudio
    audio = cfg["audio"]
    if audio["mode"] == "silent" and audio["tracks"]:
        errs.append("audio.tracks: deve ficar vazio no modo silent")
    if audio["mode"] == "licensed":
        if not audio["tracks"]:
            errs.append("audio.tracks: modo licensed exige ao menos uma faixa")
        for j, tr in enumerate(audio["tracks"]):
            check_local_file(tr["file"], f"audio.tracks[{j}].file", errs, root=AUDIO_DIR)
            for k in ("license_id", "license_url_or_proof", "author"):
                if not str(tr.get(k, "")).strip():
                    errs.append(f"audio.tracks[{j}].{k}: licença não documentada")
    return errs, warns
